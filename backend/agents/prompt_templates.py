# backend/agents/prompt_templates.py
"""
Chained agent prompts.
======================
Every prompt is a STAGE in a dependency-ordered pipeline. Each stage receives
the already-produced parts of the canonical architecture model as context and
returns ONLY the JSON section it is responsible for. Stages never re-invent
facts that an earlier stage already decided (that is what caused the
"PostgreSQL vs MongoDB" contradictions in the old system).

Pipeline order (each stage depends only on stages above it):
    analyzer -> domain -> requirements -> architecture -> tech_selector
    -> database -> api -> deployment -> security -> performance
    -> reviewer -> final
"""

import json

from backend.agents.model import (
    as_text,
    deep_get,
    ensure_dict,
    ensure_list,
)


# ---------------------------------------------------------------------------
# Stage registry
# ---------------------------------------------------------------------------

def _fmt(obj) -> str:
    """Stable JSON formatting of context passed into prompts."""
    return json.dumps(obj, indent=1, default=str)


def _context(model: dict, *paths: str) -> dict:
    """Extract only the relevant prior context for a stage."""
    out = {}
    for path in paths:
        out[path] = deep_get(model, path)
    return out


# -- Analyzer ---------------------------------------------------------------

def build_analyzer_prompt(business_problem: str, architecture_tier: str,
                          scale_estimates: dict, constraints: list) -> tuple:
    system = """You are the Business Analyzer, the FIRST stage of an architecture pipeline.
Parse the business problem and extract ONLY what can be grounded in the text. Never invent throughput numbers — if the text does not state a rate, mark every numeric field null and record a labeled assumption.

Respond with ONLY this JSON object:
{
  "system_name": "short name of the system being built",
  "summary": "one-sentence restatement of the goal",
  "domain_hint": "best-guess domain, or null if unclear",
  "actors": ["role, e.g. 'Customer'"],
  "scale": {
    "avg_requests_per_second": number|null,
    "peak_requests_per_second": number|null,
    "expected_concurrency": number|null,
    "users": number|null,
    "assumptions": [{"label": "short label", "text": "what was assumed and why"}],
    "calculated_from": "the exact phrase the number came from"
  },
  "ambiguities": [
    {"question": "what is unclear", "suggested_assumption": "reasonable default", "confidence": "low|medium|high", "impact": "low|medium|high"}
  ],
  "constraints": ["explicit constraint stated in the problem"]
}"""

    user = (
        f"Business problem:\n{business_problem}\n\n"
        f"Architecture tier: {architecture_tier}\n"
        f"Scale estimates provided by the user: {_fmt(scale_estimates)}\n"
        f"Explicit constraints provided by the user: {_fmt(constraints)}"
    )
    return system, user


# -- Domain classifier ------------------------------------------------------

def build_domain_prompt(model: dict, business_problem: str) -> tuple:
    system = """You are the Domain Classifier, the SECOND stage.
Using the analyzer output, classify the domain and judge complexity. Be conservative: a CRUD tool with no stated scale must get a LOW complexity score and a monolithic architecture. Do not copy the analyzer's numeric scale verbatim if it was null; keep nulls null.

Respond with ONLY this JSON object:
{
  "domain": "General|E-Commerce|FinTech|Healthcare|Real-Time Chat|Cybersecurity|SaaS Platform",
  "complexity_score": 0-100,
  "complexity_rationale": "which factors raised/lowered the score",
  "building_blocks": ["domain concept, e.g. 'Order', 'Payment'"]
}"""

    user = (
        f"Business problem:\n{business_problem}\n\n"
        f"Analyzer output:\n{_fmt(_context(model, 'scale_estimates'))}"
    )
    return system, user


# -- Requirements -----------------------------------------------------------

def build_requirements_prompt(model: dict, business_problem: str) -> tuple:
    system = """You are the Requirements Engineer, the THIRD stage.
Derive requirements strictly from the analyzer + domain outputs. Every requirement must be traceable to the problem text. Where the problem is ambiguous, record it as an ambiguity object instead of guessing silently. Non-functional requirements must carry measurable targets where the problem allows.

Respond with ONLY this JSON object:
{
  "functional": [{"id": "FR-1", "description": "...", "priority": "high|medium|low", "source": "phrase in the problem"}],
  "non_functional": [{"id": "NFR-1", "category": "performance|availability|security|scalability|cost", "requirement": "...", "target": "measurable target or null", "priority": "high|medium|low"}],
  "constraints": ["..."],
  "assumptions": [{"label": "...", "text": "..."}],
  "ambiguities": [{"question": "...", "suggested_assumption": "...", "confidence": "low|medium|high", "impact": "low|medium|high"}],
  "business_rules": ["..."]
}"""

    user = (
        f"Business problem:\n{business_problem}\n\n"
        f"Analyzer + domain context:\n{_fmt(_context(model, 'domain', 'scale_estimates', 'requirements.actors'))}"
    )
    return system, user


# -- Architecture planner ---------------------------------------------------

def build_architecture_prompt(model: dict, business_problem: str) -> tuple:
    system = """You are the Principal Software Architect, the FOURTH stage.
Select the SIMPLEST architecture that satisfies the workload. Rules:
- complexity_score < 25  -> Monolithic Architecture
- complexity_score < 50  -> Modular Monolith
- complexity_score < 75  -> Microservices Architecture
- complexity_score >= 75 -> Event-Driven Microservices
Justify the choice against at least 2 rejected alternatives. Every component must be typed exactly as client|gateway|service|cache|queue|database|external|infrastructure. Mark cache/queue/database components with the SAME technology string used later by the Database stage. Only add a message queue or cache when the workload genuinely requires it (never for a low-scale CRUD app). Record every non-obvious decision as an ADR with rejected alternatives.

Respond with ONLY this JSON object:
{
  "system_type": "name of the system",
  "pattern": "one of the four patterns above",
  "justification": "why chosen vs the rejected alternatives",
  "components": [
    {"id": "svc-1", "name": "...", "type": "client|gateway|service|cache|queue|database|external|infrastructure",
     "technology": "...", "responsibility": "...", "internal_or_external": "internal|external",
     "dependencies": ["svc-2"], "scaling_strategy": "...", "failure_behavior": "...", "security_considerations": "...",
     "alternatives": ["..."], "reason": "..."}
  ],
  "relationships": [{"from": "component name", "to": "component name", "kind": "calls|persists|publishes|subscribes|reads", "description": "..."}],
  "decisions": [
    {"decision": "statement", "reason": "...", "alternatives": ["..."], "rejected_alternatives": ["..."],
     "rejected_reason": "...", "tradeoff": "...", "confidence": 0-100}
  ]
}"""

    user = (
        f"Business problem:\n{business_problem}\n\n"
        f"Domain + workload context:\n{_fmt(_context(model, 'domain', 'performance.workload', 'requirements.functional', 'requirements.non_functional', 'architecture_tier'))}"
    )
    return system, user


# -- Technology selector ----------------------------------------------------

def build_tech_selector_prompt(model: dict) -> tuple:
    system = """You are the Technology Selector, the FIFTH stage.
Choose technologies that are CONSISTENT with the components already selected (their `technology` fields are authoritative). For every choice, list at least one realistic rejected alternative and the reason. Do not change component technologies.

Respond with ONLY this JSON object:
{
  "technologies": [
    {"layer": "frontend|gateway|service|data|messaging|infra|observability",
     "choice": "...", "alternatives": ["..."], "rationale": "..."}
  ],
  "decisions": [
    {"decision": "...", "reason": "...", "alternatives": ["..."], "rejected_alternatives": ["..."],
     "rejected_reason": "...", "tradeoff": "...", "confidence": 0-100}
  ]
}"""

    user = f"Architecture context:\n{_fmt(_context(model, 'architecture.components', 'architecture.pattern', 'architecture.decisions'))}"
    return system, user


# -- Database ---------------------------------------------------------------

def build_database_prompt(model: dict) -> tuple:
    system = """You are the Database Architect, the SIXTH stage.
Design the schema for the components selected. The database_type MUST match the `technology` of the component of type `database` in the architecture — never contradict it. Provide real DDL-level column definitions with primary keys, indexes for hot query paths, and explicit transaction/sharding decisions tied to the workload.

Respond with ONLY this JSON object:
{
  "database_type": "must equal the architecture's database component technology",
  "justification": "...",
  "schemas": [
    {"table_name": "...", "columns": [{"name": "...", "type": "...", "constraints": "..."}],
     "primary_key": "...", "indexes": ["..."], "relationships": [{"to_table": "...", "kind": "1:1|1:N|N:M", "on": "..."}]}
  ],
  "indexing_strategies": ["..."],
  "transactions": "...",
  "sharding": "... or 'not required at this scale'",
  "migrations": "...",
  "caching_layer": "must reference the cache component if one exists, else 'no cache needed at this scale'"
}"""

    user = f"Architecture context:\n{_fmt(_context(model, 'architecture.components', 'performance.workload', 'requirements.non_functional'))}"
    return system, user


# -- API --------------------------------------------------------------------

def build_api_prompt(model: dict) -> tuple:
    system = """You are the API Spec Agent, the SEVENTH stage.
Design the API surface that the components expose. The authentication strategy MUST match the security section if already set. Every endpoint must be grounded in a functional requirement and a component responsibility.

Respond with ONLY this JSON object:
{
  "protocol": "REST HTTP / JSON | GraphQL | gRPC | WebSocket",
  "authentication_strategy": "JWT | OAuth2 | API keys | session | none",
  "endpoints": [
    {"method": "GET|POST|PUT|DELETE|PATCH", "path": "/...", "description": "...",
     "request_body": "...", "response_body": "...", "auth_required": true, "service": "component name"}
  ],
  "rate_limits": "...",
  "versioning": "...",
  "error_handling": "...",
  "idempotency": "..."
}"""

    user = f"Architecture + database context:\n{_fmt(_context(model, 'architecture.components', 'architecture.relationships', 'database.database_type', 'database.schemas', 'security.authentication_strategy'))}"
    return system, user


# -- Deployment -------------------------------------------------------------

def build_deployment_prompt(model: dict) -> tuple:
    system = """You are the DevOps & IaC Agent, the EIGHTH stage.
Generate deployment artifacts CONSISTENT with the pattern: a monolith must NOT get Kubernetes unless the workload justifies it. The orchestration field must be empty/null for single-node deployments. Provide real, plausible Terraform and Kubernetes snippets keyed to the chosen provider.

Respond with ONLY this JSON object:
{
  "provider": "AWS|GCP|Azure|Vercel|single VPS",
  "regions": ["..."],
  "infrastructure_as_code": "Terraform",
  "orchestration": "Kubernetes | Docker | single host (empty if none)",
  "environments": ["dev", "staging", "prod"],
  "terraform_sample": "```hcl ... ```",
  "kubernetes_manifest": "```yaml ... ``` or empty string if no orchestration",
  "scaling_policy": "...",
  "disaster_recovery": "...",
  "ci_cd": "..."
}"""

    user = f"Architecture context:\n{_fmt(_context(model, 'architecture.pattern', 'architecture.components', 'performance.workload'))}"
    return system, user


# -- Security ---------------------------------------------------------------

def build_security_prompt(model: dict) -> tuple:
    system = """You are the Lead Security Architect, the NINTH stage.
Audit the design as built. Threat-model every component that handles sensitive data, and map mitigations to actual components. Compliance must match the domain (e.g. payments -> PCI-DSS, healthcare -> HIPAA). The authentication strategy MUST match the API section's authentication_strategy.

Respond with ONLY this JSON object:
{
  "authentication_strategy": "must equal api.authentication_strategy",
  "authorization": "...",
  "data_protection": "encryption at rest / in transit per component",
  "vulnerability_mitigations": [{"vulnerability": "...", "mitigation": "...", "affected_component": "..."}],
  "compliance": "...",
  "scores": {"security": 0-100, "scalability": 0-100, "cost": 0-100},
  "threat_model": [{"threat": "...", "likelihood": "low|medium|high", "impact": "low|medium|high", "mitigation": "..."}]
}"""

    user = f"Architecture + API context:\n{_fmt(_context(model, 'architecture.components', 'api.authentication_strategy', 'api.endpoints', 'database.database_type', 'domain'))}"
    return system, user


# -- Performance ------------------------------------------------------------

def build_performance_prompt(model: dict) -> tuple:
    system = """You are the Performance Engineer, the TENTH stage.
This is a REAL analysis, not generic advice. Compute the estimated database write pressure from the workload and the schema. Identify the single most likely bottleneck and give a concrete recommendation. Cache/queue recommendations MUST reference existing components or explicitly state they are being introduced.

Respond with ONLY this JSON object:
{
  "latency_targets": {"p95_read_ms": number, "p95_write_ms": number},
  "database_pressure": "estimated writes/sec x transaction cost in plain language",
  "bottlenecks": [{"component": "...", "reason": "..."}],
  "cache_requirements": "..." or "not required at this scale",
  "queue_requirements": "..." or "not required at this scale",
  "scaling_requirements": "...",
  "recommendations": [
    {"recommendation": "...", "reason": "...", "affected_component": "...",
     "expected_benefit": "...", "tradeoff": "..."}
  ]
}"""

    user = f"Workload + architecture context:\n{_fmt(_context(model, 'performance.workload', 'architecture.components', 'architecture.pattern', 'database.database_type', 'database.indexing_strategies'))}"
    return system, user


# -- Reviewer ---------------------------------------------------------------

def build_reviewer_prompt(model: dict, validation: list) -> tuple:
    system = """You are the Architecture Reviewer, the ELEVENTH stage. You are NOT a rubber stamp.
Challenge the design against the stated workload. Take a point off for every validation issue you are given, and explicitly state what must change to approve. If the workload is missing or contradicts the pattern choice, demand a change.

Respond with ONLY this JSON object:
{
  "overall_score": 0-100,
  "categories": {"correctness": 0-100, "scalability": 0-100, "security": 0-100, "cost": 0-100, "clarity": 0-100},
  "critical_issues": ["..."],
  "warnings": ["..."],
  "recommendations": ["..."],
  "missing_information": ["..."]
}"""

    user = (
        f"Full architecture model:\n{_fmt(model)}\n\n"
        f"Automated cross-tab validation issues:\n{_fmt(validation)}"
    )
    return system, user


# -- Final synthesis --------------------------------------------------------

def build_final_prompt(model: dict) -> tuple:
    system = """You are the final synthesis stage. Produce the overview narrative and the explanation modes. Everything you say must be TRUE of the model you are given — cite component names and decisions from it. Do not add new architecture facts.

Respond with ONLY this JSON object:
{
  "overview": "4-6 sentence executive overview grounded in the model",
  "explanation_modes": {
    "story": "...", "brief": "...", "long": "...", "detailed": "...",
    "terms": [{"term": "...", "definition": "..."}],
    "analogies": [{"concept": "...", "analogy": "..."}]
  }
}"""

    user = f"Final architecture model:\n{_fmt(model)}"
    return system, user


# ---------------------------------------------------------------------------
# Pipeline registry — order matters (dependency-ordered).
# ---------------------------------------------------------------------------

PIPELINE_STEPS = [
    ("analyzer", "Business Analyzer", "Parsing scope, actors and scale signals from the problem text.",
     build_analyzer_prompt),
    ("domain", "Domain Classifier", "Classifying domain and judging complexity from real signals.",
     build_domain_prompt),
    ("requirements", "Requirements Extractor", "Deriving traceable functional and non-functional requirements.",
     build_requirements_prompt),
    ("architecture", "Architecture Planner", "Selecting the simplest pattern that satisfies the workload.",
     build_architecture_prompt),
    ("tech_selector", "Technology Selector", "Choosing stacks with explicit rationale and trade-offs.",
     build_tech_selector_prompt),
    ("database", "Database Architect", "Designing the schema to match the chosen components exactly.",
     build_database_prompt),
    ("api", "API Spec Agent", "Designing the API surface grounded in components and requirements.",
     build_api_prompt),
    ("deployment", "DevOps & IaC Agent", "Generating deployment artifacts consistent with the pattern.",
     build_deployment_prompt),
    ("security", "Security Auditor", "Threat-modelling the design and mapping mitigations to components.",
     build_security_prompt),
    ("performance", "Performance Engineer", "Computing real load analysis from the workload.",
     build_performance_prompt),
    ("reviewer", "Architecture Reviewer", "Challenging the design against the workload and validation.",
     build_reviewer_prompt),
    ("final", "Final Synthesis", "Writing the overview and explanation modes from the model.",
     build_final_prompt),
]


def build_stage_prompt(key: str, model: dict, business_problem: str,
                       architecture_tier: str, scale_estimates: dict,
                       constraints: list, validation: list) -> tuple:
    """Build (system, user) for a pipeline stage, passing prior model context."""
    for stage_key, _title, _desc, builder in PIPELINE_STEPS:
        if stage_key == key:
            if key == "analyzer":
                return builder(business_problem, architecture_tier, scale_estimates, constraints)
            if key == "domain":
                return builder(model, business_problem)
            if key == "requirements":
                return builder(model, business_problem)
            if key == "architecture":
                return builder(model, business_problem)
            if key == "reviewer":
                return builder(model, validation)
            return builder(model)
    raise ValueError(f"Unknown pipeline stage: {key}")
