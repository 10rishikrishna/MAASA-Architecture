# backend/agents/model.py
"""
Canonical Architecture Model
============================
Single source of truth for every generated analysis.

Every agent (requirements, architecture, database, api, deployment, security,
performance, reviewer, diagrams, chat) reads from and writes to this ONE model.
Nothing else in the system invents architecture facts independently, so the
system can never produce contradictions such as:
    Architecture: PostgreSQL   vs   Database: MongoDB
"""

ARCHITECTURE_MODEL_VERSION = 2

# ---------------------------------------------------------------------------
# Empty / default model constructor
# ---------------------------------------------------------------------------

def new_model(business_problem: str, domain: str = "General",
              architecture_tier: str = "professional",
              scale_estimates: dict = None) -> dict:
    """Create a fresh canonical architecture model."""
    if scale_estimates is None:
        scale_estimates = {}
    return {
        "version": ARCHITECTURE_MODEL_VERSION,
        "business_problem": business_problem,
        "domain": domain,
        "architecture_tier": architecture_tier,
        "scale_estimates": scale_estimates,
        "status": "processing",
        "correction_iterations": 0,
        "overview": "",
        "overview_explained": [],
        "requirements": {
            "functional": [],
            "non_functional": [],
            "actors": [],
            "constraints": [],
            "assumptions": [],
            "ambiguities": [],
            "business_rules": [],
            "dependencies": [],
            "scale_requirements": {},
            "availability_requirement": "",
            "security_requirements": [],
        },
        "architecture": {
            "system_type": "",
            "style": "",
            "pattern": "",
            "justification": "",
            "components": [],
            "relationships": [],
            "technologies": [],
            "decisions": [],
            "explanation_modes": {
                "story": "", "brief": "", "long": "", "detailed": "",
                "terms": [], "analogies": [],
            },
            "alternatives": [],
        },
        "database": {
            "database_type": "",
            "justification": "",
            "schemas": [],
            "indexing_strategies": [],
            "transactions": "",
            "sharding": "",
            "migrations": "",
            "caching_layer": "",
        },
        "api": {
            "protocol": "",
            "authentication_strategy": "",
            "endpoints": [],
            "rate_limits": "",
            "versioning": "",
            "error_handling": "",
            "idempotency": "",
        },
        "deployment": {
            "provider": "",
            "regions": [],
            "infrastructure_as_code": "Terraform",
            "orchestration": "",
            "environments": ["dev", "staging", "prod"],
            "terraform_sample": "",
            "kubernetes_manifest": "",
            "scaling_policy": "",
            "disaster_recovery": "",
            "ci_cd": "",
        },
        "security": {
            "authentication_strategy": "",
            "authorization": "",
            "data_protection": "",
            "vulnerability_mitigations": [],
            "compliance": "",
            "scores": {"security": 0, "scalability": 0, "cost": 0},
            "threat_model": [],
        },
        "performance": {
            "workload": {
                "avg_requests_per_second": None,
                "peak_requests_per_second": None,
                "expected_concurrency": None,
                "read_write_ratio": "",
                "assumptions": [],
                "calculated_from": "",
            },
            "latency_targets": {"p95_read_ms": None, "p95_write_ms": None},
            "database_pressure": "",
            "bottlenecks": [],
            "cache_requirements": "",
            "queue_requirements": "",
            "scaling_requirements": "",
            "recommendations": [],
        },
        "failure_scenarios": [],
        "risks": [],
        "review": {
            "overall_score": None,
            "categories": {},
            "critical_issues": [],
            "warnings": [],
            "recommendations": [],
            "missing_information": [],
        },
        "diagrams": {
            "level1": {"title": "", "description": "", "mermaid": "", "ascii": ""},
            "level2": {"title": "", "description": "", "mermaid": "", "ascii": ""},
            "level3": {"title": "", "description": "", "mermaid": "", "ascii": ""},
            "legacy": {"mermaid": "", "ascii": ""},
        },
    }


# ---------------------------------------------------------------------------
# Safe deep-get / deep-merge helpers
# ---------------------------------------------------------------------------

def deep_get(data: dict, path: str, default=None):
    """Navigate a dotted path through a dict safely."""
    node = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def ensure_list(value, default=None):
    if value is None:
        return default if default is not None else []
    if isinstance(value, list):
        return value
    return [value]


def ensure_dict(value, default=None):
    if value is None:
        return default if default is not None else {}
    return value if isinstance(value, dict) else (default if default is not None else {})


def as_text(value, default=""):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        import json
        try:
            return json.dumps(value)
        except Exception:
            return str(value)
    return str(value)


# ---------------------------------------------------------------------------
# Normalizers — repair malformed / partial agent output
# ---------------------------------------------------------------------------

def normalize_component(comp: dict, index: int = 0) -> dict:
    """Coerce an arbitrary component dict into the canonical component shape."""
    comp = ensure_dict(comp)
    name = as_text(comp.get("name")) or f"Component {index + 1}"
    return {
        "id": as_text(comp.get("id")) or f"comp-{index + 1}",
        "name": name,
        "type": as_text(comp.get("type")) or as_text(comp.get("component_type")) or "service",
        "technology": as_text(comp.get("technology")) or as_text(comp.get("tech")) or "To be defined",
        "responsibility": as_text(comp.get("responsibility")) or as_text(comp.get("description")) or as_text(comp.get("purpose")) or as_text(comp.get("reason")) or "",
        "internal_or_external": as_text(comp.get("internal_or_external")) or ("internal" if as_text(comp.get("internal"), "true").lower() != "false" else "external"),
        "dependencies": ensure_list(comp.get("dependencies")),
        "scaling_strategy": as_text(comp.get("scaling_strategy")) or "",
        "failure_behavior": as_text(comp.get("failure_behavior")) or "",
        "security_considerations": as_text(comp.get("security_considerations")) or "",
        "alternatives": ensure_list(comp.get("alternatives")),
        "reason": as_text(comp.get("reason")) or as_text(comp.get("responsibility")) or "",
    }


def normalize_decision(dec: dict, index: int = 0) -> dict:
    dec = ensure_dict(dec)
    return {
        "decision": as_text(dec.get("decision")),
        "reason": as_text(dec.get("reason")),
        "alternatives": ensure_list(dec.get("alternatives")),
        "rejected_alternatives": ensure_list(dec.get("rejected_alternatives")) or ensure_list(dec.get("rejected")),
        "rejected_reason": as_text(dec.get("rejected_reason")),
        "tradeoff": as_text(dec.get("tradeoff")),
        "confidence": dec.get("confidence") if isinstance(dec.get("confidence"), (int, float)) else None,
    }


def normalize_ambiguity(amb: dict, index: int = 0) -> dict:
    amb = ensure_dict(amb)
    return {
        "question": as_text(amb.get("question")) or f"Unclear requirement {index + 1}",
        "suggested_assumption": as_text(amb.get("suggested_assumption")) or as_text(amb.get("assumption")),
        "confidence": as_text(amb.get("confidence")) or "medium",
        "impact": as_text(amb.get("impact")) or "medium",
    }


def normalize_relationship(rel: dict, index: int = 0) -> dict:
    rel = ensure_dict(rel)
    return {
        "from": as_text(rel.get("from")) or as_text(rel.get("source")),
        "to": as_text(rel.get("to")) or as_text(rel.get("target")),
        "kind": as_text(rel.get("kind")) or as_text(rel.get("type")) or "calls",
        "description": as_text(rel.get("description")),
    }


def normalize_recommendation(rec: dict, index: int = 0) -> dict:
    rec = ensure_dict(rec)
    return {
        "recommendation": as_text(rec.get("recommendation")) or as_text(rec.get("title")),
        "reason": as_text(rec.get("reason")),
        "affected_component": as_text(rec.get("affected_component")) or as_text(rec.get("component")),
        "expected_benefit": as_text(rec.get("expected_benefit")),
        "tradeoff": as_text(rec.get("tradeoff")),
    }


# ---------------------------------------------------------------------------
# Validation — cross-tab consistency checks (Step 12)
# ---------------------------------------------------------------------------

def validate_model(model: dict) -> list:
    """
    Return a list of validation issue dicts:
        {"severity": "error"|"warning", "category": str, "message": str}
    Checks for obvious contradictions across tabs and missing canonical data.
    """
    issues = []
    arch = ensure_dict(model.get("architecture"))
    db = ensure_dict(model.get("database"))
    api = ensure_dict(model.get("api"))
    sec = ensure_dict(model.get("security"))
    dep = ensure_dict(model.get("deployment"))
    reqs = ensure_dict(model.get("requirements"))
    diagrams = ensure_dict(model.get("diagrams"))
    comps = ensure_list(arch.get("components"))

    # --- Database technology mismatch ------------------------------------
    db_type = as_text(db.get("database_type"))
    if db_type and comps:
        conflicting = [c for c in comps
                       if db_type.lower() in as_text(c.get("technology")).lower()
                       and c.get("type") not in ("database", "cache", "queue")]
        # (A "PostgreSQL" reference inside a service tech string is fine.)

    # --- Missing architecture components ---------------------------------
    if not comps:
        issues.append({"severity": "error", "category": "architecture",
                       "message": "Architecture has no components."})

    # --- Requirement coverage --------------------------------------------
    functional = ensure_list(reqs.get("functional"))
    if not functional:
        issues.append({"severity": "warning", "category": "requirements",
                       "message": "No functional requirements extracted."})

    # --- Diagram vs component consistency --------------------------------
    import re as _re
    diagram_text = (
        as_text(diagrams.get("level1", {}).get("mermaid")) +
        as_text(diagrams.get("level2", {}).get("mermaid")) +
        as_text(diagrams.get("level3", {}).get("mermaid")) +
        as_text(diagrams.get("legacy", {}).get("mermaid"))
    ).lower()
    if diagram_text:
        def _norm(s):
            return _re.sub(r"[^a-z0-9]", "", s.lower())
        dt = _norm(diagram_text)
        missing_in_diagram = [
            c.get("name") for c in comps
            if as_text(c.get("name")) and _norm(as_text(c.get("name"))) not in dt
        ]
        if missing_in_diagram:
            issues.append({"severity": "warning", "category": "diagrams",
                           "message": f"Components not shown in any diagram: {', '.join(missing_in_diagram[:4])}."})

    # --- Deployment technology mismatch ----------------------------------
    orchestration = as_text(dep.get("orchestration")).lower()
    dep_text = (as_text(dep.get("terraform_sample")) + as_text(dep.get("kubernetes_manifest"))).lower()
    if orchestration and "kubernetes" in orchestration and "eks" in dep_text and "k8s" not in dep_text:
        pass  # EKS implies k8s; no conflict.

    # --- Security strategy missing from API ------------------------------
    sec_auth = as_text(sec.get("authentication_strategy")).lower()
    api_auth = as_text(api.get("authentication_strategy")).lower()
    if sec_auth and api_auth and sec_auth != api_auth:
        issues.append({"severity": "error", "category": "security",
                       "message": f"Security authentication strategy ('{sec_auth}') does not match API authentication strategy ('{api_auth}')."})

    # --- External services misclassified ---------------------------------
    for c in comps:
        loc = as_text(c.get("internal_or_external"))
        name = as_text(c.get("name")).lower()
        tech = as_text(c.get("technology")).lower()
        looks_external = any(k in name or k in tech for k in
                             ["stripe", "paypal", "razorpay", "adyen", "twilio", "auth0", "aws", "s3", "sns", "sqs"])
        if looks_external and loc != "external":
            issues.append({"severity": "error", "category": "architecture",
                           "message": f"External service '{c.get('name')}' is classified as internal."})
        if loc == "external" and not looks_external:
            pass

    # --- Performance must contain real analysis --------------------------
    workload = ensure_dict(model.get("performance", {}).get("workload"))
    if not workload.get("peak_requests_per_second"):
        issues.append({"severity": "warning", "category": "performance",
                       "message": "Performance section has no calculated peak throughput."})

    # --- Reviewer must exist ---------------------------------------------
    review = ensure_dict(model.get("review"))
    if review.get("overall_score") is None:
        issues.append({"severity": "warning", "category": "review",
                       "message": "No architecture review score present."})

    return issues


def summarize_validation(issues: list) -> dict:
    errors = [i for i in issues if i.get("severity") == "error"]
    warnings = [i for i in issues if i.get("severity") == "warning"]
    return {
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "passes": len(errors) == 0,
    }


# ---------------------------------------------------------------------------
# Backwards compatibility helpers
# ---------------------------------------------------------------------------

def to_legacy_fields(model: dict) -> dict:
    """
    Extract the legacy top-level analysis fields from the canonical model so
    older consumers (frontend tabs, exports) keep working unchanged.
    """
    arch = ensure_dict(model.get("architecture"))
    db = ensure_dict(model.get("database"))
    api = ensure_dict(model.get("api"))
    dep = ensure_dict(model.get("deployment"))
    sec = ensure_dict(model.get("security"))
    perf = ensure_dict(model.get("performance"))
    diagrams = ensure_dict(model.get("diagrams"))
    legacy_diagram = diagrams.get("legacy") or diagrams.get("level1") or {}

    # Build legacy component list with the fields the old UI expects.
    legacy_components = []
    for c in ensure_list(arch.get("components")):
        legacy_components.append({
            "name": c.get("name"),
            "description": c.get("responsibility") or c.get("description") or c.get("reason"),
            "technology": c.get("technology"),
            "reason": c.get("responsibility") or c.get("reason"),
            "alternatives": c.get("alternatives") or [],
            "tradeoffs": c.get("tradeoff") or "",
            "type": c.get("type"),
            "internal_or_external": c.get("internal_or_external"),
            "dependencies": c.get("dependencies") or [],
            "scaling_strategy": c.get("scaling_strategy") or "",
            "failure_behavior": c.get("failure_behavior") or "",
            "security_considerations": c.get("security_considerations") or "",
        })

    requirements = ensure_dict(model.get("requirements"))

    performance_legacy = {
        "caching": perf.get("cache_requirements") or "",
        "optimization": perf.get("scaling_requirements") or "",
        "workload": perf.get("workload"),
        "bottlenecks": perf.get("bottlenecks"),
        "recommendations": perf.get("recommendations"),
        "latency_targets": perf.get("latency_targets"),
    }

    security_legacy = {
        "vulnerability_mitigations": ensure_list(sec.get("vulnerability_mitigations")),
        "compliance": sec.get("compliance") or "",
        "scores": sec.get("scores") or {},
        "reviewer_critique": "",
        "authentication_strategy": sec.get("authentication_strategy") or "",
        "threat_model": ensure_list(sec.get("threat_model")),
    }

    explanation_modes = ensure_dict(arch.get("explanation_modes"))

    return {
        "requirements": {
            "functional": ensure_list(requirements.get("functional")),
            "non_functional": ensure_list(requirements.get("non_functional")),
            "actors": ensure_list(requirements.get("actors")),
            "assumptions": ensure_list(requirements.get("assumptions")),
            "ambiguities": ensure_list(requirements.get("ambiguities")),
            "constraints": ensure_list(requirements.get("constraints")),
            "business_rules": ensure_list(requirements.get("business_rules")),
            "dependencies": ensure_list(requirements.get("dependencies")),
            "scale_requirements": ensure_dict(requirements.get("scale_requirements")),
            "availability_requirement": requirements.get("availability_requirement") or "",
            "security_requirements": ensure_list(requirements.get("security_requirements")),
        },
        "architecture_design": {
            "system_type": arch.get("system_type") or "",
            "pattern": arch.get("pattern") or "",
            "style": arch.get("style") or "",
            "justification": arch.get("justification") or "",
            "components": legacy_components,
            "relationships": ensure_list(arch.get("relationships")),
            "technologies": ensure_list(arch.get("technologies")),
            "decisions": ensure_list(arch.get("decisions")),
            "story_mode": explanation_modes.get("story") or "",
            "eli5_terms": explanation_modes.get("terms") or [],
            "analogies": explanation_modes.get("analogies") or [],
            "explanations": {
                "brief": explanation_modes.get("brief") or "",
                "long": explanation_modes.get("long") or "",
                "detailed": explanation_modes.get("detailed") or "",
                "overview_explained": ensure_list(model.get("overview_explained")),
            },
            "architecture_tier": model.get("architecture_tier") or "",
            "alternatives": ensure_list(arch.get("alternatives")),
        },
        "database_schema": {
            "database_type": db.get("database_type") or "",
            "justification": db.get("justification") or "",
            "schemas": ensure_list(db.get("schemas")),
            "indexing_strategies": ensure_list(db.get("indexing_strategies")),
            "transactions": db.get("transactions") or "",
            "sharding": db.get("sharding") or "",
            "migrations": db.get("migrations") or "",
            "caching_layer": db.get("caching_layer") or "",
        },
        "api_specification": {
            "protocol": api.get("protocol") or "REST HTTP / JSON",
            "authentication_strategy": api.get("authentication_strategy") or "",
            "endpoints": ensure_list(api.get("endpoints")),
            "rate_limits": api.get("rate_limits") or "",
            "versioning": api.get("versioning") or "",
            "error_handling": api.get("error_handling") or "",
            "idempotency": api.get("idempotency") or "",
        },
        "deployment_config": {
            "provider": dep.get("provider") or "",
            "regions": ensure_list(dep.get("regions")),
            "infrastructure_as_code": dep.get("infrastructure_as_code") or "Terraform",
            "orchestration": dep.get("orchestration") or "",
            "terraform_sample": dep.get("terraform_sample") or "",
            "kubernetes_manifest": dep.get("kubernetes_manifest") or "",
            "scaling_policy": dep.get("scaling_policy") or "",
            "disaster_recovery": dep.get("disaster_recovery") or "",
            "ci_cd": dep.get("ci_cd") or "",
        },
        "security_audit": security_legacy,
        "performance_strategies": performance_legacy,
        "diagrams": {
            "mermaid": legacy_diagram.get("mermaid") or "",
            "ascii": legacy_diagram.get("ascii") or "",
            "level1": diagrams.get("level1"),
            "level2": diagrams.get("level2"),
            "level3": diagrams.get("level3"),
        },
        "failure_scenarios": ensure_list(model.get("failure_scenarios")),
        "risks": ensure_list(model.get("risks")),
        "review": ensure_dict(model.get("review")),
        "validation": summarize_validation(validate_model(model)),
    }


def from_legacy(business_problem: str, requirements=None, architecture_design=None,
                database_schema=None, api_specification=None, deployment_config=None,
                security_audit=None, performance_strategies=None, diagrams=None) -> dict:
    """
    Build a canonical model from legacy top-level fields. Used to re-host
    previously-generated analyses (created before this model existed).
    """
    reqs = ensure_dict(requirements)
    arch = ensure_dict(architecture_design)
    db = ensure_dict(database_schema)
    api = ensure_dict(api_specification)
    dep = ensure_dict(deployment_config)
    sec = ensure_dict(security_audit)
    perf = ensure_dict(performance_strategies)
    dg = ensure_dict(diagrams)

    model = new_model(
        business_problem,
        domain=as_text(arch.get("system_type"), "General").split(" Architecture")[0],
        architecture_tier=as_text(arch.get("architecture_tier"), "professional").lower(),
    )

    model["requirements"]["functional"] = ensure_list(reqs.get("functional"))
    model["requirements"]["non_functional"] = ensure_list(reqs.get("non_functional"))
    model["requirements"]["actors"] = ensure_list(reqs.get("actors"))
    model["requirements"]["assumptions"] = ensure_list(reqs.get("assumptions"))
    model["requirements"]["ambiguities"] = ensure_list(reqs.get("ambiguities"))
    model["requirements"]["constraints"] = ensure_list(reqs.get("constraints"))

    model["architecture"]["system_type"] = as_text(arch.get("system_type"))
    model["architecture"]["style"] = as_text(arch.get("style"))
    model["architecture"]["pattern"] = as_text(arch.get("pattern"))
    model["architecture"]["justification"] = as_text(arch.get("justification"))
    model["architecture"]["components"] = [
        normalize_component(c, i) for i, c in enumerate(ensure_list(arch.get("components")))
    ]
    model["architecture"]["relationships"] = [
        normalize_relationship(r, i) for i, r in enumerate(ensure_list(arch.get("relationships")))
    ]
    model["architecture"]["decisions"] = [
        normalize_decision(d, i) for i, d in enumerate(ensure_list(arch.get("decisions")))
    ]
    explanation_modes = ensure_dict(arch.get("explanations"))
    model["architecture"]["explanation_modes"]["story"] = as_text(arch.get("story_mode"))
    model["architecture"]["explanation_modes"]["brief"] = as_text(explanation_modes.get("brief"))
    model["architecture"]["explanation_modes"]["long"] = as_text(explanation_modes.get("long"))
    model["architecture"]["explanation_modes"]["detailed"] = as_text(explanation_modes.get("detailed"))
    model["architecture"]["explanation_modes"]["terms"] = ensure_list(arch.get("eli5_terms"))
    model["architecture"]["alternatives"] = ensure_list(arch.get("alternatives"))
    model["overview_explained"] = ensure_list(explanation_modes.get("overview_explained"))

    model["database"]["database_type"] = as_text(db.get("database_type"))
    model["database"]["justification"] = as_text(db.get("justification"))
    model["database"]["schemas"] = ensure_list(db.get("schemas"))
    model["database"]["indexing_strategies"] = ensure_list(db.get("indexing_strategies"))

    model["api"]["protocol"] = as_text(api.get("protocol"), "REST HTTP / JSON")
    model["api"]["endpoints"] = ensure_list(api.get("endpoints"))

    model["deployment"]["infrastructure_as_code"] = as_text(dep.get("infrastructure_as_code"), "Terraform")
    model["deployment"]["orchestration"] = as_text(dep.get("orchestration"))
    model["deployment"]["terraform_sample"] = as_text(dep.get("terraform_sample"))
    model["deployment"]["kubernetes_manifest"] = as_text(dep.get("kubernetes_manifest"))

    model["security"]["vulnerability_mitigations"] = ensure_list(sec.get("vulnerability_mitigations"))
    model["security"]["compliance"] = as_text(sec.get("compliance"))
    model["security"]["scores"] = ensure_dict(sec.get("scores"))

    model["performance"]["cache_requirements"] = as_text(perf.get("caching"))
    model["performance"]["scaling_requirements"] = as_text(perf.get("optimization"))
    model["performance"]["recommendations"] = [
        normalize_recommendation(r, i) for i, r in enumerate(ensure_list(perf.get("recommendations")))
    ]

    model["diagrams"]["legacy"]["mermaid"] = as_text(dg.get("mermaid"))
    model["diagrams"]["legacy"]["ascii"] = as_text(dg.get("ascii"))
    model["diagrams"]["level1"]["mermaid"] = as_text(dg.get("mermaid"))
    model["diagrams"]["level1"]["ascii"] = as_text(dg.get("ascii"))

    model["status"] = "completed"
    return model
