# backend/routers/chat_router.py
"""
Mosaic Studio - Architecture Chatbot (grounded in the canonical model)
=======================================================================
Answers are built from the stored architecture model, never from hardcoded
facts. Every claim a component, database, endpoint or score is read from the
model at request time. Modifications requested in chat are applied to the
model (and persisted) only when a real change occurs — the bot never claims a
change happened unless it did.
"""
import json
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.database import get_db, User, Analysis, ChatHistory
from backend.auth import get_current_user
from backend.config import settings
from backend.agents.model import (
    as_text,
    ensure_dict,
    ensure_list,
    normalize_component,
    validate_model,
    to_legacy_fields,
)

router = APIRouter(prefix="/chat", tags=["Architecture Discussion Chat"])


class ChatMessageRequest(BaseModel):
    content: str
    explanation_level: Optional[str] = "brief"  # brief, long, detailed


class ChatMessageResponse(BaseModel):
    response: str
    follow_up_suggestions: List[str]
    conversation_length: int
    explanation_level: str
    modification_applied: Optional[bool] = False
    modified_sections: Optional[List[str]] = []


# ── Model snapshot helpers ───────────────────────────────────────────────────

def model_snapshot(analysis: Analysis) -> dict:
    """Return the canonical model for an analysis, re-hosting legacy rows if needed."""
    if analysis.architecture_model:
        return analysis.architecture_model
    from backend.agents.model import from_legacy
    return from_legacy(
        analysis.business_problem,
        requirements=analysis.requirements,
        architecture_design=analysis.architecture_design,
        database_schema=analysis.database_schema,
        api_specification=analysis.api_specification,
        deployment_config=analysis.deployment_config,
        security_audit=analysis.security_audit,
        performance_strategies=analysis.performance_strategies,
        diagrams=analysis.diagrams,
    )


def persist_model(db: Session, analysis: Analysis, model: dict) -> None:
    """Persist the canonical model and keep legacy fields in sync."""
    legacy = to_legacy_fields(model)
    analysis.architecture_model = model
    analysis.requirements = legacy["requirements"]
    analysis.architecture_design = legacy["architecture_design"]
    analysis.database_schema = legacy["database_schema"]
    analysis.api_specification = legacy["api_specification"]
    analysis.deployment_config = legacy["deployment_config"]
    analysis.security_audit = legacy["security_audit"]
    analysis.performance_strategies = legacy["performance_strategies"]
    analysis.diagrams = legacy["diagrams"]
    analysis.updated_at = datetime.now(timezone.utc)


# ── Intent classification ────────────────────────────────────────────────────

INTENT_PATTERNS = {
    "greeting": ["hi", "hello", "hey", "hai", "good morning", "who are you", "help", "welcome"],
    "architecture": ["why", "chose", "choose", "pattern", "topology", "reason", "decision", "design", "overview", "explain"],
    "database": ["database", "db", "sql", "postgres", "mongo", "schema", "tables", "storage", "cache", "redis", "index"],
    "api": ["api", "endpoint", "rest", "swagger", "openapi", "route", "graphql", "websocket"],
    "security": ["security", "vulnerability", "auth", "jwt", "compliance", "hipaa", "soc2", "audit", "encrypt"],
    "deployment": ["cost", "aws", "gcp", "azure", "budget", "price", "cloud", "terraform", "k8s", "kubernetes", "deploy", "iaac", "ci/cd"],
    "component": ["component", "service", "stack", "technology", "tech", "node", "building block", "scal", "replic"],
    "performance": ["performance", "load", "throughput", "latency", "bottleneck", "rps", "requests per second", "concurr"],
    "diagram": ["diagram", "level 1", "level 2", "level 3", "mermaid", "production", "show me the flow", "topology"],
    "modify": ["change", "switch", "replace", "add", "remove", "delete", "use ", "make it", "scale", "increase", "update", "migrate", "turn on", "enable", "disable"],
    "troubleshoot": ["bug", "not working", "crash", "error", "failed", "broken", "issue", "debug", "fail"],
    "thanks": ["fixed", "worked", "thanks", "thank you", "wow", "solved", "great", "awesome"],
}


# Imperative phrases that unambiguously request a model change. These mirror the
# regexes in _apply_modification, so a query is only treated as a modification when
# the engine can actually apply it. Checked before the question-keyword intents.
MODIFY_PATTERNS = [
    re.compile(r"(?:change|switch|replace|update|migrate)\s+(?:the\s+)?(?:database|db|store)\b"),
    re.compile(r"(?:database|db|store)\s+(?:to|with|as)\s+[a-z0-9 _-]{2,30}"),
    re.compile(r"(?:change|switch|replace|update)\s+(?:the\s+)?(?:architecture|pattern)\b"),
    re.compile(r"(?:use|switch to|make it)\s+(?:a\s+)?microservices\b"),
    re.compile(r"(?:add|enable|turn on|introduce)\s+(?:a\s+)?cache\b"),
    re.compile(r"(?:scale|increase|grow|support)\b.*\b(?:users|requests|rps|req)\b"),
]


def classify_intent(question: str) -> str:
    q = question.lower()
    if any(p.search(q) for p in MODIFY_PATTERNS):
        return "modify"
    for intent, keywords in INTENT_PATTERNS.items():
        if intent == "modify":
            continue
        if any(k in q for k in keywords):
            return intent
    return "general"


# ── Grounded answer builder ──────────────────────────────────────────────────

def _comp_line(c: dict, detailed: bool = False) -> str:
    name = as_text(c.get("name"))
    tech = as_text(c.get("technology"))
    resp = as_text(c.get("responsibility"))
    loc = as_text(c.get("internal_or_external"))
    base = f"- **{name}** ({tech})"
    if detailed:
        return f"{base} — {resp} [{loc}]\n  - scaling: {as_text(c.get('scaling_strategy')) or 'horizontal'}\n  - failure: {as_text(c.get('failure_behavior')) or 'retry/backoff'}\n  - security: {as_text(c.get('security_considerations')) or 'n/a'}"
    return f"{base}: {resp}"


def grounded_answer(question: str, model: dict, intent: str, level: str) -> str:
    arch = ensure_dict(model.get("architecture"))
    reqs = ensure_dict(model.get("requirements"))
    db = ensure_dict(model.get("database"))
    api = ensure_dict(model.get("api"))
    sec = ensure_dict(model.get("security"))
    dep = ensure_dict(model.get("deployment"))
    perf = ensure_dict(model.get("performance"))
    review = ensure_dict(model.get("review"))
    workload = ensure_dict(perf.get("workload"))
    comps = ensure_list(arch.get("components"))

    names = [as_text(c.get("name")) for c in comps if as_text(c.get("name"))]
    score = review.get("overall_score")
    db_type = as_text(db.get("database_type")) or "not yet decided"
    pattern = as_text(arch.get("pattern")) or "not yet decided"
    system_type = as_text(arch.get("system_type")) or "your system"
    avg_rps = workload.get("avg_requests_per_second")
    peak_rps = workload.get("peak_requests_per_second")

    def top_n(limit=5):
        return ", ".join(names[:limit]) if names else "the core service"

    if intent == "greeting":
        return (
            f"Hi! I'm your architecture assistant for **{system_type}**.\n"
            f"It uses a **{pattern}** with {len(comps)} components and a **{db_type}** database. "
            f"Ask me about the components, database, APIs, security, deployment, or ask me to change something."
        )

    if intent == "architecture":
        reasons = ""
        if as_text(arch.get("justification")):
            reasons = as_text(arch.get("justification"))
        lines = [
            f"**{system_type}** uses a **{pattern}** pattern.",
            f"**Why:** {reasons}",
            f"**Components ({len(comps)}):**",
        ]
        lines += [_comp_line(c, detailed=(level != "brief")) for c in comps[: (6 if level != "brief" else 4)]]
        decisions = ensure_list(arch.get("decisions"))
        if decisions and level != "brief":
            lines.append("**Key decisions (ADR):**")
            for d in decisions[:3]:
                lines.append(f"- {as_text(d.get('decision'))} — {as_text(d.get('reason'))}")
        return "\n".join(lines)

    if intent == "database":
        lines = [
            f"The persistence layer is **{db_type}**.",
            f"**Why:** {as_text(db.get('justification')) or 'chosen to match the workload'}",
        ]
        schemas = ensure_list(db.get("schemas"))
        if schemas:
            lines.append(f"**Tables ({len(schemas)}):** " + ", ".join(
                as_text(s.get("table_name")) or as_text(s.get("name")) for s in schemas[:6]
            ))
        if as_text(db.get("sharding")):
            lines.append(f"**Sharding:** {as_text(db.get('sharding'))}")
        if as_text(db.get("caching_layer")):
            lines.append(f"**Cache:** {as_text(db.get('caching_layer'))}")
        return "\n".join(lines)

    if intent == "api":
        endpoints = ensure_list(api.get("endpoints"))
        protocol = as_text(api.get("protocol")) or "REST HTTP / JSON"
        lines = [f"The API surface is **{protocol}** with {len(endpoints)} endpoint(s).",
                 f"**Auth:** {as_text(api.get('authentication_strategy')) or 'n/a'}"]
        if endpoints:
            lines.append("**Endpoints:**")
            lines += [
                f"- `{as_text(e.get('method'))}` **{as_text(e.get('path'))}** — {as_text(e.get('description'))}"
                for e in endpoints[:6]
            ]
        if as_text(api.get("rate_limits")):
            lines.append(f"**Rate limits:** {as_text(api.get('rate_limits'))}")
        return "\n".join(lines)

    if intent == "security":
        lines = [f"**Auth strategy:** {as_text(sec.get('authentication_strategy')) or 'n/a'}",
                 f"**Authorization:** {as_text(sec.get('authorization')) or 'n/a'}",
                 f"**Compliance:** {as_text(sec.get('compliance')) or 'n/a'}"]
        mitigations = ensure_list(sec.get("vulnerability_mitigations"))
        if mitigations:
            lines.append(f"**Mitigations ({len(mitigations)}):**")
            for m in mitigations[:5]:
                if isinstance(m, dict):
                    lines.append(f"- {as_text(m.get('vulnerability'))}: {as_text(m.get('mitigation'))}")
                else:
                    lines.append(f"- {m}")
        scores = ensure_dict(sec.get("scores"))
        if scores:
            lines.append("**Scores:** " + ", ".join(f"{k}={v}" for k, v in scores.items()))
        return "\n".join(lines)

    if intent == "deployment":
        lines = [f"**Provider:** {as_text(dep.get('provider')) or 'n/a'}",
                 f"**Orchestration:** {as_text(dep.get('orchestration')) or 'none (single host)'}",
                 f"**IaC:** {as_text(dep.get('infrastructure_as_code'))}",
                 f"**Scaling policy:** {as_text(dep.get('scaling_policy')) or 'n/a'}",
                 f"**DR:** {as_text(dep.get('disaster_recovery')) or 'n/a'}"]
        if level != "brief" and as_text(dep.get("terraform_sample")):
            lines.append("**Terraform:**")
            lines.append("```hcl\n" + as_text(dep.get("terraform_sample")) + "\n```")
        return "\n".join(lines)

    if intent == "performance":
        lines = []
        if avg_rps or peak_rps:
            lines.append(
                f"**Workload:** {avg_rps} req/s avg, {peak_rps} req/s peak "
                f"(concurrency {workload.get('expected_concurrency') or 'n/a'})."
            )
        if workload.get("assumptions"):
            lines.append("**Load assumptions:**")
            for a in ensure_list(workload.get("assumptions"))[:3]:
                if isinstance(a, dict):
                    lines.append(f"- {as_text(a.get('label'))}: {as_text(a.get('text'))}")
                else:
                    lines.append(f"- {a}")
        for key, label in (("cache_requirements", "Cache"), ("queue_requirements", "Queue")):
            val = as_text(perf.get(key))
            if val:
                lines.append(f"**{label}:** {val}")
        bottlenecks = ensure_list(perf.get("bottlenecks"))
        if bottlenecks:
            lines.append("**Bottlenecks:**")
            for b in bottlenecks[:3]:
                if isinstance(b, dict):
                    lines.append(f"- {as_text(b.get('component'))}: {as_text(b.get('reason'))}")
                else:
                    lines.append(f"- {b}")
        if not lines:
            lines.append("No load analysis recorded yet.")
        return "\n".join(lines)

    if intent == "component":
        lines = [f"The system has **{len(comps)}** components: {top_n()}."]
        for c in comps[:6]:
            lines.append(_comp_line(c, detailed=(level != "brief")))
        return "\n".join(lines)

    if intent == "diagram":
        level_map = {
            "level 1": "level1", "level1": "level1",
            "level 2": "level2", "level2": "level2",
            "level 3": "level3", "level3": "level3",
            "production": "level3",
        }
        q = question.lower()
        target = None
        for key, value in level_map.items():
            if key in q:
                target = value
                break
        if not target:
            target = "level2"
        d = ensure_dict(model.get("diagrams", {}).get(target))
        mermaid = as_text(d.get("mermaid"))
        if not mermaid:
            d = ensure_dict(model.get("diagrams", {}).get("legacy"))
            mermaid = as_text(d.get("mermaid"))
        if not mermaid:
            return f"I don't have a diagram for '{target}' yet."
        title = as_text(d.get("title")) or target.upper()
        return f"**{title}**\n\n```mermaid\n{mermaid}\n```"

    if intent == "troubleshoot":
        failure_scenarios = ensure_list(model.get("failure_scenarios"))
        lines = ["Here is how this design handles failure:"]
        if failure_scenarios:
            for f in failure_scenarios[:4]:
                if isinstance(f, dict):
                    lines.append(f"- {as_text(f.get('scenario') or f.get('failure'))}: {as_text(f.get('handling') or f.get('mitigation'))}")
                else:
                    lines.append(f"- {f}")
        for c in comps[:4]:
            fb = as_text(c.get("failure_behavior"))
            if fb:
                lines.append(f"- **{as_text(c.get('name'))}:** {fb}")
        if len(lines) == 1:
            lines.append("No explicit failure analysis recorded.")
        return "\n".join(lines)

    if intent == "modify":
        return (
            "I can apply that change for you. Please be specific, for example:\n"
            "- \"change the database to PostgreSQL\"\n"
            "- \"add a cache layer\"\n"
            "- \"use microservices instead\"\n"
            "- \"scale to 1 million users\"\n"
            "If you already asked a concrete change, tell me exactly what to set."
        )

    if intent == "thanks":
        return f"You're welcome! The **{pattern}** design for **{system_type}** is saved in this analysis — ask me anything about it."

    # general
    lines = [
        f"Here's a quick overview of **{system_type}** ({pattern}):",
        f"- Components: {top_n()}",
        f"- Database: {db_type}",
        f"- API: {as_text(api.get('protocol')) or 'REST'} with {len(ensure_list(api.get('endpoints')))} endpoint(s)",
        f"- Load: {avg_rps} req/s avg / {peak_rps} req/s peak" if avg_rps or peak_rps else f"- Load: not specified",
    ]
    if score is not None:
        lines.append(f"- Reviewer score: **{score}/100**")
    if as_text(sec.get("compliance")):
        lines.append(f"- Compliance: {as_text(sec.get('compliance'))}")
    lines.append("Ask about architecture, database, API, security, performance, diagrams, or request a change.")
    return "\n".join(lines)


def follow_up_suggestions(model: dict, intent: str, level: str) -> List[str]:
    comps = ensure_list(model.get("architecture", {}).get("components"))
    names = [as_text(c.get("name")) for c in comps if as_text(c.get("name"))]
    base = {
        "greeting": ["Why did you choose this architecture?", "Show the database design", "Show API endpoints"],
        "architecture": ["What are the trade-offs?", "Show deployment config", "Explain security measures"],
        "database": ["Show the SQL schema", "How is caching configured?", "Explain indexing strategies"],
        "api": ["How are tokens validated?", "Is there rate limiting?", "Show request payloads"],
        "security": ["Show compliance details", "What scores did the review give?", "List threat model entries"],
        "deployment": ["How to reduce costs?", "Show the scaling policy", "What if traffic doubles?"],
        "performance": ["What is the bottleneck?", "Show workload assumptions", "Scale to 1 million users"],
        "component": ["Explain database schema", "Show API endpoints", "What about security?"],
        "diagram": ["Show level 1", "Show level 3 (production)", "Explain the components"],
        "modify": ["Change the database to PostgreSQL", "Add a cache layer", "Use microservices instead"],
        "troubleshoot": ["How does failover work?", "Show security audit", "What are retry policies?"],
        "thanks": ["Download report", "View Terraform IaC", "Ask another question"],
        "general": ["Explain architecture", "Show component details", "What is the workload?"],
    }
    sugg = list(base.get(intent, base["general"]))
    if names:
        sugg = sugg[:2] + [f"What does {names[0]} do?"] + sugg[2:]
    if level == "brief":
        sugg.append("Give me a detailed explanation")
    elif level == "long":
        sugg.append("Show me the full technical details")
    return sugg[:4]


# ── Modification engine ──────────────────────────────────────────────────────

def _apply_modification(question: str, model: dict) -> tuple:
    """Return (modified, changed_sections, explanation). Never claims change unless applied."""
    q = question.lower()

    m_db = re.search(r"(?:database|db|store)\s+(?:to|with|as)?\s*([a-z0-9 _-]{2,30})", q)
    if m_db and any(k in q for k in ("change", "switch", "replace", "use", "migrate")):
        known = {
            "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
            "mysql": "MySQL", "mariadb": "MariaDB",
            "mongodb": "MongoDB", "mongo": "MongoDB",
            "redis": "Redis", "dynamodb": "DynamoDB",
            "sqlite": "SQLite", "cassandra": "Cassandra",
        }
        requested = m_db.group(1).strip().lower()
        matched = [canonical for alias, canonical in known.items() if alias in requested]
        if not matched:
            return False, [], f"'{requested}' isn't a database I can safely apply. Try PostgreSQL, MySQL, MongoDB, DynamoDB, or SQLite."
        new_type = matched[0]
        current = as_text(model.get("database", {}).get("database_type"))
        if current.lower() == new_type.lower():
            return False, [], f"The database is already **{new_type}** — no change needed."
        model["database"]["database_type"] = new_type
        model["database"]["justification"] = f"Changed from {current or 'the previous choice'} to {new_type} via chat."
        for c in ensure_list(model.get("architecture", {}).get("components")):
            if c.get("type") == "database":
                c["technology"] = new_type
        changed = ["database"]
        msg = f"Applied: database changed to **{new_type}**. All tabs now reflect this."
        return True, changed, msg

    if any(k in q for k in ("add a cache", "add cache", "enable cache", "turn on cache")):
        comps = ensure_list(model.get("architecture", {}).get("components"))
        if any(c.get("type") == "cache" for c in comps):
            return False, [], "A cache layer already exists — no change needed."
        comps.append(normalize_component({
            "name": "Cache Layer", "type": "cache", "technology": "Redis",
            "responsibility": "Hot-path read caching to offload the database",
            "internal_or_external": "internal",
            "scaling_strategy": "Cluster mode / replication",
            "failure_behavior": "Cache miss falls through to the database",
        }, len(comps)))
        model["architecture"]["components"] = comps
        model["performance"]["cache_requirements"] = "Redis cache added via chat; write-through with TTL for hot reads."
        changed = ["architecture", "performance"]
        return True, changed, "Applied: added a **Redis cache layer**; the architecture and performance tabs are updated."

    if any(k in q for k in ("use microservices", "switch to microservices", "make it microservices")):
        if as_text(model.get("architecture", {}).get("pattern")).lower().startswith("microservices"):
            return False, [], "The architecture is already microservices-based — no change needed."
        model["architecture"]["pattern"] = "Microservices Architecture"
        model["architecture"]["justification"] = "Pattern changed to Microservices via chat for independent scaling and team autonomy."
        changed = ["architecture"]
        return True, changed, "Applied: architecture pattern changed to **Microservices Architecture**."

    m_users = re.search(r"(\d[\d,.]*)\s*(million|thousand|k|m)?\s*(?:users|requests|rps|req)", q)
    if m_users and any(k in q for k in ("scale", "increase", "grow", "support")):
        try:
            num = float(m_users.group(1).replace(",", ""))
            mult = m_users.group(2) or ""
            if mult.startswith("m"):
                num *= 1_000_000
            elif mult.startswith("k"):
                num *= 1_000
        except ValueError:
            return False, [], "I couldn't parse that number."
        workload = ensure_dict(model.get("performance", {}).get("workload"))
        workload["users"] = num
        workload["avg_requests_per_second"] = num * 0.002
        workload["peak_requests_per_second"] = num * 0.006
        workload["assumptions"] = [
            *ensure_list(workload.get("assumptions")),
            {"label": "chat-rescale", "text": f"Rescaled to ~{int(num):,} users via chat."},
        ]
        model["performance"]["workload"] = workload
        changed = ["performance"]
        return True, changed, f"Applied: workload rescaled to **{int(num):,} users** (est. {round(num * 0.002)} req/s avg / {round(num * 0.006)} req/s peak)."

    return False, [], None


# ── Main generator ───────────────────────────────────────────────────────────

async def _llm_grounded(question: str, model: dict, level: str) -> Optional[str]:
    if not settings.OPENAI_API_KEY:
        return None
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        system = (
            "You answer questions ONLY about the provided architecture model. "
            "Never invent facts not present in the model; if a fact is missing say so. "
            "Cite component names, the pattern, and scores from the model. "
            "Answer in markdown with clear headers."
        )
        user = f"Architecture model:\n{json.dumps(model, default=str)}\n\nQuestion: {question}"
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[WARN] Chat LLM failed, using grounded generator: {e}")
        return None


def generate_contextual_response(
    question: str,
    model: dict,
    explanation_level: str = "brief"
) -> tuple:
    intent = classify_intent(question)
    if intent == "modify":
        modified, changed_sections, message = _apply_modification(question, model)
        if message is None:
            message = grounded_answer(question, model, intent, explanation_level)
        return message, follow_up_suggestions(model, intent, explanation_level), modified, changed_sections
    return grounded_answer(question, model, intent, explanation_level), follow_up_suggestions(
        model, intent, explanation_level), False, []


# ── API Endpoints ────────────────────────────────────────────────────────────

@router.post("/{analysis_id}/send", response_model=ChatMessageResponse)
async def send_chat_message(
    analysis_id: str,
    payload: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id,
    ).first()

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    chat = db.query(ChatHistory).filter(
        ChatHistory.analysis_id == analysis_id,
        ChatHistory.user_id == current_user.id,
    ).first()

    if not chat:
        chat = ChatHistory(
            analysis_id=analysis_id,
            user_id=current_user.id,
            messages=[],
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)

    model = model_snapshot(analysis)
    level = payload.explanation_level or "brief"

    content, suggestions, modified, changed_sections = generate_contextual_response(
        payload.content, model, level
    )

    if not modified and "modify" == classify_intent(payload.content):
        # Try the LLM only for conversational replies to modification prompts
        # that the deterministic engine could not apply.
        llm_answer = await _llm_grounded(payload.content, model, level)
        if llm_answer:
            content = llm_answer

    if modified:
        validation_issues = validate_model(model)
        model["validation"] = {
            "issue_count": len(validation_issues),
            "issues": validation_issues,
        }
        persist_model(db, analysis, model)
        db.commit()
        print(f"[OK] Chat modification applied: {changed_sections}")

    user_msg = {
        "role": "user",
        "content": payload.content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    bot_msg = {
        "role": "assistant",
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "explanation_level": level,
        "modification_applied": modified,
        "modified_sections": changed_sections,
    }

    msgs = list(chat.messages or [])
    msgs.append(user_msg)
    msgs.append(bot_msg)
    chat.messages = msgs
    db.commit()

    return ChatMessageResponse(
        response=content,
        follow_up_suggestions=suggestions,
        conversation_length=len(msgs),
        explanation_level=level,
        modification_applied=modified,
        modified_sections=changed_sections,
    )


@router.get("/{analysis_id}/history")
def get_chat_history(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = db.query(ChatHistory).filter(
        ChatHistory.analysis_id == analysis_id,
        ChatHistory.user_id == current_user.id,
    ).first()

    if not chat:
        return {"messages": []}

    return {"messages": chat.messages}


@router.post("/{analysis_id}/clear")
def clear_chat_history(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = db.query(ChatHistory).filter(
        ChatHistory.analysis_id == analysis_id,
        ChatHistory.user_id == current_user.id,
    ).first()

    if chat:
        chat.messages = []
        db.commit()

    return {"success": True}
