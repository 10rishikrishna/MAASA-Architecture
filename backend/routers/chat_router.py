# backend/routers/chat_router.py
"""
Mosaic Studio - Context-Aware Architecture Chatbot
Provides intelligent, analysis-contextual responses with 3 explanation tiers.
"""
import re
import random
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.database import get_db, User, Analysis, ChatHistory
from backend.auth import get_current_user
from backend.config import settings

router = APIRouter(prefix="/chat", tags=["Architecture Discussion Chat"])


class ChatMessageRequest(BaseModel):
    content: str
    explanation_level: Optional[str] = "brief"  # brief, long, detailed


class ChatMessageResponse(BaseModel):
    response: str
    follow_up_suggestions: List[str]
    conversation_length: int
    explanation_level: str


# ── 3-Tier Explanation System ────────────────────────────────────────────────

EXPLANATION_TEMPLATES = {
    "brief": {
        "max_sentences": 3,
        "include_code": False,
        "include_diagram": False,
        "include_analogy": False,
        "style": "concise",
    },
    "long": {
        "max_sentences": 8,
        "include_code": True,
        "include_diagram": True,
        "include_analogy": True,
        "style": "balanced",
    },
    "detailed": {
        "max_sentences": 999,
        "include_code": True,
        "include_diagram": True,
        "include_analogy": True,
        "style": "comprehensive",
    },
}


def get_explanation_template(level: str) -> dict:
    return EXPLANATION_TEMPLATES.get(level, EXPLANATION_TEMPLATES["brief"])


# ── Context-Aware Response Generator ────────────────────────────────────────

class ArchitectureContext:
    """Extracts and structures analysis context for intelligent responses."""

    def __init__(self, analysis: Analysis):
        self.analysis = analysis
        self.arch = analysis.architecture_design or {}
        self.db_schema = analysis.database_schema or {}
        self.api_spec = analysis.api_specification or {}
        self.security = analysis.security_audit or {}
        self.perf = analysis.performance_strategies or {}
        self.deployment = analysis.deployment_config or {}
        self.diagrams = analysis.diagrams or {}

    @property
    def system_type(self) -> str:
        return self.arch.get("system_type", "Domain Architecture")

    @property
    def pattern(self) -> str:
        return self.arch.get("pattern", "Microservices Architecture")

    @property
    def tier(self) -> str:
        return self.arch.get("architecture_tier", "Professional")

    @property
    def components(self) -> list:
        return self.arch.get("components", [])

    @property
    def component_names(self) -> list:
        return [c.get("name", "Service") for c in self.components]

    @property
    def database_type(self) -> str:
        return self.db_schema.get("database_type", "PostgreSQL")

    @property
    def security_score(self) -> int:
        return self.security.get("scores", {}).get("security", 92)

    @property
    def compliance(self) -> str:
        return self.security.get("compliance", "SOC2 / GDPR")

    @property
    def endpoints(self) -> list:
        return self.api_spec.get("endpoints", [])

    @property
    def tables(self) -> list:
        return self.db_schema.get("schemas", [])

    @property
    def mitigation_count(self) -> int:
        return len(self.security.get("vulnerability_mitigations", []))


def generate_brief_response(ctx: ArchitectureContext, question: str, topic: str) -> str:
    """Brief explanation: 2-3 sentences, no code, no diagrams."""

    responses = {
        "greeting": (
            f"Welcome to **{ctx.system_type}** ({ctx.tier} tier)! "
            f"Your architecture uses **{ctx.pattern}** with **{len(ctx.components)} core services** "
            f"and **{ctx.database_type}** database. How can I help?"
        ),
        "architecture": (
            f"Your system uses **{ctx.pattern}** at the **{ctx.tier} tier**. "
            f"This pattern was chosen because {ctx.arch.get('justification', 'it provides optimal component isolation')}. "
            f"The core components are: {', '.join(ctx.component_names[:4])}."
        ),
        "database": (
            f"Your database layer uses **{ctx.database_type}** with {len(ctx.tables)} core tables. "
            f"This choice was made because {ctx.db_schema.get('justification', 'it suits the access patterns')} "
            f"and provides strong transactional integrity."
        ),
        "api": (
            f"Your API uses **{ctx.api_spec.get('protocol', 'REST HTTP/JSON')}** with "
            f"{len(ctx.endpoints)} primary endpoints. All requests pass through the API Gateway "
            f"for JWT validation and rate limiting."
        ),
        "security": (
            f"Security score: **{ctx.security_score}/100** ({ctx.compliance}). "
            f"The system has **{ctx.mitigation_count} vulnerability mitigations** in place."
        ),
        "cost": (
            f"Estimated cloud cost for the **{ctx.tier} tier** is approximately **$240/month** "
            f"on AWS, including compute, database, cache, and API gateway."
        ),
    }

    return responses.get(topic, responses["greeting"])


def generate_long_response(ctx: ArchitectureContext, question: str, topic: str) -> str:
    """Long explanation: 5-8 sentences, includes code snippets and analogies."""

    responses = {
        "greeting": (
            f"**Welcome to {ctx.system_type} ({ctx.tier} Tier)!**\n\n"
            f"Your architecture follows the **{ctx.pattern}** pattern. "
            f"The system is designed to handle high-throughput requests with independent service boundaries.\n\n"
            f"**Core Building Blocks:**\n"
            + "\n".join([f"- **{c.get('name')}** (`{c.get('technology', 'N/A')}`): {c.get('reason', '')}" for c in ctx.components[:5]])
            + f"\n\n**Database:** {ctx.database_type} provides the persistence layer with ACID guarantees. "
            f"**Security Score:** {ctx.security_score}/100 ({ctx.compliance})."
        ),
        "architecture": (
            f"**Architecture Decision Record (ADR):**\n\n"
            f"We selected **{ctx.pattern}** at the **{ctx.tier} Tier**.\n\n"
            f"**Rationale:**\n{ctx.arch.get('justification', 'Optimal component isolation.')}\n\n"
            f"**Key Benefits:**\n"
            f"1. **Fault Isolation:** Failure in one service (e.g., {ctx.component_names[0] if ctx.component_names else 'Core Service'}) "
            f"doesn't cascade to others.\n"
            f"2. **Independent Scaling:** Each service scales horizontally based on its own load.\n"
            f"3. **Team Autonomy:** Engineering teams can deploy services independently.\n\n"
            f"**Trade-offs:** Higher operational complexity vs. monolithic simplicity. "
            f"Requires service mesh, distributed tracing, and centralized logging."
        ),
        "database": (
            f"**Database Design:**\n\n"
            f"- **Primary Engine:** `{ctx.database_type}`\n"
            f"- **Tables:** `{', '.join([t.get('table_name', 'entities') for t in ctx.tables[:5]])}`\n"
            f"- **Cache Layer:** Redis Distributed Cache (1-hour TTL for sessions)\n"
            f"- **Indexing:** {len(ctx.db_schema.get('indexing_strategies', []))} index strategies for query optimization\n\n"
            f"**Schema:**\n"
            + "\n".join([f"```\n{t.get('sql', '')}\n```" for t in ctx.tables[:2]])
        ),
        "api": (
            f"**API Specification ({ctx.api_spec.get('protocol', 'REST HTTP/JSON')}):**\n\n"
            + "\n".join([f"- `{ep.get('method')}` **{ep.get('path')}**: {ep.get('description')}" for ep in ctx.endpoints[:5]])
            + "\n\nAll requests pass through the API Gateway where JWT tokens are validated. "
            f"Rate limiting is enforced at **{settings.RATE_LIMIT_PER_MINUTE} req/min** per IP."
        ),
        "security": (
            f"**Security Audit (Score: {ctx.security_score}/100):**\n\n"
            f"**Compliance:** {ctx.compliance}\n\n"
            f"**Mitigations:**\n"
            + "\n".join([f"- {m}" for m in ctx.security.get('vulnerability_mitigations', [])[:5]])
            + "\n\nIntra-service traffic is encrypted via TLS 1.3 mTLS tunnels."
        ),
    }

    return responses.get(topic, responses["greeting"])


def generate_detailed_response(ctx: ArchitectureContext, question: str, topic: str) -> str:
    """Detailed explanation: Full technical depth with all components."""

    responses = {
        "greeting": (
            f"**{ctx.system_type} — Full Technical Deep Dive ({ctx.tier} Tier)**\n\n"
            f"**Architecture Pattern:** {ctx.pattern}\n\n"
            f"**System Design Philosophy:**\n"
            f"{ctx.arch.get('justification', 'Optimal component isolation.')}\n\n"
            f"**Component Breakdown:**\n"
            + "\n".join([
                f"### {c.get('name')}\n"
                f"- **Technology:** {c.get('technology')}\n"
                f"- **Purpose:** {c.get('reason')}\n"
                f"- **Alternatives:** {', '.join(c.get('alternatives', []))}\n"
                f"- **Trade-offs:** {c.get('tradeoffs', 'N/A')}"
                for c in ctx.components[:6]
            ])
            + f"\n\n**Database Layer:**\n"
            f"- **Engine:** {ctx.database_type}\n"
            f"- **Justification:** {ctx.db_schema.get('justification', 'N/A')}\n"
            f"- **Tables:**\n"
            + "\n".join([f"```\n{t.get('sql', '')}\n```" for t in ctx.tables])
            + f"\n- **Indexing Strategies:**\n"
            + "\n".join([f"  - {s}" for s in ctx.db_schema.get('indexing_strategies', [])])
            + f"\n\n**API Layer:**\n"
            f"- **Protocol:** {ctx.api_spec.get('protocol', 'REST')}\n"
            + "\n".join([f"- `{ep.get('method')}` **{ep.get('path')}**\n  {ep.get('description')}" for ep in ctx.endpoints[:6]])
            + f"\n\n**Security:**\n"
            f"- **Score:** {ctx.security_score}/100\n"
            f"- **Compliance:** {ctx.compliance}\n"
            f"- **Mitigations:**\n"
            + "\n".join([f"  - {m}" for m in ctx.security.get('vulnerability_mitigations', [])])
            + f"\n\n**Deployment:**\n"
            f"- **IaC:** {ctx.deployment.get('infrastructure_as_code', 'Terraform')}\n"
            f"- **Orchestration:** {ctx.deployment.get('orchestration', 'Kubernetes')}\n"
            f"```hcl\n{ctx.deployment.get('terraform_sample', '')}\n```\n"
            f"```yaml\n{ctx.deployment.get('kubernetes_manifest', '')}\n```"
        ),
    }

    return responses.get(topic, _generate_fallback_detailed(ctx, question))


def _generate_fallback_detailed(ctx: ArchitectureContext, question: str) -> str:
    """Generate a detailed fallback response for any question."""
    return (
        f"**Question:** {question}\n\n"
        f"**Context in {ctx.system_type} ({ctx.pattern}, {ctx.tier} tier):**\n\n"
        f"In this architecture, the request flows through the following path:\n"
        f"1. **Client** sends request via HTTPS/TLS\n"
        f"2. **CDN/WAF** (Cloudflare) filters malicious traffic and caches static assets\n"
        f"3. **API Gateway** (Kong) validates JWT tokens and enforces rate limits\n"
        f"4. **Service Mesh** routes to the appropriate service: {', '.join(ctx.component_names[:4])}\n"
        f"5. **Cache Layer** (Redis) serves frequently accessed data\n"
        f"6. **Database** ({ctx.database_type}) provides durable persistence\n\n"
        f"**How this relates to your question:**\n"
        f"The system handles `{question}` through delegation to **{ctx.component_names[0] if ctx.component_names else 'Core Service'}** "
        f"which communicates with **{ctx.database_type}** for state management and **Redis** for session caching.\n\n"
        f"**Key Observability Points:**\n"
        f"- Prometheus metrics at `/metrics`\n"
        f"- Jaeger distributed tracing via OpenTelemetry\n"
        f"- Structured logging to ELK stack\n\n"
        f"What specific aspect would you like me to elaborate on further?"
    )


# ── Intent Classification ────────────────────────────────────────────────────

INTENT_PATTERNS = {
    "architecture": ["why", "chose", "choose", "pattern", "topology", "reason", "decision", "design", "overview", "explain"],
    "database": ["database", "db", "sql", "postgres", "schema", "tables", "storage", "cache", "redis", "index"],
    "api": ["api", "endpoint", "rest", "swagger", "openapi", "route", "dispatch", "graphql"],
    "security": ["security", "vulnerability", "auth", "jwt", "compliance", "hipaa", "soc2", "audit", "encrypt"],
    "cost": ["cost", "aws", "budget", "price", "cloud", "terraform", "k8s", "kubernetes", "deploy"],
    "component": ["component", "service", "stack", "technology", "tech", "node", "building block"],
    "troubleshoot": ["bug", "not working", "crash", "error", "failed", "broken", "issue", "debug"],
    "greeting": ["hi", "hello", "hey", "hai", "good morning", "who are you", "help"],
    "thanks": ["fixed", "worked", "thanks", "thank you", "wow", "solved", "great", "awesome"],
}


def classify_intent(question: str) -> str:
    q = question.lower()
    for intent, keywords in INTENT_PATTERNS.items():
        if any(k in q for k in keywords):
            return intent
    return "general"


# ── Main Response Generator ──────────────────────────────────────────────────

def generate_contextual_response(
    question: str,
    analysis: Analysis,
    explanation_level: str = "brief"
) -> tuple[str, List[str]]:
    ctx = ArchitectureContext(analysis)
    intent = classify_intent(question)
    template = get_explanation_template(explanation_level)

    # Generate response based on explanation level
    if explanation_level == "detailed":
        response = generate_detailed_response(ctx, question, intent)
    elif explanation_level == "long":
        response = generate_long_response(ctx, question, intent)
    else:
        response = generate_brief_response(ctx, question, intent)

    # Generate follow-up suggestions based on intent
    suggestion_map = {
        "greeting": [
            "Why did you choose this architecture?",
            "Explain database design",
            "Show API endpoints",
        ],
        "architecture": [
            "What are the trade-offs?",
            "Show deployment config",
            "Explain security measures",
        ],
        "database": [
            "Show SQL DDL code",
            "How is caching configured?",
            "Explain indexing strategies",
        ],
        "api": [
            "How are tokens validated?",
            "Is there rate limiting?",
            "Show request payloads",
        ],
        "security": [
            "How to audit API keys?",
            "Can we add 2FA?",
            "Show compliance details",
        ],
        "cost": [
            "How to reduce costs?",
            "Can we run on Kubernetes?",
            "What if traffic doubles?",
        ],
        "component": [
            "Explain database schema",
            "Show API endpoints",
            "What about security?",
        ],
        "troubleshoot": [
            "How does failover work?",
            "Show security audit",
            "What are retry policies?",
        ],
        "thanks": [
            "Download report",
            "View Terraform IaC",
            "Ask another question",
        ],
        "general": [
            "Explain architecture",
            "Show component details",
            "What is the cost breakdown?",
        ],
    }

    suggestions = suggestion_map.get(intent, suggestion_map["general"])

    # Add level-aware suggestions
    if explanation_level == "brief":
        suggestions.append("Give me a detailed explanation")
    elif explanation_level == "long":
        suggestions.append("Show me the full technical details")

    return response, suggestions[:4]


# ── API Endpoints ────────────────────────────────────────────────────────────

@router.post("/{analysis_id}/send", response_model=ChatMessageResponse)
def send_chat_message(
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

    user_msg = {
        "role": "user",
        "content": payload.content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    ans_content, suggestions = generate_contextual_response(
        payload.content, analysis, payload.explanation_level or "brief"
    )

    bot_msg = {
        "role": "assistant",
        "content": ans_content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "explanation_level": payload.explanation_level or "brief",
    }

    msgs = list(chat.messages)
    msgs.append(user_msg)
    msgs.append(bot_msg)
    chat.messages = msgs

    db.commit()

    return ChatMessageResponse(
        response=ans_content,
        follow_up_suggestions=suggestions,
        conversation_length=len(msgs),
        explanation_level=payload.explanation_level or "brief",
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
