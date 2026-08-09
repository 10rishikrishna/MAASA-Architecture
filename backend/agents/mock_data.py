# backend/agents/mock_data.py
"""
Mosaic Studio - Procedural Architecture Synthesizer
====================================================
Builds a *canonical architecture model* from a business problem by reasoning
about scale, domain and constraints. This is the fallback engine used when no
LLM API key is configured. It is deliberately NOT a set of fixed templates:

  * Architecture pattern is derived from an explicit complexity/workload score,
    so a simple CRUD app is never forced into microservices + Kafka + K8s.
  * Performance numbers are *calculated* from the workload (labeled as
    calculated vs assumed), not copy-pasted advice.
  * Diagrams are generated from the canonical model with rotating layouts and
    color palettes across three detail levels.
  * Every important choice carries an ADR-style decision record.
"""
import json
import hashlib
import re

from backend.agents.model import (
    new_model, ensure_list, ensure_dict, as_text, validate_model,
)

# ---------------------------------------------------------------------------
# Numeric / scale parsing
# ---------------------------------------------------------------------------

_NUMBER_PATTERN = re.compile(r"([\d][\d,]*(?:\.\d+)?)\s*(million|billion|k|thousand|m|k)?", re.IGNORECASE)

_RATE_PATTERNS = [
    # e.g. "100,000 orders/hour", "5000 requests per second", "1M users"
    re.compile(r"([\d][\d,]*(?:\.\d+)?)\s*(million|m|billion|thousand|k)?\s*(orders|requests|users|messages|transactions|students|patients|events|hits|searches|payments|calls)\s*(?:per|/)\s*(hour|hr|day|second|sec|minute|min|month)", re.IGNORECASE),
]

# Business events imply several HTTP requests each (browse, validate, mutate, confirm...).
_EVENT_REQUEST_FACTOR = 8

_USER_PATTERNS = [
    re.compile(r"([\d][\d,]*(?:\.\d+)?)\s*(million|billion|thousand|k)?\s*(concurrent\s+)?users", re.IGNORECASE),
    re.compile(r"([\d][\d,]*(?:\.\d+)?)\s*(million|billion|thousand|k)?\s*(concurrent\s+)?(customers|people|students|patients)", re.IGNORECASE),
]


def parse_number(text: str):
    if not text:
        return None
    s = str(text).strip().replace(",", "").lower()
    mult = 1.0
    for suffix, factor in (("million", 1e6), ("billion", 1e9), ("thousand", 1e3)):
        if s.endswith(suffix):
            mult = factor
            s = s[: -len(suffix)].strip()
            break
    for suffix, factor in (("m", 1e6), ("k", 1e3)):
        if s.endswith(suffix) and s[:-1].replace(".", "").isdigit():
            mult = factor
            s = s[:-1].strip()
            break
    if not s.replace(".", "").isdigit():
        return None
    return int(float(s) * mult)


def _apply_scale(amount, unit):
    """Combine a number with an optional million/billion/thousand/k unit."""
    unit = (unit or "").lower()
    factors = {"million": 1e6, "billion": 1e9, "thousand": 1e3, "m": 1e6, "k": 1e3}
    if amount is None:
        return None
    return int(amount * factors.get(unit, 1))


def _find_rate(business_problem: str):
    """Look for rate-like phrases in the problem text, e.g. '100k orders/hour'."""
    for pat in _RATE_PATTERNS:
        m = pat.search(business_problem.lower())
        if m:
            amount = _apply_scale(parse_number(m.group(1)), m.group(2))
            unit = m.group(4).lower()
            noun = m.group(3).lower()
            if amount is None:
                continue
            business_events = ("orders", "transactions", "payments", "events", "searches", "calls", "messages")
            kind = "business_event" if noun in business_events else "request"
            if unit in ("second", "sec"):
                return {"type": "per_second", "value": amount, "kind": kind, "event": noun}
            if unit in ("minute", "min"):
                return {"type": "per_second", "value": amount / 60.0, "kind": kind, "event": noun}
            if unit in ("hour", "hr"):
                return {"type": "per_second", "value": amount / 3600.0, "kind": kind, "event": noun}
            if unit in ("day",):
                return {"type": "per_second", "value": amount / 86400.0, "kind": kind, "event": noun}
            if unit in ("month",):
                return {"type": "per_second", "value": amount / (86400.0 * 30), "kind": kind, "event": noun}
    return None


def _find_users(business_problem: str):
    for pat in _USER_PATTERNS:
        m = pat.search(business_problem.lower())
        if m:
            return _apply_scale(parse_number(m.group(1)), m.group(2))
    return None


def extract_workload(business_problem: str, scale_estimates: dict) -> dict:
    """Derive a workload profile from the form + text. Labels every figure."""
    scale_estimates = ensure_dict(scale_estimates)
    assumptions = []
    source = "estimate"

    users = parse_number(scale_estimates.get("users")) or _find_users(business_problem)
    daily_requests = parse_number(scale_estimates.get("daily_requests"))
    rate = _find_rate(business_problem)

    avg_rps = None
    if rate and rate["type"] == "per_second":
        avg_rps = rate["value"]
        if rate["kind"] == "business_event":
            avg_rps *= _EVENT_REQUEST_FACTOR
            assumptions.append(
                f"The stated {rate['event']}/time figure is a business-event rate; each event involves "
                f"~{_EVENT_REQUEST_FACTOR} API requests (browse, validate, mutate, confirm), so it was "
                "scaled up to a request rate."
            )
        else:
            source = "parsed from problem text"
            assumptions.append("Hourly/rate figures in the problem text were converted to requests/second.")
    elif daily_requests:
        avg_rps = daily_requests / 86400.0
        source = "daily request volume from scale form"
        assumptions.append("Requests are evenly distributed; avg = daily_requests / 86400.")

    if avg_rps is None:
        if users and users >= 100000:
            avg_rps = users * 0.002   # 2% concurrent users, ~1 request per 10s each
            assumptions.append("No throughput given: estimated avg = 2% of users concurrently active, ~1 request each per 10 seconds.")
        else:
            avg_rps = 2.0
            assumptions.append("No throughput given: assumed a modest baseline of 2 requests/second.")

    peak_multiplier = 3.0
    peak_rps = avg_rps * peak_multiplier
    assumptions.append(f"Peak = average x {peak_multiplier:g} (burst multiplier assumption).")

    avg_response_s = 0.25
    concurrency = peak_rps * avg_response_s
    assumptions.append(f"Concurrency = peak x avg response time ({avg_response_s}s assumed).")

    return {
        "users": users,
        "daily_requests": daily_requests,
        "avg_requests_per_second": round(avg_rps, 2),
        "peak_requests_per_second": round(peak_rps, 2),
        "peak_multiplier": peak_multiplier,
        "expected_concurrency": round(concurrency, 1),
        "avg_response_time_s": avg_response_s,
        "source": source,
        "assumptions": assumptions,
        "budget_monthly": scale_estimates.get("budget", ""),
    }


def compute_complexity(workload: dict, domain: str, constraints: list, architecture_tier: str) -> int:
    """0-100 complexity score driving the architecture pattern choice."""
    peak = workload.get("peak_requests_per_second") or 0
    users = workload.get("users") or 0

    if peak < 5:
        throughput = 5
    elif peak < 50:
        throughput = 15
    elif peak < 500:
        throughput = 25
    elif peak < 5000:
        throughput = 40
    else:
        throughput = 50

    if users >= 1_000_000:
        user_scale = 15
    elif users >= 100_000:
        user_scale = 10
    elif users >= 10_000:
        user_scale = 5
    else:
        user_scale = 0

    domain_scores = {
        "Cybersecurity": 25, "FinTech": 25, "Healthcare": 20,
        "Real-Time Chat": 20, "E-Commerce": 15, "SaaS Platform": 8,
        "General": 2,
    }
    domain_factor = domain_scores.get(domain, 2)

    constraint_factor = 0
    for c in (constraints or []):
        cl = str(c).lower()
        if any(k in cl for k in ["compliance", "hipaa", "gdpr", "soc2", "pci", "multi-region", "global", "99.99", "high availability"]):
            constraint_factor += 4
        elif any(k in cl for k in ["low latency", "real-time", "realtime"]):
            constraint_factor += 3

    return min(100, throughput + user_scale + domain_factor + constraint_factor)


def select_pattern(complexity: int, domain: str) -> tuple:
    """
    Returns (pattern, style, justification, components_flavor).
    Pattern is driven by complexity so simple apps never get over-engineered.
    """
    if complexity < 25:
        return (
            "Monolithic Architecture",
            "monolith",
            (
                f"Complexity score is {complexity}/100 — traffic is low and the domain "
                f"({domain}) does not require distributed compute. A single deployable unit "
                "with one database keeps latency low, cost minimal, and operations trivial. "
                "No queues, message brokers or service mesh are warranted at this scale."
            ),
            "light",
        )
    if complexity < 50:
        return (
            "Modular Monolith",
            "modular_monolith",
            (
                f"Complexity score is {complexity}/100. A modular monolith keeps a single "
                f"deployable unit with clean internal module boundaries, plus a cache layer "
                f"and a primary database with a read replica. This satisfies {domain} needs "
                "without the operational cost of distributed microservices."
            ),
            "standard",
        )
    if complexity < 75:
        return (
            "Microservices Architecture",
            "microservices",
            (
                f"Complexity score is {complexity}/100 with meaningful throughput for {domain}. "
                "Independent services behind an API gateway allow per-service scaling, fault "
                "isolation and team ownership. A message queue decouples async work such as "
                "notifications and background jobs."
            ),
            "heavy",
        )
    return (
        "Event-Driven Microservices",
        "event_driven",
        (
            f"Complexity score is {complexity}/100 — very high throughput and strict "
            f"{domain} requirements justify an event-driven architecture. A streaming bus "
            "enables decoupled producers/consumers, horizontal partitioning, and replayable "
            "event logs for audit and analytics."
        ),
        "heavy",
    )


# ---------------------------------------------------------------------------
# Domain classification
# ---------------------------------------------------------------------------

def classify_domain(business_problem: str) -> str:
    p = business_problem.lower()

    def has(terms):
        return any(re.search(r"\b" + re.escape(t) + r"\b", p) for t in terms)

    if has(["cybersecurity", "security", "threat", "soc", "siem", "endpoint", "malware", "vulnerability", "firewall", "ids", "intrusion", "detection engine"]):
        return "Cybersecurity"
    elif has(["e-commerce", "ecommerce", "shop", "cart", "checkout", "retail", "store", "order", "catalog"]):
        return "E-Commerce"
    elif has(["fintech", "bank", "payment", "ledger", "fraud", "trading", "crypto", "wallet", "transactions", "ach"]):
        return "FinTech"
    elif has(["health", "patient", "medical", "fhir", "hipaa", "telehealth", "hospital", "clinic"]):
        return "Healthcare"
    elif has(["chat", "messaging", "websocket", "slack", "messenger", "communication", "conversation"]):
        return "Real-Time Chat"
    elif has(["saas", "multi-tenant", "multitenant", "tenant", "billing", "subscription", "crm", "erp"]):
        return "SaaS Platform"
    else:
        return "General"


# ---------------------------------------------------------------------------
# Component primitives
# ---------------------------------------------------------------------------

def sanitize_label(name: str) -> str:
    """Make a component name safe for a mermaid node label."""
    return re.sub(r"[^\w\- ]", " ", name).strip()


def _scaling_for(comp_type: str, flavor: str) -> str:
    if comp_type == "database":
        return "Read replicas for reads; vertical scale for writes; partition if writes exceed single-node capacity."
    if comp_type == "cache":
        return "Cluster mode with replicas; scale by adding shards."
    if comp_type == "queue":
        return "Horizontal partitions/consumer groups; add consumers to increase throughput."
    if comp_type == "gateway":
        return "Stateless — scale horizontally behind the load balancer."
    if comp_type == "external":
        return "Managed by provider; subscribe to higher tiers for more capacity."
    if flavor == "heavy":
        return "Stateless — scale horizontally with auto-scaling (HPA) on CPU/RPS."
    if flavor == "standard":
        return "Scale vertically initially; add instances and a load balancer when needed."
    return "Scale vertically; not expected to need horizontal scaling at this traffic."


def _failure_for(comp_type: str, flavor: str) -> str:
    if comp_type == "database":
        return "Primary failure triggers automatic failover to a replica (RPO < 5 min). Degraded reads during promotion."
    if comp_type == "cache":
        return "Cache miss storm on failure; sustained by falling back to the database, with gradual warm-up."
    if comp_type == "queue":
        return "Messages remain persisted in the broker; consumers resume after reconnect; duplicate delivery must be idempotent."
    if comp_type == "external":
        return "Outage handled via circuit breaker + retry with backoff; degraded mode returns cached/stale data."
    if flavor == "heavy":
        return "Instance failure is handled by the orchestrator restarting the pod; traffic rerouted to healthy replicas."
    return "Restart on failure; single instance implies brief downtime unless a backup instance is provisioned."


def _security_for(comp_type: str, domain: str) -> str:
    base = "mTLS between internal services; principle of least privilege."
    if comp_type == "external":
        return "Secrets managed in a vault; provider API calls signed and never logged in plaintext."
    if comp_type == "database":
        return "Encrypted at rest (AES-256); credentials via secrets manager; row/column level access control."
    if comp_type == "cache":
        return "Network-isolated; auth enabled; sensitive data evicted via TTL and never cached unencrypted where prohibited."
    if domain == "FinTech":
        return "PCI-DSS scoping; dual control for admin actions; full tamper-evident audit trail."
    if domain == "Healthcare":
        return "HIPAA: PHI encrypted in transit/at rest; access logged for every read; BAA-managed third parties."
    return base


def make_component(index, name, comp_type, technology, responsibility, flavor, domain,
                   dependencies, alternatives=None) -> dict:
    return {
        "id": f"comp-{index + 1}",
        "name": name,
        "type": comp_type,
        "technology": technology,
        "responsibility": responsibility,
        "internal_or_external": "external" if comp_type == "external" else "internal",
        "dependencies": dependencies,
        "scaling_strategy": _scaling_for(comp_type, flavor),
        "failure_behavior": _failure_for(comp_type, flavor),
        "security_considerations": _security_for(comp_type, domain),
        "alternatives": alternatives or [],
        "reason": responsibility,
    }


# ---------------------------------------------------------------------------
# Requirements agent
# ---------------------------------------------------------------------------

def build_requirements(business_problem: str, domain: str, workload: dict,
                       constraints: list, architecture_tier: str) -> dict:
    reqs = {
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
    }

    constraints = [str(c).strip() for c in (constraints or []) if str(c).strip()]
    peak = workload.get("peak_requests_per_second") or 0
    users = workload.get("users")

    if domain == "General":
        reqs["functional"].append("Core CRUD operations for the primary business entities described.")
        reqs["functional"].append("User-facing interface (web/mobile) authenticated against the system.")
        reqs["functional"].append("Administrative view for managing core entities and monitoring usage.")
    elif domain == "E-Commerce":
        reqs["functional"].extend([
            "Product catalog browsing, search and filtering.",
            "Shopping cart management with price/stock validation at checkout.",
            "Order placement with transactional inventory deduction and payment authorization.",
            "Order status tracking and fulfillment/notification events.",
        ])
        reqs["actors"].extend(["Customer", "Admin/CSR", "Payment Provider", "Fulfillment System"])
        reqs["business_rules"].append("A product cannot be oversold: stock is reserved atomically at order placement.")
    elif domain == "FinTech":
        reqs["functional"].extend([
            "Double-entry ledger posting with strict serializability per account.",
            "Payment initiation, authorization and settlement with external rails.",
            "Fraud scoring on every transaction before settlement.",
            "KYC/AML identity verification and sanction screening.",
        ])
        reqs["actors"].extend(["Account Holder", "Compliance Officer", "Payment Rails (ACH/ISO20022)", "Fraud Analysts"])
        reqs["business_rules"].append("Every money movement must post to both a debit and a credit leg atomically.")
    elif domain == "Real-Time Chat":
        reqs["functional"].extend([
            "Real-time message delivery over persistent connections.",
            "Presence/typing indicators for online participants.",
            "Message history retrieval and unread counts.",
        ])
        reqs["actors"].extend(["User", "Moderator", "Notification Service"])
    elif domain == "Cybersecurity":
        reqs["functional"].extend([
            "Continuous event ingestion from endpoints and network sensors.",
            "Correlation rules that detect threats in real time.",
            "Alerting and incident case management.",
        ])
        reqs["actors"].extend(["Security Analyst", "Endpoint Agent", "Threat Intelligence Feeds", "SIEM"])
    elif domain == "Healthcare":
        reqs["functional"].extend([
            "FHIR-compliant patient record management.",
            "Role-based access to PHI with full audit logging.",
            "Appointment/scheduling and clinical notes workflows.",
        ])
        reqs["actors"].extend(["Patient", "Physician", "Radiology/Imaging System", "Billing System"])
    elif domain == "SaaS Platform":
        reqs["functional"].extend([
            "Multi-tenant accounts, teams and role-based access control.",
            "Core domain workflows for tenants with per-tenant data isolation.",
            "Usage metering and billing/export capabilities.",
        ])
        reqs["actors"].extend(["Tenant Admin", "End User", "Billing Provider"])

    reqs["functional"].append("Authentication and authorization for all user-facing capabilities.")
    reqs["functional"].append("Audit trail of significant system events for accountability.")

    # Non-functional (workload-driven)
    reqs["non_functional"].extend([
        f"Throughput: sustain {workload['avg_requests_per_second']:g} req/s average, "
        f"{workload['peak_requests_per_second']:g} req/s at peak.",
        f"Expected concurrency of ~{workload['expected_concurrency']:g} simultaneous in-flight requests.",
        "P95 latency target: < 200ms for reads, < 500ms for writes.",
    ])
    if peak >= 500:
        reqs["non_functional"].append("Horizontal scalability: stateless services must scale out without data rebalancing.")
    if peak >= 5000:
        reqs["non_functional"].append("Asynchronous processing via a message queue for non-interactive workloads.")
    if domain in ("FinTech", "Healthcare", "Cybersecurity"):
        reqs["non_functional"].append("Availability target 99.99% with zero-data-loss recovery points.")
        reqs["availability_requirement"] = "99.99%"
    else:
        reqs["non_functional"].append("Availability target 99.9% for business hours.")
        reqs["availability_requirement"] = "99.9%"

    reqs["non_functional"].append("Encryption in transit (TLS 1.3) and at rest (AES-256).")
    if workload.get("budget_monthly"):
        reqs["non_functional"].append(f"Stay within the stated monthly budget of {workload['budget_monthly']}.")

    reqs["constraints"] = constraints or []
    if "multi-region" in " ".join(constraints).lower() or any(k in business_problem.lower() for k in ["multi-region", "global", "worldwide"]):
        reqs["constraints"].append("Multi-region availability required.")

    # Assumptions & ambiguities — never silently invent critical values.
    reqs["assumptions"].extend(workload.get("assumptions", []))
    if users is None:
        reqs["ambiguities"].append({
            "question": "What is the expected number of concurrent / total users?",
            "suggested_assumption": "Not specified — throughput modeled from the problem text.",
            "confidence": "low",
            "impact": "high",
        })
    if not workload.get("daily_requests") and not _find_rate(business_problem):
        reqs["ambiguities"].append({
            "question": "What is the expected peak traffic volume?",
            "suggested_assumption": f"{workload['peak_requests_per_second']:g} requests/second modeled from a {workload['peak_multiplier']:g}x burst factor.",
            "confidence": "medium",
            "impact": "high",
        })
    if domain == "General":
        reqs["ambiguities"].append({
            "question": "What are the core entities and primary user flows?",
            "suggested_assumption": "Generic CRUD entities; flows will need confirmation.",
            "confidence": "low",
            "impact": "high",
        })

    reqs["dependencies"] = ["Identity/Authentication provider"] if domain not in ("Cybersecurity",) else ["Endpoint agents", "Threat intelligence feeds"]
    if domain in ("E-Commerce", "FinTech"):
        reqs["dependencies"].append("External payment provider")
    if domain == "Healthcare":
        reqs["dependencies"].append("External FHIR-compliant registries")

    reqs["scale_requirements"] = {
        "users": users,
        "avg_requests_per_second": workload["avg_requests_per_second"],
        "peak_requests_per_second": workload["peak_requests_per_second"],
        "concurrency": workload["expected_concurrency"],
    }
    if domain in ("FinTech", "Healthcare"):
        reqs["security_requirements"] = ["Encryption at rest/in transit", "Full audit trail", "Strong authentication", "Access control per role"]
    else:
        reqs["security_requirements"] = ["TLS everywhere", "Role-based access control", "Input validation", "Secrets management"]

    return reqs


# ---------------------------------------------------------------------------
# Architecture agent
# ---------------------------------------------------------------------------

def build_components(domain: str, workload: dict, pattern: str, flavor: str) -> list:
    comps = []
    domain = domain or "General"

    # Common infrastructure components.
    comps.append(make_component(
        0, "Web / Mobile Client", "client", "Browser / Native",
        "Entry point for end users; renders the UI and calls the API.", flavor, domain, [],
    ))
    idx = 1
    gateway_tech = "Kong / Ocelot" if flavor == "heavy" else "Nginx"
    comps.append(make_component(
        idx, "API Gateway", "gateway", gateway_tech,
        "Single front door: terminates TLS, authenticates tokens, enforces rate limits and routes requests.",
        flavor, domain, ["Web / Mobile Client"], ["AWS API Gateway", "Traefik"],
    ))
    idx += 1

    # Domain services.
    svc_specs = _domain_services(domain, flavor)
    for (name, tech, responsibility, deps) in svc_specs:
        comps.append(make_component(idx, name, "service", tech, responsibility, flavor, domain, deps))
        idx += 1

    # Cache — only included when warranted by scale.
    if flavor in ("standard", "heavy") or workload["peak_requests_per_second"] >= 50:
        comps.append(make_component(
            idx, "Cache Layer", "cache", "Redis",
            "Caches hot reads (sessions, catalog, lookups) to cut database load.",
            flavor, domain, ["API Gateway"], ["Memcached"],
        ))
        idx += 1

    # Queue — only for heavy / high-throughput patterns.
    if flavor == "heavy":
        queue_tech = "Apache Kafka" if workload["peak_requests_per_second"] >= 2000 else "RabbitMQ"
        comps.append(make_component(
            idx, "Message Queue", "queue", queue_tech,
            "Decouples async work: notifications, event distribution, analytics ingestion.",
            flavor, domain, ["API Gateway"], ["Redis Streams", "SQS"],
        ))
        idx += 1

    # Database.
    db_tech = _database_for(domain, pattern)[0]
    comps.append(make_component(
        idx, "Primary Database", "database", db_tech,
        "System of record: transactional persistence for the core domain.",
        flavor, domain, ["API Gateway"], _database_for(domain, pattern)[2],
    ))
    idx += 1

    # External systems.
    ext_specs = _external_services(domain, flavor)
    for (name, tech, responsibility) in ext_specs:
        comps.append(make_component(idx, name, "external", tech, responsibility, flavor, domain, []))
        idx += 1

    # Observability when warranted.
    if flavor in ("standard", "heavy"):
        comps.append(make_component(
            idx, "Observability Stack", "infrastructure", "Prometheus + Grafana + Jaeger",
            "Metrics, tracing and centralized logging for the whole system.",
            flavor, domain, ["API Gateway"],
        ))

    return comps


def _domain_services(domain: str, flavor: str):
    if flavor == "light":
        return [
            ("Core Application Service", "Python (FastAPI)",
             "Implements the business logic for the primary entities and workflows.",
             ["API Gateway"]),
        ]
    if domain == "E-Commerce":
        return [
            ("Product Catalog Service", "Node.js / NestJS",
             "Read-heavy catalog, search and product metadata.", ["API Gateway"]),
            ("Cart & Checkout Service", "Go",
             "Atomic cart mutations, price/stock validation, checkout orchestration.", ["API Gateway", "Product Catalog Service"]),
            ("Order Processing Service", "Java / Spring Boot",
             "Order state machine, inventory deduction, fulfillment dispatch, outbox events.", ["API Gateway", "Cart & Checkout Service"]),
        ]
    if domain == "FinTech":
        return [
            ("Core Ledger Engine", "Rust / Go",
             "Double-entry ledger with strict per-account serializability.", ["API Gateway"]),
            ("Payment Gateway Service", "Go",
             "Payment authorization/settlement with external rails and idempotency.", ["API Gateway", "Core Ledger Engine"]),
            ("Fraud Detection Service", "Python",
             "Real-time transaction scoring against fraud models.", ["API Gateway", "Payment Gateway Service"]),
            ("KYC / AML Service", "Python (FastAPI)",
             "Identity verification and sanction-list screening.", ["API Gateway"]),
        ]
    if domain == "Real-Time Chat":
        return [
            ("WebSocket Gateway", "Go",
             "Maintains persistent connections and routes messages.", ["API Gateway"]),
            ("Message Dispatcher", "Rust",
             "Fan-out of messages to recipient connections, ordering and delivery.", ["WebSocket Gateway"]),
            ("Presence Service", "Node.js / Redis",
             "Tracks online/typing state and pushes presence updates.", ["WebSocket Gateway", "Cache Layer"]),
        ]
    if domain == "Cybersecurity":
        return [
            ("Detection Engine", "Python / Rust",
             "Evaluates events against Sigma/YARA rules and correlates threats.", ["API Gateway"]),
            ("Threat Intelligence Service", "FastAPI",
             "Enriches IPs/hashes from external feeds with caching.", ["API Gateway"]),
            ("Alerting Service", "Node.js",
             "Dispatches deduplicated alerts to PagerDuty/Slack/email.", ["API Gateway"]),
        ]
    if domain == "Healthcare":
        return [
            ("Patient Records Service", "Node.js",
             "FHIR-compliant management of patient data with access control.", ["API Gateway"]),
            ("Appointments Service", "Go",
             "Scheduling, availability and notifications.", ["API Gateway", "Patient Records Service"]),
            ("Clinical Notes Service", "Python",
             "Structured clinical notes with strict audit logging.", ["API Gateway", "Patient Records Service"]),
        ]
    if domain == "SaaS Platform":
        return [
            ("Tenant & Auth Service", "FastAPI",
             "Tenant onboarding, authentication, RBAC and isolation.", ["API Gateway"]),
            ("Core Business Service", "Node.js / Go",
             "Executes tenant domain workflows.", ["API Gateway", "Tenant & Auth Service"]),
            ("Reporting Service", "Python",
             "Aggregates tenant metrics and exports reports via the queue.", ["API Gateway", "Core Business Service"]),
        ]
    # General
    return [
        ("Auth Service", "FastAPI",
         "Authentication, sessions and role-based authorization.", ["API Gateway"]),
        ("Business Logic Service", "Python (FastAPI)",
         "Implements the core workflows of the primary entities.", ["API Gateway", "Auth Service"]),
        ("Notification Service", "Node.js",
         "Sends email/push notifications on state changes.", ["API Gateway", "Business Logic Service"]),
    ]


def _external_services(domain: str, flavor: str):
    if flavor == "light":
        return []
    if domain in ("E-Commerce", "FinTech"):
        return [("Payment Provider", "Stripe / Razorpay / Adyen",
                 "External PSP handling card/UPI/wallet payments. Never modeled as an internal microservice.")]
    if domain == "Healthcare":
        return [("Imaging / RIS System", "DICOM / PACS",
                 "External radiology imaging system exchange.")]
    if domain == "Real-Time Chat":
        return [("Push Notification Provider", "FCM / APNs",
                 "External mobile push delivery.")]
    if domain == "Cybersecurity":
        return [("Threat Intel Feeds", "VirusTotal / AlienVault",
                 "External enrichment APIs with rate-limit caching.")]
    return []


def _database_for(domain: str, pattern: str):
    """Returns (primary, cache, alternatives)."""
    if domain == "Real-Time Chat":
        return ("PostgreSQL (messages + metadata)", "Redis (presence/cache)", ["Cassandra", "ScyllaDB"])
    if domain == "Cybersecurity":
        return ("PostgreSQL (metadata) + TimescaleDB (events)", "Redis (active threats)", ["Elasticsearch"])
    if domain == "E-Commerce":
        return ("PostgreSQL (ACID orders/cart)", "Redis (sessions/catalog cache)", ["MongoDB", "DynamoDB"])
    if domain == "FinTech":
        return ("PostgreSQL (ledger, ACID)", "Redis (locks/cache)", ["TigerBeetle", "MongoDB"])
    if domain == "Healthcare":
        return ("PostgreSQL (PHI, encrypted)", "Redis (session cache)", ["S3 for DICOM objects"])
    if domain == "SaaS Platform":
        return ("PostgreSQL (multi-tenant)", "Redis (tenant cache)", ["MySQL"])
    return ("PostgreSQL", "Redis (optional cache)", ["SQLite", "MySQL"])


def build_relationships(components: list, flavor: str) -> list:
    rels = []
    by_name = {c["name"]: c for c in components}
    for c in components:
        for dep in c.get("dependencies", []):
            if dep in by_name and dep != c["name"]:
                rels.append({
                    "from": c["name"], "to": dep, "kind": "depends_on",
                    "description": f"{c['name']} depends on {dep}.",
                })
    # Client -> Gateway -> services -> db flow.
    if "API Gateway" in by_name and "Web / Mobile Client" in by_name:
        rels.append({"from": "Web / Mobile Client", "to": "API Gateway", "kind": "HTTPS",
                     "description": "All traffic enters through the API Gateway."})
    for c in components:
        if c.get("type") == "service":
            rels.append({"from": "API Gateway", "to": c["name"], "kind": "route",
                         "description": f"Gateway routes requests to {c['name']}."})
    if "Primary Database" in by_name:
        for c in components:
            if c.get("type") == "service":
                rels.append({"from": c["name"], "to": "Primary Database", "kind": "read/write",
                             "description": f"{c['name']} persists state in the database."})
    if "Cache Layer" in by_name:
        rels.append({"from": "API Gateway", "to": "Cache Layer", "kind": "read-through",
                     "description": "Cache is checked before hitting the database."})
    if "Message Queue" in by_name:
        for c in components:
            if c.get("type") == "service":
                rels.append({"from": c["name"], "to": "Message Queue", "kind": "publish",
                             "description": f"{c['name']} publishes async events."})
    # dedupe
    seen = set()
    out = []
    for r in rels:
        key = (r["from"], r["to"], r["kind"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def build_decisions(domain: str, pattern: str, flavor: str, workload: dict, db_tech: str, has_cache: bool, has_queue: bool, queue_tech: str) -> list:
    peak = workload["peak_requests_per_second"]
    decisions = [
        {
            "decision": pattern,
            "reason": (
                f"Complexity score of {workload['complexity_score']}/100 (peak {peak:g} req/s) does "
                f"not warrant a heavier topology; {pattern} satisfies the {domain} requirements with "
                "the least operational burden."
            ),
            "alternatives": ["Microservices", "Serverless", "Event-Driven"],
            "rejected_alternatives": ["Microservices"] if flavor == "light" else [],
            "rejected_reason": (
                "Network hops, distributed transactions and operational overhead add no value at this scale."
                if flavor == "light" else "Not applicable at the selected complexity."
            ),
            "tradeoff": "A single deployable unit couples deployments; future extraction of services is possible as scale grows.",
            "confidence": 0.9,
        },
        {
            "decision": db_tech,
            "reason": (
                f"The {domain} domain requires strong transactional guarantees for core workflows; "
                f"peak write pressure of ~{workload['write_per_second']:g} writes/s fits a single ACID "
                "primary with read replicas."
            ),
            "alternatives": ["MongoDB", "DynamoDB"],
            "rejected_alternatives": ["DynamoDB"],
            "rejected_reason": "The workload has relational/transactional requirements that NoSQL document stores handle poorly.",
            "tradeoff": "Horizontal write scaling is more complex than a sharded NoSQL store.",
            "confidence": 0.91,
        },
    ]
    if has_cache:
        decisions.append({
            "decision": "Redis cache layer",
            "reason": (
                f"Peak reads of ~{workload['read_per_second']:g}/s would otherwise land on the database; "
                "caching hot reads cuts DB load and improves P95 latency."
            ),
            "alternatives": ["Memcached", "In-process cache"],
            "rejected_alternatives": ["In-process cache"],
            "rejected_reason": "Does not survive instance restarts and cannot be shared across instances.",
            "tradeoff": "Cache invalidation and consistency complexity; cold-start cache misses.",
            "confidence": 0.85,
        })
    if has_queue:
        decisions.append({
            "decision": f"{queue_tech} message queue",
            "reason": (
                f"Async workloads (notifications, reporting, event distribution) are decoupled at "
                f"{peak:g} req/s peak to protect the interactive API path."
            ),
            "alternatives": ["RabbitMQ", "Redis Streams", "SQS"],
            "rejected_alternatives": ["SQS"] if "Kafka" not in queue_tech else ["RabbitMQ"],
            "rejected_reason": "Managed queues limit replay and long retention needed for analytics." if "Kafka" in queue_tech else "Simplicity over features at this scale.",
            "tradeoff": "At-least-once delivery requires idempotent consumers.",
            "confidence": 0.8,
        })
    return decisions


# ---------------------------------------------------------------------------
# Database agent
# ---------------------------------------------------------------------------

def build_database(domain: str, pattern: str, workload: dict, db_tech: str, flavor: str) -> dict:
    primary = db_tech.split(" + ")[0]
    entity = _core_entity(domain)
    write_sql = f"""CREATE TABLE IF NOT EXISTS {entity.replace(' ', '_').lower()} (
  id UUID PRIMARY KEY,
  {entity.lower().replace(' ', '_')}_key VARCHAR(255) NOT NULL,
  status VARCHAR(50) NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_{entity.replace(' ', '_').lower()}_status
  ON {entity.replace(' ', '_').lower()}(status, created_at DESC);
"""
    audit_sql = """CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY,
  actor_id UUID NOT NULL,
  action VARCHAR(255) NOT NULL,
  resource_id VARCHAR(255) NOT NULL,
  ip_address INET,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_actor ON audit_logs(actor_id, created_at DESC);
"""
    schemas = [
        {"table_name": entity.replace(" ", "_").lower(), "sql": write_sql},
        {"table_name": "audit_logs", "sql": audit_sql},
    ]
    if flavor in ("standard", "heavy"):
        schemas.append({
            "table_name": "outbox_events",
            "sql": """CREATE TABLE IF NOT EXISTS outbox_events (
  id UUID PRIMARY KEY,
  aggregate_id VARCHAR(255) NOT NULL,
  event_type VARCHAR(100) NOT NULL,
  payload JSONB NOT NULL,
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_outbox_unpublished ON outbox_events(published_at)
  WHERE published_at IS NULL;
""",
        })

    return {
        "database_type": db_tech,
        "justification": (
            f"{primary} is chosen because the {domain} workloads are predominantly transactional and "
            f"relational. Peak writes of ~{workload['write_per_second']:g}/s are comfortably served by "
            "a single primary with read replicas for the read-heavy paths."
        ),
        "schemas": schemas,
        "indexing_strategies": [
            f"Index on {entity.lower().replace(' ', '_')}(status, created_at DESC) for dashboard and state queries.",
            "Index on audit_logs(actor_id, created_at DESC) for compliance queries.",
        ],
        "transactions": "ACID transactions used for all money/state-changing operations.",
        "sharding": "Not required at current scale; schema partitioned by tenant/region when multi-tenancy grows.",
        "migrations": "Liquibase/Alembic versioned migrations applied via CI with backward-compatible changes.",
        "caching_layer": "Redis read-through cache with TTL on hot reads; write-through for sessions.",
    }


def _core_entity(domain: str) -> str:
    return {
        "E-Commerce": "Order", "FinTech": "Transaction", "Real-Time Chat": "Message",
        "Cybersecurity": "SecurityEvent", "Healthcare": "Patient", "SaaS Platform": "Tenant",
        "General": "Entity",
    }.get(domain, "Entity")


# ---------------------------------------------------------------------------
# API agent
# ---------------------------------------------------------------------------

def build_api(domain: str, components: list, database: dict, security: dict, workload: dict) -> dict:
    endpoints = []
    entity = _core_entity(domain).lower().replace(" ", "_")

    def ep(method, path, desc, req, res):
        endpoints.append({
            "method": method, "path": path, "description": desc,
            "request_body": req, "response_body": res,
        })

    ep("POST", f"/api/v1/{entity}s",
       f"Create a new {_core_entity(domain)} with validation and audit logging.",
       '{\n  "data": {},\n  "client_request_id": "uuid"\n}',
       '{\n  "id": "uuid",\n  "status": "created"\n}')
    ep("GET", f"/api/v1/{entity}s/{{id}}",
       f"Fetch a single {_core_entity(domain)} by id.",
       None,
       '{\n  "id": "uuid",\n  "status": "ok"\n}')
    if "Order" in _core_entity(domain):
        ep("POST", "/api/v1/orders/checkout",
           "Atomic checkout: validates cart, reserves stock, authorizes payment.",
           '{\n  "cart_id": "uuid",\n  "payment_token": "string"\n}',
           '{\n  "order_id": "uuid",\n  "status": "placed"\n}')
    if "Transaction" in _core_entity(domain):
        ep("POST", "/api/v1/transactions/initiate",
           "Initiate a payment with an idempotency key.",
           '{\n  "amount": "100.00",\n  "currency": "INR",\n  "idempotency_key": "uuid"\n}',
           '{\n  "txn_id": "uuid",\n  "status": "authorizing"\n}')
    ep("POST", "/api/v1/events",
       "Ingest operational events (audit / telemetry).",
       '{\n  "event_type": "string",\n  "data": {}\n}',
       '{\n  "status": "received",\n  "event_id": "uuid"\n}')

    return {
        "protocol": "REST HTTP / JSON",
        "authentication_strategy": security.get("authentication_strategy", "OAuth2 / JWT"),
        "endpoints": endpoints,
        "rate_limits": f"{60 if workload['peak_requests_per_second'] < 100 else 300} req/min per user, {600} req/min per IP.",
        "versioning": "URL versioning /api/v1; additive-only changes within a major version.",
        "error_handling": "RFC 7807 problem+json errors; retry-after on 429; 5xx not retried blindly.",
        "idempotency": "Idempotency keys on all mutating endpoints; safe retry of payment/order calls.",
    }


# ---------------------------------------------------------------------------
# Deployment agent
# ---------------------------------------------------------------------------

def build_deployment(pattern: str, flavor: str, domain: str) -> dict:
    if flavor == "light":
        orchestration = "Single VM / Docker Compose"
        manifest = "docker-compose.yml (single service + database)"
        tf_sample = """# main.tf - Single-node starter
provider "aws" {
  region = "us-east-1"
}

resource "aws_instance" "app" {
  ami           = "ami-0abcdef123"
  instance_type = "t3.small"
  tags          = { Name = "app" }
}

resource "aws_db_instance" "db" {
  engine              = "postgres"
  instance_class      = "db.t4g.small"
  allocated_storage   = 20
  skip_final_snapshot = true
}
"""
    elif flavor == "standard":
        orchestration = "AWS ECS (Fargate) / Docker Compose"
        tf_sample = """# main.tf - Modular monolith with cache + read replica
provider "aws" { region = "us-east-1" }

resource "aws_ecs_cluster" "main" { name = "main" }

resource "aws_db_instance" "primary" {
  engine           = "postgres"
  instance_class   = "db.t4g.medium"
  multi_az         = true
  allocated_storage = 50
}

resource "aws_db_instance" "replica" {
  engine            = "postgres"
  instance_class    = "db.t4g.medium"
  replicate_source_db = aws_db_instance.primary.id
}

resource "aws_elasticache_cluster" "cache" {
  cluster_id = "cache"
  engine     = "redis"
  node_type  = "cache.t4g.small"
}
"""
    else:
        orchestration = "Amazon EKS (Kubernetes)"
        tf_sample = """# main.tf - Production EKS cluster
provider "aws" { region = "us-east-1" }

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  name    = "mosaic-vpc"
  cidr    = "10.0.0.0/16"
  azs     = ["us-east-1a", "us-east-1b"]
  private_subnets = ["10.0.10.0/24", "10.0.11.0/24"]
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  enable_nat_gateway = true
}

module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  cluster_name    = "mosaic-cluster"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets
}
"""
    k8s_manifest = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: domain-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: domain-service
  template:
    metadata:
      labels:
        app: domain-service
    spec:
      containers:
      - name: service
        image: mosaic/domain-service:latest
        ports:
        - containerPort: 8000
        resources:
          requests: { cpu: "250m", memory: "256Mi" }
          limits:   { cpu: "500m", memory: "512Mi" }
      readinessProbe:
        httpGet: { path: /health, port: 8000 }
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: domain-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: domain-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target: { type: Utilization, averageUtilization: 70 }
"""

    return {
        "provider": "AWS",
        "regions": ["us-east-1"] if flavor == "light" else ["us-east-1", "us-west-2"],
        "infrastructure_as_code": "Terraform",
        "orchestration": orchestration,
        "environments": ["dev", "staging", "prod"],
        "terraform_sample": tf_sample,
        "kubernetes_manifest": k8s_manifest if flavor != "light" else "# Not applicable at starter tier.",
        "scaling_policy": (
            "Manual resize; HPA not required."
            if flavor == "light" else
            "HPA on CPU/RPS (min 3, max 20); cache cluster auto-scaled."
        ),
        "disaster_recovery": (
            "Daily automated backups with point-in-time recovery; RPO 24h."
            if flavor == "light" else
            "Multi-AZ primary + cross-region snapshot replication; RPO < 15 min, RTO < 1 h."
        ),
        "ci_cd": "CI builds + image scan; blue/green deploy to ECS/EKS with automated rollback.",
    }


# ---------------------------------------------------------------------------
# Security agent
# ---------------------------------------------------------------------------

def build_security(domain: str, pattern: str, flavor: str, workload: dict) -> dict:
    mitigations = [
        "Authentication: OAuth2 / OIDC with short-lived JWTs; refresh-token rotation.",
        "Authorization: RBAC with least-privilege scopes enforced at the API layer.",
        "Transport: TLS 1.3 everywhere; internal mTLS between services.",
        "At rest: AES-256 encryption for all datastores.",
        "Input validation + parameterized queries to prevent injection.",
        "Rate limiting and bot/WAF filtering at the edge.",
    ]
    if domain in ("E-Commerce", "FinTech"):
        mitigations.append("PCI-DSS scoping: card data flows directly to the PSP, never stored internally.")
        mitigations.append("Idempotency keys and signed webhooks to prevent replay/duplicate payments.")
        mitigations.append("Tamper-evident, append-only audit logs with dual control.")
    if domain == "Healthcare":
        mitigations.append("HIPAA: PHI access logged on every read; BAA with external processors.")
    if domain == "Cybersecurity":
        mitigations.append("Zero-trust network segmentation with per-service policy enforcement.")

    auth_strategy = "OAuth2 / OIDC (PKCE) with JWT access tokens + refresh rotation"
    compliance = {
        "FinTech": "PCI-DSS, SOX, data-residency compliance",
        "Healthcare": "HIPAA (ePHI), SOC2",
        "Cybersecurity": "SOC2 Type II, ISO 27001",
        "E-Commerce": "PCI-DSS (Level 1), GDPR",
        "SaaS Platform": "SOC2, GDPR",
        "Real-Time Chat": "GDPR, COPPA (if minors)",
        "General": "SOC2 / GDPR baseline",
    }.get(domain, "SOC2 / GDPR baseline")

    scores = {
        "security": min(99, 88 + (6 if domain in ("FinTech", "Healthcare", "Cybersecurity") else 2)),
        "scalability": min(99, 78 + int(workload["peak_requests_per_second"]) // 1000),
        "cost": 85 if flavor == "light" else (82 if flavor == "standard" else 74),
    }

    return {
        "authentication_strategy": auth_strategy,
        "authorization": "Role-based access control (RBAC) with scoped JWT claims.",
        "data_protection": "TLS 1.3 in transit; AES-256 at rest; secrets in a vault; field-level encryption for PHI/PII.",
        "vulnerability_mitigations": mitigations,
        "compliance": compliance,
        "scores": scores,
        "threat_model": [
            "Spoofing: mitigated by OAuth2 + mTLS.",
            "Tampering: integrity via TLS + signed webhooks.",
            "Repudiation: append-only audit logs.",
            "Information disclosure: least-privilege + field-level encryption.",
            "Denial of service: rate limits, WAF, autoscaling.",
            "Elevation: RBAC scopes, no admin surface exposed publicly.",
        ],
    }


# ---------------------------------------------------------------------------
# Performance agent — real workload analysis
# ---------------------------------------------------------------------------

def build_performance(domain: str, workload: dict, components: list, flavor: str) -> dict:
    peak = workload["peak_requests_per_second"]
    avg = workload["avg_requests_per_second"]
    read_ratio = 0.8
    read_ps = avg * read_ratio
    write_ps = avg * (1 - read_ratio)
    workload["read_per_second"] = round(read_ps, 2)
    workload["write_per_second"] = round(write_ps, 2)

    bottlenecks = []
    if peak >= 100:
        bottlenecks.append({
            "name": "Primary database writes",
            "analysis": f"~{write_ps:g} writes/s at the average, ~{write_ps * 3:g}/s at peak, hit a single primary. Above ~5k writes/s the primary becomes the constraint.",
            "impact": "Write latency grows and lock contention increases.",
            "mitigation": "Read replicas for reads, batching and async writes via the queue.",
        })
    if peak >= 500:
        bottlenecks.append({
            "name": "Synchronous service-to-service calls",
            "analysis": f"{peak:g} req/s peak across services amplifies tail latency when calls are synchronous.",
            "impact": "P95 latency spikes under burst.",
            "mitigation": "Circuit breakers, timeouts, async offload.",
        })
    bottlenecks.append({
        "name": "Cache coverage",
        "analysis": f"With ~{read_ps:g} reads/s, an uncached hot-read path drives that traffic into the database.",
        "impact": "DB CPU and connection pool exhaustion.",
        "mitigation": "Read-through Redis with TTLs on hot entities.",
    })

    recommendations = []
    if peak >= 50:
        recommendations.append({
            "recommendation": "Add a Redis read-through cache on hot-read paths.",
            "reason": f"{read_ps:g} reads/s would otherwise hit the database.",
            "affected_component": "Cache Layer",
            "expected_benefit": "Cuts database read load by ~60-80% and P95 read latency.",
            "tradeoff": "Cache invalidation complexity and cold-start misses.",
        })
    if peak >= 500:
        recommendations.append({
            "recommendation": "Offload notifications/reporting to the message queue.",
            "reason": "Peak request handling must not wait on slow side-effects.",
            "affected_component": "Message Queue",
            "expected_benefit": "Stabilizes interactive P95 latency.",
            "tradeoff": "At-least-once semantics require idempotent consumers.",
        })
    recommendations.append({
        "recommendation": "Connection pooling with tuned pool size.",
        "reason": f"Concurrency of ~{workload['expected_concurrency']:g} needs bounded DB connections.",
        "affected_component": "API Gateway",
        "expected_benefit": "Prevents connection exhaustion under concurrency.",
        "tradeoff": "Pool sizing must be tuned; too large can oversubscribe the DB.",
    })
    recommendations.append({
        "recommendation": "Add read replicas when read traffic grows.",
        "reason": f"{read_ps:g} reads/s will eventually exceed a single node.",
        "affected_component": "Primary Database",
        "expected_benefit": "Scales reads horizontally without changing application code.",
        "tradeoff": "Replica lag means slightly stale reads (acceptable for read-mostly data).",
    })

    return {
        "workload": workload,
        "latency_targets": {"p95_read_ms": 200, "p95_write_ms": 500},
        "database_pressure": (
            f"~{write_ps:g} writes/s and ~{read_ps:g} reads/s; single-primary fits below ~5k writes/s. "
            "Connection pool must be sized for expected concurrency."
        ),
        "bottlenecks": bottlenecks,
        "cache_requirements": (
            "Redis read-through with TTLs on hot entities and sessions." if flavor != "light"
            else "Not required at this traffic; revisit above ~50 req/s."
        ),
        "queue_requirements": (
            "Required for async workloads and to protect interactive latency." if flavor == "heavy"
            else "Not required at this scale."
        ),
        "scaling_requirements": (
            "Horizontal auto-scaling for stateless services; read replicas for the database."
            if flavor in ("standard", "heavy") else
            "Vertical scaling of the single instance; no horizontal scaling needed yet."
        ),
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Failure scenarios + risks
# ---------------------------------------------------------------------------

def build_failure_scenarios(components: list, flavor: str) -> list:
    scenarios = [
        {
            "scenario": "Primary database fails",
            "detection": "Health checks / connection errors within 15s.",
            "recovery": "Automatic failover to a replica; reads continue, writes buffer briefly.",
            "impact": "Brief write unavailability; RPO < 5 min." if flavor != "light" else "Downtime until manual restore.",
        },
        {
            "scenario": "Cache layer fails",
            "detection": "Elevated DB latency + cache connection errors.",
            "recovery": "Read-through falls back to the database; cache warms up gradually.",
            "impact": "Temporary latency increase; no data loss.",
        },
    ]
    if flavor == "heavy":
        scenarios.append({
            "scenario": "Message queue / broker failure",
            "detection": "Consumer lag and publish errors.",
            "recovery": "Broker replicas take over; consumers resume with idempotent replay.",
            "impact": "Delayed async processing; no message loss with replication.",
        })
        scenarios.append({
            "scenario": "Region outage",
            "detection": "Cross-region health probes fail.",
            "recovery": "DNS/DNS failover routes traffic to the standby region.",
            "impact": "Up to 15 min of read-only degradation.",
        })
    scenarios.append({
        "scenario": "External provider outage (payment/intel)",
        "detection": "Circuit breaker trips after N consecutive failures.",
        "recovery": "Degraded mode with retries/backoff and user-facing retry messaging.",
        "impact": "Affected flows unavailable until provider recovers.",
    })
    return scenarios


def build_risks(domain: str, flavor: str, workload: dict, constraints: list) -> list:
    risks = [
        {
            "risk": "Underestimated traffic",
            "likelihood": "medium",
            "impact": "high",
            "mitigation": "Load tests at peak; autoscaling thresholds tuned below peak.",
        },
        {
            "risk": "Single point of failure in the database",
            "likelihood": "medium",
            "impact": "high",
            "mitigation": "Multi-AZ primary + replicas + tested failover.",
        },
    ]
    if flavor == "heavy":
        risks.append({
            "risk": "Distributed systems complexity",
            "likelihood": "medium",
            "impact": "medium",
            "mitigation": "Strict contracts, tracing, and module ownership.",
        })
    if domain in ("FinTech", "Healthcare"):
        risks.append({
            "risk": "Compliance gaps",
            "likelihood": "low",
            "impact": "high",
            "mitigation": "Continuous compliance checks and audit logging.",
        })
    return risks


# ---------------------------------------------------------------------------
# Architecture reviewer (Step 8)
# ---------------------------------------------------------------------------

def review_model(model: dict) -> dict:
    """Score the architecture and challenge it. Must not rubber-stamp."""
    arch = ensure_dict(model.get("architecture"))
    reqs = ensure_dict(model.get("requirements"))
    db = ensure_dict(model.get("database"))
    sec = ensure_dict(model.get("security"))
    perf = ensure_dict(model.get("performance"))
    dep = ensure_dict(model.get("deployment"))
    workload = ensure_dict(model.get("performance", {}).get("workload"))
    pattern = as_text(arch.get("pattern"))
    style = as_text(arch.get("style"))
    comps = ensure_list(arch.get("components"))
    scores = {}
    critical = []
    warnings = []
    recommendations = []
    missing = []

    # Requirement coverage
    n_func = len(ensure_list(reqs.get("functional")))
    n_comp = len([c for c in comps if c.get("type") in ("service", "gateway")])
    cov = min(100, n_comp * 20 + 20)
    scores["requirement_coverage"] = min(100, 60 + n_func * 5)
    if n_comp < 2 and n_func > 2:
        warnings.append("Few services for the number of functional requirements; check coverage of every flow.")

    # Scalability fit
    expected = {"monolith": 30, "modular_monolith": 60, "microservices": 80, "event_driven": 95}
    complexity = workload.get("complexity_score")
    if complexity is not None:
        ideal_style = ("monolith" if complexity < 25 else
                       "modular_monolith" if complexity < 50 else
                       "microservices" if complexity < 75 else "event_driven")
        if style != ideal_style:
            if expected.get(style, 0) > expected.get(ideal_style, 0) + 20:
                critical.append(f"Pattern '{pattern}' is over-engineered for complexity {complexity}/100; '{ideal_style.replace('_', ' ')}' fits better.")
            else:
                warnings.append(f"Pattern '{pattern}' is heavier than the minimum needed at complexity {complexity}/100.")
        scores["scalability"] = min(100, expected.get(style, 60))
    else:
        scores["scalability"] = 70
        missing.append("Workload complexity score was not computed; scalability judgement is coarse.")

    # Reliability
    reliability = 70
    n_failure = len(ensure_list(model.get("failure_scenarios")))
    reliability += min(15, n_failure * 5)
    dr = as_text(dep.get("disaster_recovery"))
    if dr:
        reliability += 10
    else:
        critical.append("No disaster recovery strategy defined.")
    scores["reliability"] = min(100, reliability)

    # Security
    sec_score = ensure_dict(sec.get("scores")).get("security", 70)
    if sec_score < 80 and domain_needs_high_security(as_text(model.get("domain"))):
        warnings.append("Security posture is below the bar for this domain.")
    scores["security"] = sec_score

    # Performance
    if perf.get("workload", {}).get("peak_requests_per_second") and perf.get("recommendations"):
        scores["performance"] = 85
    else:
        scores["performance"] = 55
        missing.append("Performance lacks calculated workload or concrete recommendations.")

    # Cost
    budget = workload.get("budget_monthly") or ""
    if "flavor_heavy" in as_text(style) or style in ("microservices", "event_driven"):
        scores["cost"] = 70
    else:
        scores["cost"] = 85
    if budget:
        scores["cost"] = min(95, scores["cost"] + 3)

    # Complexity (is it justified?)
    if complexity is not None and style in ("microservices", "event_driven") and complexity < 55:
        warnings.append("Microservices may be excessive for current traffic; a modular monolith would cut operational cost.")
        scores["complexity"] = 55
    else:
        scores["complexity"] = 85

    # Internal/external correctness
    bad_external = [c.get("name") for c in comps
                    if c.get("internal_or_external") == "internal"
                    and any(k in as_text(c.get("name")).lower() + as_text(c.get("technology")).lower()
                            for k in ["stripe", "paypal", "razorpay", "adyen", "twilio", "auth0"])]
    if bad_external:
        critical.append(f"External provider(s) modeled as internal services: {', '.join(bad_external)}.")

    # Technology fit
    tech_issues = [c.get("name") for c in comps if not as_text(c.get("technology")) or as_text(c.get("technology")) == "To be defined"]
    if tech_issues:
        warnings.append(f"Components missing concrete technology choices: {', '.join(tech_issues)}.")

    # Validation issues feed the review.
    for issue in validate_model(model):
        if issue["severity"] == "error":
            critical.append(issue["message"])
        else:
            warnings.append(issue["message"])

    if not dep.get("ci_cd"):
        warnings.append("CI/CD pipeline not specified.")
    if not perf.get("latency_targets"):
        missing.append("Latency targets were not defined.")

    overall = int(sum(scores.values()) / len(scores)) if scores else 60
    if critical:
        overall -= 8 * min(3, len(critical))
    overall = max(20, min(98, overall))

    recommendations.extend([
        "Add a tested failover drill for the primary database.",
        "Add load tests at the modeled peak before production cutover.",
    ])
    if style in ("microservices", "event_driven") and complexity is not None and complexity < 55:
        recommendations.insert(0, "Consider a modular monolith until traffic justifies service boundaries.")

    return {
        "overall_score": overall,
        "categories": scores,
        "critical_issues": critical,
        "warnings": warnings,
        "recommendations": recommendations,
        "missing_information": missing,
    }


def domain_needs_high_security(domain: str) -> bool:
    return domain in ("FinTech", "Healthcare", "Cybersecurity")


# ---------------------------------------------------------------------------
# Bounded self-correction (Step 9)
# ---------------------------------------------------------------------------

MAX_CORRECTION_ITERATIONS = 2


def self_correct(model: dict) -> dict:
    """Fix fixable critical issues; re-review. Bounded loop, never infinite."""
    iterations = 0
    while iterations < MAX_CORRECTION_ITERATIONS:
        review = ensure_dict(model.get("review"))
        critical = ensure_list(review.get("critical_issues"))
        fixed_any = False

        # Fix 1: over-engineered pattern -> downgrade.
        over_engineered = [c for c in critical if "over-engineered" in c]
        if over_engineered:
            new_pattern, style, justification, flavor = (
                "Modular Monolith", "modular_monolith",
                "Revised by the Architecture Reviewer: the previous microservices topology was over-engineered for the modeled traffic. A modular monolith keeps clean boundaries with far lower operational cost.",
                "standard",
            )
            model["architecture"]["pattern"] = new_pattern
            model["architecture"]["style"] = style
            model["architecture"]["justification"] = justification
            workload = ensure_dict(model.get("performance", {}).get("workload"))
            workload["complexity_score"] = min(workload.get("complexity_score") or 50, 49)
            model["performance"]["workload"] = workload
            _rebuild_downstream(model, flavor)
            fixed_any = True

        # Fix 2: external service misclassified -> reclassify.
        for c in ensure_list(model.get("architecture", {}).get("components")):
            name = as_text(c.get("name")).lower() + " " + as_text(c.get("technology")).lower()
            if c.get("internal_or_external") == "internal" and any(
                    k in name for k in ["stripe", "paypal", "razorpay", "adyen", "twilio", "auth0"]):
                c["internal_or_external"] = "external"
                fixed_any = True

        # Fix 3: missing DR -> add one.
        dep = ensure_dict(model.get("deployment"))
        if not as_text(dep.get("disaster_recovery")):
            dep["disaster_recovery"] = "Automated daily backups with point-in-time recovery; RPO 24h (starter) or cross-region replication (production)."
            model["deployment"] = dep
            fixed_any = True

        # Fix 4: missing latency targets.
        perf = ensure_dict(model.get("performance"))
        if not ensure_dict(perf.get("latency_targets")):
            perf["latency_targets"] = {"p95_read_ms": 200, "p95_write_ms": 500}
            model["performance"] = perf
            fixed_any = True

        if not fixed_any:
            break
        iterations += 1
        model["correction_iterations"] = iterations
        model["review"] = review_model(model)

    return model


def _rebuild_downstream(model: dict, flavor: str):
    """After a pattern change, rebuild components + dependent sections."""
    domain = as_text(model.get("domain"))
    workload = ensure_dict(model.get("performance", {}).get("workload"))
    model["architecture"]["components"] = build_components(domain, workload, model["architecture"]["pattern"], flavor)
    model["architecture"]["relationships"] = build_relationships(model["architecture"]["components"], flavor)
    db_tech = _database_for(domain, model["architecture"]["pattern"])
    model["database"] = build_database(domain, model["architecture"]["pattern"], workload, db_tech[0], flavor)
    model["security"] = build_security(domain, model["architecture"]["pattern"], flavor, workload)
    model["api"] = build_api(domain, model["architecture"]["components"], model["database"], model["security"], workload)
    model["deployment"] = build_deployment(model["architecture"]["pattern"], flavor, domain)
    model["performance"] = build_performance(domain, workload, model["architecture"]["components"], flavor)
    model["architecture"]["decisions"] = build_decisions(
        domain, model["architecture"]["pattern"], flavor, workload, db_tech[0],
        has_cache=flavor in ("standard", "heavy"),
        has_queue=flavor == "heavy",
        queue_tech="Apache Kafka" if workload["peak_requests_per_second"] >= 2000 else "RabbitMQ",
    )


# ---------------------------------------------------------------------------
# Diagrams — 3 levels, dynamic design (user requests #1 and #2)
# ---------------------------------------------------------------------------

DIAGRAM_THEMES = [
    {  # Indigo / cyan
        "client":   {"fill": "#1e1b4b", "stroke": "#818cf8"},
        "edge":     {"fill": "#0c4a6e", "stroke": "#38bdf8"},
        "gateway":  {"fill": "#3b0764", "stroke": "#a855f7"},
        "service":  {"fill": "#052e16", "stroke": "#34d399"},
        "db":       {"fill": "#431407", "stroke": "#fb923c"},
        "queue":    {"fill": "#450a0a", "stroke": "#f87171"},
        "external": {"fill": "#111827", "stroke": "#9ca3af"},
        "cache":    {"fill": "#1e3a8a", "stroke": "#60a5fa"},
        "infra":    {"fill": "#14532d", "stroke": "#4ade80"},
    },
    {  # Amber / rose / slate
        "client":   {"fill": "#1c1917", "stroke": "#a8a29e"},
        "edge":     {"fill": "#451a03", "stroke": "#fb923c"},
        "gateway":  {"fill": "#4c0519", "stroke": "#fb7185"},
        "service":  {"fill": "#052e16", "stroke": "#4ade80"},
        "db":       {"fill": "#082f49", "stroke": "#38bdf8"},
        "queue":    {"fill": "#3f1d06", "stroke": "#fbbf24"},
        "external": {"fill": "#1f2937", "stroke": "#9ca3af"},
        "cache":    {"fill": "#3b0764", "stroke": "#a855f7"},
        "infra":    {"fill": "#064e3b", "stroke": "#2dd4bf"},
    },
    {  # Teal / fuchsia
        "client":   {"fill": "#042f2e", "stroke": "#2dd4bf"},
        "edge":     {"fill": "#0c4a6e", "stroke": "#7dd3fc"},
        "gateway":  {"fill": "#701a75", "stroke": "#e879f9"},
        "service":  {"fill": "#0f172a", "stroke": "#818cf8"},
        "db":       {"fill": "#450a0a", "stroke": "#f87171"},
        "queue":    {"fill": "#422006", "stroke": "#facc15"},
        "external": {"fill": "#111827", "stroke": "#8b5cf6"},
        "cache":    {"fill": "#1e1b4b", "stroke": "#a5b4fc"},
        "infra":    {"fill": "#14532d", "stroke": "#86efac"},
    },
]

NODE_TYPE_CLASS = {
    "client": "client", "edge": "edge", "gateway": "gateway", "service": "service",
    "database": "db", "cache": "cache", "queue": "queue", "external": "external",
    "infrastructure": "infra",
}


def _theme_for(model: dict) -> dict:
    key = as_text(model.get("domain")) + "|" + as_text(model.get("architecture", {}).get("pattern"))
    idx = int(hashlib.md5(key.encode()).hexdigest(), 16) % len(DIAGRAM_THEMES)
    return DIAGRAM_THEMES[idx]


def _classdefs(theme: dict) -> str:
    lines = []
    for cls, colors in theme.items():
        lines.append(f"    classDef {cls} fill:{colors['fill']},stroke:{colors['stroke']},color:#ffffff,stroke-width:2px;")
    return "\n".join(lines)


def _node_id(index: int) -> str:
    return f"N{index}"


def _label(node_id: str, name: str, style: str = "rect"):
    n = sanitize_label(name)
    if style == "db":
        return f"{node_id}[(\"{n}\")]"
    if style == "queue":
        return f"{node_id}{{\"{n}\"}}"
    return f"{node_id}[\"{n}\"]"


def build_diagrams(model: dict) -> dict:
    """Generate 3 levels of diagrams that always reflect the canonical model."""
    comps = ensure_list(model.get("architecture", {}).get("components"))
    domain = as_text(model.get("domain"))
    theme = _theme_for(model)
    by_type = {c.get("type"): c for c in comps}
    services = [c for c in comps if c.get("type") == "service"]
    client = by_type.get("client") or {"name": "Client"}
    gateway = by_type.get("gateway") or {"name": "API Gateway"}
    db = by_type.get("database") or {"name": "Database"}
    cache = by_type.get("cache")
    queue = by_type.get("queue")
    externals = [c for c in comps if c.get("type") == "external"]
    infra = [c for c in comps if c.get("type") == "infrastructure"]

    cd = _classdefs(theme)

    # ---------------- LEVEL 1: basic flow ----------------
    l1_ids = {}
    l1 = ["graph LR", cd]
    l1_ids["N1"] = client.get("name")
    l1_ids["N2"] = gateway.get("name")
    l1_ids["N3"] = services[0]["name"] if services else "Core Service"
    l1_ids["N4"] = db.get("name")
    l1.append(f"    {_node_id(1)}[\"{client.get('name')}\"]:::client")
    l1.append(f"    {_node_id(2)}[\"{gateway.get('name')}\"]:::gateway")
    core = services[0] if services else {"name": "Core Service"}
    l1.append(f"    {_node_id(3)}[\"{sanitize_label(core['name'])}\"]:::service")
    l1.append(f"    {_node_id(4)}[(\"{sanitize_label(db['name'])}\")]:::db")
    l1.append(f"    {_node_id(1)} -->|HTTPS| {_node_id(2)}")
    l1.append(f"    {_node_id(2)} -->|route| {_node_id(3)}")
    l1.append(f"    {_node_id(3)} -->|read/write| {_node_id(4)}")
    if cache:
        l1_ids["N5"] = cache["name"]
        l1.append(f"    {_node_id(5)}[(\"{sanitize_label(cache['name'])}\")]:::cache")
        l1.append(f"    {_node_id(3)} -.->|cache| {_node_id(5)}")
    l1_mermaid = "\n".join(l1)
    l1_ascii = (
        f"+------------+   +------------+   +------------+   +--------------+\n"
        f"|  {sanitize_label(client.get('name'))[:11]:^12} |-->| {sanitize_label(gateway.get('name'))[:11]:^12} |-->| {sanitize_label(core['name'])[:11]:^12} |-->| {sanitize_label(db['name'])[:13]:^14} |\n"
        f"+------------+   +------------+   +------------+   +--------------+\n"
    )

    # ---------------- LEVEL 2: structure ----------------
    l2 = ["graph TB", cd]
    ids = {"Client": _node_id(1), "API Gateway": _node_id(2)}
    l2_node_map = {"N1": client.get("name"), "N2": gateway.get("name")}
    l2.append(f"    {_node_id(1)}[\"{client.get('name')}\"]:::client")
    l2.append(f"    {_node_id(2)}[\"{gateway.get('name')}\"]:::gateway")
    l2.append(f"    {_node_id(1)} -->|HTTPS / WSS| {_node_id(2)}")
    node_index = 3
    for s in services:
        nid = _node_id(node_index)
        ids[s["name"]] = nid
        l2_node_map[nid] = s["name"]
        style_cls = NODE_TYPE_CLASS.get(s.get("type"), "service")
        l2.append(f"    {nid}[\"{sanitize_label(s['name'])}\"]:::{style_cls}")
        l2.append(f"    {_node_id(2)} -->|route| {nid}")
        node_index += 1
    db_id = _node_id(node_index)
    l2_node_map[db_id] = db["name"]
    l2.append(f"    {db_id}[(\"{sanitize_label(db['name'])}\")]:::db")
    for s in services:
        l2.append(f"    {ids[s['name']]} -->|persist| {db_id}")
    node_index += 1
    if cache:
        cid = _node_id(node_index)
        ids[cache["name"]] = cid
        l2_node_map[cid] = cache["name"]
        l2.append(f"    {cid}[(\"{sanitize_label(cache['name'])}\")]:::cache")
        l2.append(f"    {_node_id(2)} -.->|read-through| {cid}")
        node_index += 1
    if queue:
        qid = _node_id(node_index)
        ids[queue["name"]] = qid
        l2_node_map[qid] = queue["name"]
        l2.append(f"    {qid}{{\"{sanitize_label(queue['name'])}\"}}:::queue")
        for s in services:
            l2.append(f"    {ids[s['name']]} -->|publish| {qid}")
        node_index += 1
    for e in externals:
        eid = _node_id(node_index)
        ids[e["name"]] = eid
        l2_node_map[eid] = e["name"]
        l2.append(f"    {eid}[\"{sanitize_label(e['name'])}\"]:::external")
        first_service = services[0] if services else None
        if first_service and first_service["name"] in ids:
            l2.append(f"    {ids[first_service['name']]} -->|API calls| {eid}")
        else:
            l2.append(f"    {_node_id(2)} -->|API calls| {eid}")
        node_index += 1
    l2_mermaid = "\n".join(l2)
    for nid in l2_node_map:
        l2_mermaid += f"\n    click {nid} diagramNodeClick"
    l2_ascii = _ascii_l2(client, gateway, services, db, cache, queue, externals)

    # ---------------- LEVEL 3: production ----------------
    l3 = ["graph TB", cd]
    l3_node_map = {"N1": client.get("name"), "N2": gateway.get("name")}
    l3.append("    subgraph edge[\"Client Edge\"]")
    l3.append(f"      {_node_id(1)}[\"{client.get('name')}\"]:::client")
    l3.append("    end")
    l3.append("    subgraph access[\"Access & Security\"]")
    l3.append(f"      {_node_id(2)}[\"{gateway.get('name')}\"]:::gateway")
    l3.append("    end")
    l3.append(f"    {_node_id(1)} -->|HTTPS / WSS| {_node_id(2)}")
    l3.append("    subgraph app[\"Application Services\"]")
    l3_ids = {}
    app_ids = []
    ni = 3
    for s in services:
        nid = _node_id(ni)
        l3_ids[s["name"]] = nid
        l3_node_map[nid] = s["name"]
        style_cls = NODE_TYPE_CLASS.get(s.get("type"), "service")
        l3.append(f"      {nid}[\"{sanitize_label(s['name'])}\"]:::{style_cls}")
        l3.append(f"      {_node_id(2)} -->|route| {nid}")
        app_ids.append(nid)
        ni += 1
    l3.append("    end")
    if queue:
        qid = _node_id(ni)
        l3_node_map[qid] = queue["name"]
        l3.append(f"    {qid}{{\"{sanitize_label(queue['name'])}\"}}:::queue")
        for s in services:
            l3.append(f"    {l3_ids[s['name']]} -->|publish| {qid}")
        ni += 1
    db_id2 = _node_id(ni)
    l3_node_map[db_id2] = db["name"]
    l3.append(f"    {db_id2}[(\"{sanitize_label(db['name'])}\")]:::db")
    replica_id = _node_id(ni + 1)
    l3_node_map[replica_id] = "Read Replica"
    l3.append(f"    {db_id2} -->|replication| {replica_id}[(\"Read Replica\")]:::db")
    ni += 2
    if cache:
        cid2 = _node_id(ni)
        l3_node_map[cid2] = cache["name"]
        l3.append(f"    {cid2}[(\"{sanitize_label(cache['name'])}\")]:::cache")
        l3.append(f"    {_node_id(2)} -.->|read-through| {cid2}")
        ni += 1
    for s in services:
        l3.append(f"    {l3_ids[s['name']]} -->|persist| {db_id2}")
    if externals:
        l3.append("    subgraph ext[\"External Providers\"]")
        for e in externals:
            eid = _node_id(ni)
            l3_node_map[eid] = e["name"]
            l3.append(f"      {eid}[\"{sanitize_label(e['name'])}\"]:::external")
            ni += 1
        l3.append("    end")
        for e in externals:
            eid = _node_id(ni - len(externals) + externals.index(e))
            l3.append(f"    {app_ids[0] if app_ids else _node_id(2)} -->|signed API calls| {eid}")
    if infra:
        l3.append("    subgraph obs[\"Observability\"]")
        for it in infra:
            iid = _node_id(ni)
            l3_node_map[iid] = it["name"]
            l3.append(f"      {iid}[\"{sanitize_label(it['name'])}\"]:::infra")
            ni += 1
        l3.append("    end")
    for nid in l3_node_map:
        l3.append(f"    click {nid} diagramNodeClick")
    l3_mermaid = "\n".join(l3)
    l3_ascii = _ascii_l2(client, gateway, services, db, cache, queue, externals)

    l1_mermaid += "\n"
    for nid, name in l1_ids.items():
        l1_mermaid += f"    click {nid} diagramNodeClick\n"

    level_meta = [
        {
            "title": "Level 1 - Basic Flow",
            "description": "The simplest view: how a request travels from client to database.",
            "mermaid": l1_mermaid, "ascii": l1_ascii, "node_map": l1_ids,
        },
        {
            "title": "Level 2 - Component Structure",
            "description": "All internal services, cache, queue, database and external providers.",
            "mermaid": l2_mermaid, "ascii": l2_ascii, "node_map": l2_node_map,
        },
        {
            "title": "Level 3 - Production Deployment",
            "description": "Full production topology with access/security, replicas, external providers and observability.",
            "mermaid": l3_mermaid, "ascii": l3_ascii, "node_map": l3_node_map,
        },
    ]

    return {
        "level1": level_meta[0],
        "level2": level_meta[1],
        "level3": level_meta[2],
        # Backwards-compatible top-level diagram (used by legacy consumers).
        "legacy": {"mermaid": l2_mermaid, "ascii": l2_ascii},
    }


def _ascii_l2(client, gateway, services, db, cache, queue, externals) -> str:
    lines = [
        f"+----------------+    +----------------+",
        f"| {sanitize_label(client.get('name'))[:15]:^16} | -> | {sanitize_label(gateway.get('name'))[:15]:^16} |",
        f"+----------------+    +----------------+",
        "                              |",
        "            +-----------------+-----------------+",
    ]
    svc_rows = []
    for s in services:
        svc_rows.append(f"| {sanitize_label(s['name'])[:17]:^19} |")
    if svc_rows:
        lines.append("            " + "    ".join(svc_rows))
        lines.append("            +-------------------+    " * len(svc_rows))
    db_label = sanitize_label(db.get('name'))
    lines.append(f"                 |  {db_label[:28]:^30}  |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Explanation modes (story + ELI5 decoder + brief/long/detailed)
# ---------------------------------------------------------------------------

def _num(value):
    """Render a numeric throughput value for prose, falling back to 'moderate'."""
    if value is None:
        return "moderate"
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return "moderate"


def _flow_components(model: dict) -> list:
    """Component names in the order a request flows through them."""
    comps = ensure_list(model.get("architecture", {}).get("components"))
    by_type = lambda t: [c for c in comps if c.get("type") == t]
    order = []
    if by_type("gateway"):
        order.append(by_type("gateway")[0]["name"])
    for c in by_type("service"):
        order.append(c["name"])
    if by_type("cache"):
        order.append(by_type("cache")[0]["name"])
    if by_type("queue"):
        order.append(by_type("queue")[0]["name"])
    for c in comps:
        if c.get("type") in ("database", "datastore", "storage"):
            order.append(c["name"])
    for c in comps:
        if c.get("type") == "external":
            order.append(c["name"])
    seen = set()
    out = []
    for n in order:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def build_explanation_modes(model: dict) -> dict:
    """Build detailed, grounded story / ELI5 / brief / long / detailed narratives."""
    domain = model.get("domain", "General")
    arch = ensure_dict(model.get("architecture", {}))
    pattern = as_text(arch.get("pattern")) or "a single deployable system"
    components = ensure_list(arch.get("components"))
    workload = ensure_dict(model.get("performance", {}).get("workload"))
    db_type = as_text(model.get("database", {}).get("database_type")) or "a database"
    api_protocol = as_text(model.get("api", {}).get("protocol")) or "HTTPS"
    system_type = as_text(arch.get("system_type")) or f"{domain} Architecture"

    comps = [c for c in components if c.get("type") == "service"]
    names = ", ".join(sanitize_label(c["name"]) for c in comps[:3]) or "the core service"
    entry = _flow_components(model)
    first_hop = entry[0] if entry else "the client"
    db_name = next((c["name"] for c in components if c.get("type") in ("database", "datastore")), "the database")
    cache_name = next((c["name"] for c in components if c.get("type") == "cache"), None)
    queue_name = next((c["name"] for c in components if c.get("type") == "queue"), None)
    ext_names = [c["name"] for c in components if c.get("type") == "external"]
    has_cache = cache_name is not None
    has_queue = queue_name is not None
    avg = workload.get("avg_requests_per_second")
    peak = workload.get("peak_requests_per_second")
    score = workload.get("complexity_score")
    users = workload.get("users")

    brief = (
        f"**{domain} Architecture:** uses **{pattern}** with {len(comps)} core service(s) "
        f"({names}) and **{db_type}** as the system of record. "
        f"Modeled for {_num(avg)} req/s average and {_num(peak)} req/s peak."
    )

    long = (
        f"**{pattern}** was selected because the complexity score "
        f"({_num(score)}/100) does not justify a heavier topology.\n\n"
        + "\n".join([f"- **{c['name']}** (`{c['technology']}`): {c['responsibility']}" for c in comps[:5]])
        + f"\n\n**Persistence:** {db_type}. **Cache:** {'Redis read-through.' if has_cache else 'Not required at this scale.'}"
        + f" Peak throughput: {_num(peak)} req/s."
    )

    detailed = (
        f"# {domain} Architecture - Full Specification\n\n"
        f"## Pattern\n**{pattern}**\n\n"
        f"## Components\n"
        + "\n".join([f"### {c['name']}\n- **Type:** {c['type']}\n- **Technology:** {c['technology']}\n- **Responsibility:** {c['responsibility']}\n- **Internal/External:** {c['internal_or_external']}" for c in components])
        + f"\n\n## Data Layer\n**{db_type}**"
    )

    # ---- Detailed plain-language story --------------------------------------
    cache_line = (
        f"4. Before touching the database, the **{cache_name}** is checked. If the data was "
        f"read recently it is returned instantly from memory — think of it as the receptionist "
        f"who remembers your name so you don't have to fill in a form every visit. If it is not "
        f"there (a 'cache miss'), the request falls through to the database and the answer is "
        f"remembered for next time.\n"
        if has_cache else ""
    )
    queue_line = (
        f"5. Anything that is slow but not urgent — sending an email, generating a report, "
        f"processing a payment settlement — is dropped into the **{queue_name}** instead of "
        f"blocking the user. A background worker picks the task up when it has capacity, so the "
        f"user gets an instant 'we're on it' response while the heavy lifting happens out of sight.\n"
        if has_queue else ""
    )
    ext_line = (
        f"6. If the request needs a real-world service — like **{', '.join(ext_names[:3])}** — "
        f"the system calls out to that provider. These calls are the riskiest part of the journey "
        f"because you do not control the other side, so they are wrapped in timeouts, retries and "
        f"circuit breakers: if the provider is slow or down, the system fails fast instead of "
        f"hanging the user's request.\n"
        if ext_names else ""
    )
    failure_line = (
        f"7. Nothing is perfect, so every hop has a fallback plan. The **{db_name}** is the "
        f"source of truth and is backed up; the cache can be bypassed harmlessly (a miss just "
        f"means a slower read); and if a service is unhealthy, the gateway stops sending it "
        f"traffic and directs requests to a healthy copy. The design trades a tiny bit of "
        f"complexity for the guarantee that one failing part cannot take the whole system down.\n"
    )
    scale_line = (
        f"8. When traffic grows, the bottlenecks are known in advance: the services and the "
        f"database are the two places to watch. Services can be scaled by running more copies "
        f"behind the gateway, and reads are offloaded through the cache and read replicas so the "
        f"database is only written once. Peak load is modeled at {_num(peak)} req/s"
        f"{f' for ~{int(users):,} users' if users else ''}.\n"
    )
    story = (
        f"**How the {domain} system works — plain language**\n\n"
        f"Imagine walking into a large office building. **{system_type}** is built on a "
        f"**{pattern}** topology, and every request from a user takes the same journey. Here is "
        f"that journey from the moment the user taps a button to the moment they see the result.\n\n"
        f"**1. The front door.** The user's browser or mobile app talks to **{first_hop}** over "
        f"{api_protocol}. This is the only door into the building: it checks who you are "
        f"(authentication), makes sure you are allowed to do what you asked (authorization), and "
        f"then lets you in. Nothing reaches the rest of the system without passing this checkpoint.\n"
        f"**2. Finding the right specialist.** The door doesn't do the work itself — it looks at "
        f"your request and routes it to the specialist that can handle it: {names}. Each "
        f"specialist owns one slice of the business, so the logic for that feature lives in one "
        f"place and can change without touching the others.\n"
        f"**3. Reading and writing the truth.** Specialists keep state in **{db_type}** "
        f"(**{db_name}**). This is the system of record — the one place that always holds the "
        f"correct, complete copy of the data.\n"
        + cache_line
        + queue_line
        + ext_line
        + failure_line
        + scale_line
        +         f"**The whole point.** Every layer above exists to make one guarantee: the user gets a "
        f"correct answer, quickly, even when traffic spikes, a provider stalls, or a server "
        f"dies. The **{pattern}** shape (with {len(components)} components) is the cheapest "
        f"design that still delivers that guarantee at {_num(avg)} req/s average / {_num(peak)} "
        f"req/s peak."
    )

    terms = [
        {"term": "API Gateway", "symbol": "(Shield)", "meaning": "The single front door every request passes through. It authenticates the caller, checks permissions, rate-limits traffic, and routes each request to the right service. Nothing else is reachable from the internet, so it is also the natural place to add monitoring, logging and throttling.", "analogy": "Airport security checkpoint: one queue, ID checked once, then you are guided to the correct gate."},
        {"term": "Service / Component", "symbol": "(Box)", "meaning": "A self-contained piece of the business logic with one clear job (e.g. handling orders, sending notifications). It owns its data and exposes a small set of operations; other parts of the system talk to it, never reaching inside it.", "analogy": "A specialist department: accounting never redoes what shipping already did — it just hands work over."},
        {"term": "Cache", "symbol": "(Cylinder)", "meaning": "A fast in-memory copy of data that is read often. The system checks the cache before the database; a hit returns instantly, a miss falls through to the database and then the answer is stored for next time. This cuts database load dramatically at peak.", "analogy": "A cheat-sheet on your desk instead of walking to the library every time someone asks the same question."},
        {"term": "Database", "symbol": "((DB))", "meaning": "The durable system of record that holds every piece of committed data, survives restarts and failures, and guarantees consistency through transactions. Every service reads and writes its data here; backups protect it from loss.", "analogy": "A bank vault: the single, authoritative copy of the truth that everyone consults."},
        {"term": "Queue", "symbol": "{}", "meaning": "A staging area for work that does not need to finish before the user gets a reply. The system publishes a task and a background worker consumes it when ready. This smooths out bursts of work and prevents slow side-effects (emails, exports, notifications) from blocking the main request.", "analogy": "A post-office sorting line: you drop the parcel, you don't wait for it to be delivered."},
        {"term": "External Provider", "symbol": "(Cloud)", "meaning": "A third-party system the architecture calls — payments, identity, email, push notifications. Because you don't control it, calls are wrapped in timeouts, retries and circuit breakers so a slow provider can't stall your own system.", "analogy": "A courier company: you hand the parcel over, and you only wait a fixed amount of time before giving up."},
        {"term": "Load Balancer", "symbol": "(<> —)", "meaning": "A distributor that spreads incoming requests across several copies of a service so no single server is overloaded, and so traffic can be rerouted away from a server that has just failed.", "analogy": "A restaurant host splitting diners between several waiters so nobody is stuck waiting."},
        {"term": "Authentication vs Authorization", "symbol": "(ID card)", "meaning": "Authentication proves who you are (your username and password, or token). Authorization decides what you are allowed to do once we know who you are (view, edit, admin). Both must happen before the gateway lets a request through.", "analogy": "A passport proves your identity; a visa decides which countries you may actually enter."},
        {"term": "Horizontal Scaling", "symbol": "(x2 boxes)", "meaning": "Running more copies of a service behind a load balancer to serve more traffic. It works because requests are independent — no single machine becomes a bottleneck. The database is the one part that cannot be trivially copied, which is why caching and read replicas matter.", "analogy": "Adding more checkout counters when the store gets busy instead of making one counter faster."},
        {"term": "Circuit Breaker", "symbol": "(✂ line)", "meaning": "A safety switch that stops sending requests to a failing dependency after enough errors. It lets the dependency recover, and the system fails fast (or serves a cached fallback) instead of piling up timeouts.", "analogy": "A power breaker that cuts the circuit before a shorted wire starts a fire."},
        {"term": "Read Replica", "symbol": "((DB) copy)", "meaning": "A live copy of the database that serves read-only traffic. Writes go to the primary; reads fan out to replicas. This increases read capacity with a tiny delay on the copies.", "analogy": "Photocopies of the master ledger for the front desk, while the original stays safe in the office."},
        {"term": "Idempotency", "symbol": "(↻ repeat-safe)", "meaning": "Making an operation safe to repeat: if the same request arrives twice (a retry, a double-click), the system detects it and applies the change only once. Essential for payments and any action with real-world consequences.", "analogy": "Pressing the elevator button twice still gets you to the same floor, once."},
    ]

    analogies = [
        {"concept": "Monolith vs Microservices", "explanation": "A monolith is one workshop doing everything under one roof — simple to build and run, but every change touches the whole building. Microservices are specialist teams in separate buildings connected by a network — each can change, scale and fail independently, but you pay in coordination and operational cost. You only build separate buildings when traffic justifies the extra coordination cost."},
        {"concept": "Read replicas", "explanation": "One writer updates the master copy while photocopies serve readers — faster reads, with a tiny delay on the copies."},
        {"concept": "Synchronous vs asynchronous", "explanation": "A synchronous call waits for the answer before continuing — like phoning a restaurant to book a table. An asynchronous call drops a task into a queue and continues — like sending an email; the reply arrives when the other side gets to it. Queues turn slow, bursty work into steady background work."},
    ]
    return {
        "story": story, "brief": brief, "long": long, "detailed": detailed,
        "terms": terms, "analogies": analogies,
    }


# ---------------------------------------------------------------------------
# Alternative architectures (2-tier, 3-tier, current) with detailed flows
# ---------------------------------------------------------------------------

def build_alternatives(model: dict) -> list:
    """Candidate architectures for the same business problem, each with a detailed flow."""
    domain = model.get("domain", "General")
    arch = ensure_dict(model.get("architecture", {}))
    pattern = as_text(arch.get("pattern")) or "Monolithic Architecture"
    components = ensure_list(arch.get("components"))
    workload = ensure_dict(model.get("performance", {}).get("workload"))
    db_type = as_text(model.get("database", {}).get("database_type")) or "a relational database"
    api_protocol = as_text(model.get("api", {}).get("protocol")) or "HTTPS"
    avg = workload.get("avg_requests_per_second")
    peak = workload.get("peak_requests_per_second")
    users = workload.get("users")
    peak_label = f"{peak:g} req/s" if peak else "moderate"
    avg_label = f"{avg:g} req/s" if avg else "moderate"

    services = [c for c in components if c.get("type") == "service"]
    gateway = next((c for c in components if c.get("type") == "gateway"), None)
    cache_name = next((c["name"] for c in components if c.get("type") == "cache"), "a cache")
    db_name = next((c["name"] for c in components if c.get("type") in ("database", "datastore")), "Primary Database")
    ext_names = [c["name"] for c in components if c.get("type") == "external"]

    # ---- Current / recommended pattern --------------------------------------
    current_flow = [
        f"User taps an action in the browser or mobile app; the client opens a secure {api_protocol} connection.",
    ]
    if gateway:
        current_flow.append(
            f"The request arrives at **{gateway['name']}** — the only internet-facing entry point. "
            f"It authenticates the caller, checks the permission, applies rate limits, and records the request."
        )
    if services:
        route_names = ", ".join(sanitize_label(c["name"]) for c in services[:4])
        current_flow.append(
            f"The gateway routes the request to the responsible specialist ({route_names}). "
            f"The specialist runs the business rules for that feature — validation, calculations, and "
            f"any state changes."
        )
    if any(c.get("type") == "cache" for c in components):
        current_flow.append(
            f"Before any slow work, the **{cache_name}** is checked. On a hit the specialist returns "
            f"the answer immediately; on a miss it reads from the database and stores the result for later."
        )
    current_flow.append(
        f"The specialist reads or writes durable state in **{db_name}** ({db_type}) using short, "
        f"atomic transactions so the data always stays consistent even if a step fails midway."
    )
    if any(c.get("type") == "queue" for c in components):
        current_flow.append(
            f"Side-effects that don't need to finish before the reply — emails, exports, analytics — "
            f"are published to the message queue and processed asynchronously by background workers."
        )
    if ext_names:
        current_flow.append(
            f"When a real-world service is required ({', '.join(ext_names[:3])}), the system calls the "
            f"provider with timeouts, retries and a circuit breaker so a slow provider can't block the user."
        )
    current_flow.append(
        f"The response flows back the same way, and the gateway returns it to the user — typically in "
        f"tens of milliseconds, even at {avg_label} average / {peak_label} peak."
    )
    current = {
        "key": pattern.lower().replace(" ", "_"),
        "name": pattern,
        "recommended": True,
        "description": (
            f"The design selected for this problem: **{pattern}** with {len(components)} components. "
            f"It is the cheapest topology that meets the modeled workload ({avg_label} avg / {peak_label} "
            f"peak), balancing build cost, operational burden and headroom for growth."
        ),
        "flow": current_flow,
        "components": [
            {"name": c["name"], "type": c["type"], "technology": c["technology"], "responsibility": c["responsibility"]}
            for c in components
        ],
        "pros": [
            "Reflects the actual workload and constraints computed for this problem.",
            "Single, consistent data flow that every other option is measured against.",
            "Backed by the decisions, validation and reviewer pass in the model.",
        ],
        "cons": [
            "Any change must be planned against this specific topology (see alternatives below).",
        ],
        "when_to_use": "Keep this design as the baseline; revisit it only if scale or requirements change materially.",
    }

    # ---- 2-Tier (Client-Server) ----------------------------------------------
    two_tier = {
        "key": "two_tier",
        "name": "2-Tier Architecture (Client-Server)",
        "recommended": False,
        "description": (
            "The simplest possible shape: two tiers. The **client tier** (browser or mobile app) and a "
            "single **server tier** that runs all business logic *and* hosts the database in one process. "
            "Great for prototypes, internal tools, and low-concurrency line-of-business apps where speed of "
            "delivery matters more than scale."
        ),
        "flow": [
            "User performs an action in the **Client** (browser/mobile).",
            "The client opens a direct connection to the **Application + Database Server** over the LAN or VPN — there is no separate gateway or load balancer tier.",
            "The server validates the request, runs the business rules, and applies the change.",
            "The same process writes the result to the embedded **database** ({db_type}) and returns the response in the same call.",
            "Because everything lives in one process, there is exactly one network hop — extremely low latency and near-zero infrastructure to operate.",
            "If the single server is down, the whole application is down: availability depends on one machine (backups and restarts are the safety net).",
        ],
        "components": [
            {"name": "Client (Browser / Mobile App)", "type": "client", "technology": "Web / Mobile", "responsibility": "Renders the UI and talks to the server directly."},
            {"name": "Application + Database Server", "type": "server", "technology": "App runtime + DB engine", "responsibility": "All business logic and the database engine run in one deployable process."},
            {"name": "Embedded Database", "type": "database", "technology": db_type, "responsibility": "Durable storage co-located with the application."},
        ],
        "pros": [
            "Fewest moving parts: one deployment, one process to monitor, one place to debug.",
            "Lowest latency because client and data are at most one hop apart.",
            "Cheapest to build and host; ideal when the team is small or the product is new.",
        ],
        "cons": [
            "No isolation: a bug in business logic can take the database down and vice-versa.",
            "Scaling means scaling one big process — you can't scale reads separately from writes.",
            f"At the modeled {avg_label} avg / {peak_label} peak this single process becomes the bottleneck and a single point of failure.",
        ],
        "when_to_use": "Internal tools, admin panels, prototypes, and apps with under a few hundred concurrent users and no SLA for zero downtime.",
    }

    # ---- 3-Tier (Presentation / Application / Data) --------------------------
    three_tier = {
        "key": "three_tier",
        "name": "3-Tier Architecture (Presentation / Application / Data)",
        "recommended": False,
        "description": (
            "The classic enterprise shape: the client talks to a **presentation tier** (web server / static "
            "front-end plus the API edge), which calls a separate **application tier** holding the business "
            "logic, which finally reaches the **data tier** (database, cache, storage). Each tier is deployed "
            "and scaled independently — the sweet spot for medium-load applications before full microservices."
        ),
        "flow": [
            "User's browser loads the UI from the **Presentation Tier** (web server / CDN).",
            "The UI calls the **API layer** in the presentation tier over {api_protocol}; the API authenticates the caller and enforces rate limits.",
            "The API layer forwards the request to the **Application Tier** — a stateless business-logic service — which can be run in several copies behind a load balancer.",
            "The application tier checks the **cache** first ({cache_name}); on a miss it reads/writes the **data tier** ({db_name}, {db_type}) inside a transaction.",
            "Long-running or background work (reports, notifications) is handed to a worker queue so the request returns immediately.",
            "The data tier returns the result up the chain: application tier → API → user.",
            "Each tier scales on its own axis: more web nodes for traffic, more application replicas for CPU-bound logic, and read replicas / cache for database pressure.",
        ],
        "components": [
            {"name": "Client", "type": "client", "technology": "Browser / Mobile", "responsibility": "Renders UI and calls the presentation tier."},
            {"name": "Presentation Tier (Web + API)", "type": "presentation", "technology": "Web server / CDN + API", "responsibility": "Serves the UI, authenticates requests, enforces rate limits, and proxies to the application tier."},
            {"name": "Application Tier (Business Logic)", "type": "application", "technology": "Stateless app service", "responsibility": "Runs the business rules; scales horizontally behind a load balancer."},
            {"name": "Cache", "type": "cache", "technology": "Redis", "responsibility": "Offloads hot reads from the data tier."},
            {"name": "Data Tier (Database)", "type": "database", "technology": db_type, "responsibility": "System of record with read replicas for scale."},
        ],
        "pros": [
            "Separation of concerns: UI, business logic and data each change and deploy independently.",
            "Stateless application tier scales horizontally simply by adding replicas.",
            "Fits medium workloads and is a natural stepping stone to microservices later.",
        ],
        "cons": [
            "More components to operate than 2-tier: load balancers, API servers, app servers, replicas.",
            "More network hops mean higher latency than 2-tier for the same data.",
            f"At {avg_label} avg / {peak_label} peak it comfortably copes, but beyond that you'd partition into microservices.",
        ],
        "when_to_use": "Web products with a real user base, shared databases, medium concurrency, and a small ops team that still wants clean scaling.",
    }

    return [current, two_tier, three_tier]


# ---------------------------------------------------------------------------
# Deep-dive overview ("everything explained" for the Overview tab)
# ---------------------------------------------------------------------------

def build_deep_overview(model: dict) -> list:
    """A guided, plain-language walkthrough of every facet of the design."""
    domain = model.get("domain", "General")
    arch = ensure_dict(model.get("architecture", {}))
    reqs = ensure_dict(model.get("requirements", {}))
    db = ensure_dict(model.get("database", {}))
    api = ensure_dict(model.get("api", {}))
    sec = ensure_dict(model.get("security", {}))
    dep = ensure_dict(model.get("deployment", {}))
    perf = ensure_dict(model.get("performance", {}))
    workload = ensure_dict(perf.get("workload", {}))
    review = ensure_dict(model.get("review", {}))
    components = ensure_list(arch.get("components"))
    pattern = as_text(arch.get("pattern")) or "a single deployable system"
    db_type = as_text(db.get("database_type")) or "a relational database"
    score = review.get("overall_score")
    peak = workload.get("peak_requests_per_second")
    avg = workload.get("avg_requests_per_second")
    complexity = workload.get("complexity_score")

    sections = []

    # 1. Executive summary ----------------------------------------------------
    sections.append({
        "key": "summary",
        "title": "What this system is — at a glance",
        "icon": "book",
        "paragraphs": [
            f"This analysis designs **{as_text(arch.get('system_type')) or f'{domain} Architecture'}** for the problem: "
            f"*“{as_text(model.get('business_problem'))}”*. The recommended shape is **{pattern}** with "
            f"{len(components)} components and **{db_type}** as the system of record.",
            f"It is sized for **{_num(avg)} req/s average** and **{_num(peak)} req/s peak** "
            f"{f'across ~{int(workload["users"]):,} users' if workload.get('users') else ''}. "
            f"Every number below was calculated from the problem statement, not guessed, and the design was reviewed "
            f"and scored" + (f" at **{int(score)}/100**" if score is not None else "") + ".",
        ],
    })

    # 2. Workload & scale -----------------------------------------------------
    wl = [
        f"The load model is the foundation of every choice: it determines how big the system has to be. "
        f"Throughput is **{_num(avg)} req/s on average** and **{_num(peak)} req/s at peak**.",
        f"This complexity of **{_num(complexity)}/100** is the key driver — it is what decides whether a simple "
        f"monolith, a modular monolith, microservices or an event-driven design is appropriate. The mapping is: "
        f"under 25 → monolith; 25–50 → modular monolith; 50–75 → microservices; 75+ → event-driven.",
    ]
    if workload.get("users"):
        wl.append(f"The model assumes roughly **{int(workload['users']):,} users**, which drives the expected "
                  f"concurrency of **{_num(workload.get('expected_concurrency'))}** simultaneous requests.")
    if workload.get("assumptions"):
        wl.append("Stated assumptions: " + "; ".join(
            as_text(a.get("text")) if isinstance(a, dict) else as_text(a) for a in workload["assumptions"][:5]) + ".")
    sections.append({"key": "workload", "title": "Scale, explained", "icon": "zap", "paragraphs": wl})

    # 3. Architecture pattern -------------------------------------------------
    sections.append({
        "key": "pattern",
        "title": "The architecture pattern, explained",
        "icon": "git",
        "paragraphs": [
            f"The system uses a **{pattern}** topology." + (f" Its style is **{as_text(arch.get('style'))}**." if as_text(arch.get('style')) else ""),
            f"**Why this pattern?** {as_text(arch.get('justification')) or 'Chosen to match the computed workload while keeping operations simple.'}",
            f"The pattern dictates how components communicate (synchronous calls vs. an event bus), how they are "
            f"deployed (one process vs. many services), and how they scale. It is the highest-leverage decision in "
            f"the whole design, which is why the reviewer scores it separately.",
        ],
    })

    # 4. Components -----------------------------------------------------------
    comp_lines = []
    for c in components:
        name = as_text(c.get("name")) or "Component"
        tech = as_text(c.get("technology")) or "To be defined"
        resp = as_text(c.get("responsibility")) or "No responsibility recorded."
        kind = as_text(c.get("internal_or_external")) or "internal"
        parts = f"- **{name}** (`{tech}`, {kind}): {resp}."
        if as_text(c.get("scaling_strategy")):
            parts += f" Scaling: {as_text(c.get('scaling_strategy'))}."
        if as_text(c.get("failure_behavior")):
            parts += f" Failure handling: {as_text(c.get('failure_behavior'))}."
        comp_lines.append(parts)
    sections.append({
        "key": "components",
        "title": f"Every component, explained ({len(components)})",
        "icon": "server",
        "paragraphs": (
            ["Each component is one job with its own technology. Read them as a story: the gateway receives, the "
             "services decide, the cache accelerates, the queue absorbs bursts, and the database remembers."]
            + comp_lines
        ),
    })

    # 5. Data layer -----------------------------------------------------------
    data_paras = [
        f"The system of record is **{db_type}**. {as_text(db.get('justification')) or ''}".strip(),
    ]
    if as_text(db.get("transactions")):
        data_paras.append(f"**Transactions:** {as_text(db.get('transactions'))}")
    if as_text(db.get("caching_layer")):
        data_paras.append(f"**Caching:** {as_text(db.get('caching_layer'))}")
    if as_text(db.get("sharding")):
        data_paras.append(f"**Sharding:** {as_text(db.get('sharding'))}")
    if as_text(db.get("migrations")):
        data_paras.append(f"**Migrations:** {as_text(db.get('migrations'))}")
    idx = ensure_list(db.get("indexing_strategies"))
    if idx:
        data_paras.append("**Indexing:** " + " ".join(as_text(i) for i in idx[:4]))
    n_schemas = len(ensure_list(db.get("schemas")))
    if n_schemas:
        data_paras.append(f"**Schema:** {n_schemas} table definition(s) are generated (see the Database tab) that "
                          f"capture the core entity, an audit trail, and (where needed) an outbox for reliable events.")
    sections.append({"key": "data", "title": "Data layer, explained", "icon": "database", "paragraphs": data_paras})

    # 6. API layer ------------------------------------------------------------
    api_paras = [f"All clients talk to the system over **{as_text(api.get('protocol')) or 'REST HTTP / JSON'}**."]
    if as_text(api.get("authentication_strategy")):
        api_paras.append(f"**Authentication:** {as_text(api.get('authentication_strategy'))}")
    eps = ensure_list(api.get("endpoints"))
    if eps:
        ep_names = [as_text(e.get("path")) if isinstance(e, dict) else as_text(e) for e in eps[:8]]
        api_paras.append(f"**Endpoints:** {len(eps)} defined, including " + ", ".join(f"`{n}`" for n in ep_names) + ".")
    if as_text(api.get("rate_limits")):
        api_paras.append(f"**Rate limiting:** {as_text(api.get('rate_limits'))}")
    if as_text(api.get("versioning")):
        api_paras.append(f"**Versioning:** {as_text(api.get('versioning'))}")
    if as_text(api.get("error_handling")):
        api_paras.append(f"**Error handling:** {as_text(api.get('error_handling'))}")
    if as_text(api.get("idempotency")):
        api_paras.append(f"**Idempotency:** {as_text(api.get('idempotency'))}")
    sections.append({"key": "api", "title": "API layer, explained", "icon": "api", "paragraphs": api_paras})

    # 7. Security -------------------------------------------------------------
    sec_paras = []
    if as_text(sec.get("authentication_strategy")):
        sec_paras.append(f"**Authentication:** {as_text(sec.get('authentication_strategy'))}")
    if as_text(sec.get("authorization")):
        sec_paras.append(f"**Authorization:** {as_text(sec.get('authorization'))}")
    if as_text(sec.get("data_protection")):
        sec_paras.append(f"**Data protection:** {as_text(sec.get('data_protection'))}")
    if as_text(sec.get("compliance")):
        sec_paras.append(f"**Compliance:** {as_text(sec.get('compliance'))}")
    sec_scores = ensure_dict(sec.get("scores"))
    if sec_scores:
        sec_paras.append("**Security posture:** " + ", ".join(
            f"{k.replace('_', ' ').title()} {v}/100" for k, v in sec_scores.items()) + ".")
    mitigations = ensure_list(sec.get("vulnerability_mitigations"))
    if mitigations:
        sec_paras.append("**Mitigations:** " + " ".join(as_text(m) for m in mitigations[:6]))
    tm = ensure_list(sec.get("threat_model"))
    if tm:
        sec_paras.append("**Threat model:** " + "; ".join(as_text(t) for t in tm[:6]))
    if not sec_paras:
        sec_paras.append("No dedicated security posture was recorded — treat security review as pending.")
    sections.append({"key": "security", "title": "Security, explained", "icon": "shield", "paragraphs": sec_paras})

    # 8. Deployment -----------------------------------------------------------
    dep_paras = [f"The system is hosted on **{as_text(dep.get('provider')) or 'a cloud provider'}**."]
    if ensure_list(dep.get("regions")):
        dep_paras.append("**Regions:** " + ", ".join(as_text(r) for r in dep["regions"]) + ".")
    if as_text(dep.get("orchestration")):
        dep_paras.append(f"**Orchestration:** {as_text(dep.get('orchestration'))}")
    if as_text(dep.get("scaling_policy")):
        dep_paras.append(f"**Scaling policy:** {as_text(dep.get('scaling_policy'))}")
    if as_text(dep.get("disaster_recovery")):
        dep_paras.append(f"**Disaster recovery:** {as_text(dep.get('disaster_recovery'))}")
    if as_text(dep.get("ci_cd")):
        dep_paras.append(f"**CI/CD:** {as_text(dep.get('ci_cd'))}")
    if as_text(dep.get("infrastructure_as_code")):
        dep_paras.append(f"**Infrastructure as code:** {as_text(dep.get('infrastructure_as_code'))} manifests are "
                         f"generated so the environment is reproducible.")
    sections.append({"key": "deployment", "title": "Deployment, explained", "icon": "deploy", "paragraphs": dep_paras})

    # 9. Performance ----------------------------------------------------------
    perf_paras = []
    bn = ensure_list(perf.get("bottlenecks"))
    if bn:
        perf_paras.append("**Predicted bottlenecks:** " + "; ".join(as_text(b) for b in bn))
    if as_text(perf.get("database_pressure")):
        perf_paras.append(f"**Database pressure:** {as_text(perf.get('database_pressure'))}")
    if as_text(perf.get("cache_requirements")):
        perf_paras.append(f"**Cache requirements:** {as_text(perf.get('cache_requirements'))}")
    if as_text(perf.get("queue_requirements")):
        perf_paras.append(f"**Queue requirements:** {as_text(perf.get('queue_requirements'))}")
    if as_text(perf.get("scaling_requirements")):
        perf_paras.append(f"**Scaling requirements:** {as_text(perf.get('scaling_requirements'))}")
    recs = ensure_list(perf.get("recommendations"))
    if recs:
        rec_lines = []
        for r in recs:
            if isinstance(r, dict):
                rec_lines.append(f"- **{as_text(r.get('recommendation'))}**: {as_text(r.get('reason'))}")
            else:
                rec_lines.append(f"- {as_text(r)}")
        perf_paras.append("**Recommendations to reach target latency:**\n" + "\n".join(rec_lines))
    if not perf_paras:
        perf_paras.append("No performance tuning notes were recorded.")
    sections.append({"key": "performance", "title": "Performance, explained", "icon": "zap", "paragraphs": perf_paras})

    # 10. Review score --------------------------------------------------------
    rev_paras = []
    if score is not None:
        rev_paras.append(f"The reviewer scored this design **{int(score)}/100**. The categories it checks are "
                         f"requirement coverage, scalability, reliability, security, performance, cost and "
                         f"complexity justification — so the score is a weighted judgment of whether the design "
                         f"matches the problem.")
    cats = ensure_dict(review.get("categories"))
    if cats:
        rev_paras.append("**Category scores:** " + "; ".join(
            f"{k.replace('_', ' ').title()} {int(v)}/100" for k, v in sorted(cats.items())) + ".")
    if ensure_list(review.get("critical_issues")):
        rev_paras.append("**Critical issues the reviewer flagged:** " + " ".join(
            f"- {as_text(i)}" for i in review["critical_issues"]))
    if ensure_list(review.get("warnings")):
        rev_paras.append("**Warnings:** " + " ".join(f"- {as_text(w)}" for w in review["warnings"]))
    if ensure_list(review.get("recommendations")):
        rev_paras.append("**What to do next:** " + " ".join(f"- {as_text(r)}" for r in review["recommendations"]))
    sections.append({"key": "review", "title": "Why the design scores what it does", "icon": "check", "paragraphs": rev_paras})

    # 11. Risks & failure scenarios -------------------------------------------
    risk_paras = []
    fs = ensure_list(model.get("failure_scenarios"))
    if fs:
        risk_paras.append("**Failure scenarios the design plans for:**")
        for f in fs:
            if isinstance(f, dict):
                risk_paras.append(f"- **{as_text(f.get('scenario') or f.get('component'))}**: {as_text(f.get('impact') or f.get('description'))}. Mitigation: {as_text(f.get('mitigation') or f.get('strategy') or 'documented')}.")
            else:
                risk_paras.append(f"- {as_text(f)}")
    rs = ensure_list(model.get("risks"))
    if rs:
        risk_paras.append("**Residual risks:**")
        for r in rs:
            if isinstance(r, dict):
                risk_paras.append(f"- **{as_text(r.get('risk') or r.get('title'))}**: {as_text(r.get('mitigation') or r.get('detail') or '')}")
            else:
                risk_paras.append(f"- {as_text(r)}")
    if not risk_paras:
        risk_paras.append("No explicit failure scenarios were recorded.")
    sections.append({"key": "risks", "title": "Risks & failure handling, explained", "icon": "alert", "paragraphs": risk_paras})

    # 12. Requirements summary -------------------------------------------------
    func = ensure_list(reqs.get("functional"))
    nfr = ensure_list(reqs.get("non_functional"))
    req_paras = [f"The analysis captured **{len(func)} functional requirement(s)** and **{len(nfr)} non-functional "
                 f"requirement(s)** (see the Requirements tab for the full list)."]
    if func:
        req_paras.append("**The top functional requirements:** " + " ".join(
            f"- {reqTextInline(r)}" for r in func[:6]))
    if nfr:
        req_paras.append("**The top non-functional requirements:** " + " ".join(
            f"- {reqTextInline(r)}" for r in nfr[:6]))
    sections.append({"key": "requirements", "title": "What the requirements say", "icon": "list", "paragraphs": req_paras})

    return sections


def reqTextInline(r):
    if isinstance(r, dict):
        return as_text(r.get("description")) or as_text(r.get("requirement")) or as_text(r.get("id"))
    return as_text(r)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def get_mock_analysis(business_problem: str, scale_estimates: dict = None,
                      constraints: list = None, architecture_tier: str = "professional") -> dict:
    """Build the full canonical architecture model."""
    if scale_estimates is None:
        scale_estimates = {}
    if constraints is None:
        constraints = []

    domain = classify_domain(business_problem)
    workload = extract_workload(business_problem, scale_estimates)
    complexity = compute_complexity(workload, domain, constraints, architecture_tier)
    workload["complexity_score"] = complexity
    read_ratio = 0.8
    workload["read_per_second"] = round(workload["avg_requests_per_second"] * read_ratio, 2)
    workload["write_per_second"] = round(workload["avg_requests_per_second"] * (1 - read_ratio), 2)

    pattern, style, justification, flavor = select_pattern(complexity, domain)

    model = new_model(business_problem, domain, architecture_tier, scale_estimates)
    model["requirements"] = build_requirements(business_problem, domain, workload, constraints, architecture_tier)

    model["architecture"]["system_type"] = f"{domain} Architecture ({architecture_tier.title()} Tier)"
    model["architecture"]["pattern"] = pattern
    model["architecture"]["style"] = style
    model["architecture"]["justification"] = justification

    components = build_components(domain, workload, pattern, flavor)
    model["architecture"]["components"] = components
    model["architecture"]["relationships"] = build_relationships(components, flavor)

    db_tech = _database_for(domain, pattern)
    has_cache = any(c["type"] == "cache" for c in components)
    has_queue = any(c["type"] == "queue" for c in components)
    queue_tech = next((c["technology"] for c in components if c["type"] == "queue"), "RabbitMQ")
    model["architecture"]["decisions"] = build_decisions(
        domain, pattern, flavor, workload, db_tech[0], has_cache, has_queue, queue_tech,
    )
    model["architecture"]["technologies"] = [
        {"component": c["name"], "technology": c["technology"], "purpose": c["responsibility"],
         "alternatives": c["alternatives"] or [], "reason": c["reason"],
         "tradeoff": _scaling_for(c["type"], flavor)}
        for c in components if c["type"] in ("service", "database", "cache", "queue", "gateway")
    ]

    model["database"] = build_database(domain, pattern, workload, db_tech[0], flavor)
    model["security"] = build_security(domain, pattern, flavor, workload)
    model["api"] = build_api(domain, components, model["database"], model["security"], workload)
    model["deployment"] = build_deployment(pattern, flavor, domain)
    model["performance"] = build_performance(domain, workload, components, flavor)
    model["failure_scenarios"] = build_failure_scenarios(components, flavor)
    model["risks"] = build_risks(domain, flavor, workload, constraints)

    model["review"] = review_model(model)
    model = self_correct(model)

    # Diagrams + explanation modes + alternatives are regenerated after any
    # correction so they always reflect the final canonical state.
    model["architecture"]["explanation_modes"] = build_explanation_modes(model)
    model["architecture"]["alternatives"] = build_alternatives(model)
    model["overview_explained"] = build_deep_overview(model)
    model["diagrams"] = build_diagrams(model)
    model["status"] = "completed"
    return model


# Convenience: JSON round-trip helper for consumers.
def model_to_json(model: dict) -> str:
    return json.dumps(model, default=str)
