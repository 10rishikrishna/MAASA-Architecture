# backend/agents/mock_data.py
import json

DOMAIN_KNOWLEDGE_BASE = {
    "Cybersecurity": {
        "services": [
            {"name": "Endpoint Collector Agent", "tech": "Go / Rust", "reason": "High performance background telemetry streaming from host agents.", "alternatives": ["C++ Daemon"], "tradeoffs": "Requires low memory footprint."},
            {"name": "Detection Engine", "tech": "Python / Rust", "reason": "Evaluates incoming security events against Sigma and YARA threat rules.", "alternatives": ["Suricata", "Snort"], "tradeoffs": "High CPU utilization during peak log spikes."},
            {"name": "Threat Intelligence Service", "tech": "FastAPI (Python)", "reason": "Enriches IP addresses and file hashes with alienvault/virustotal feeds.", "alternatives": ["MISP"], "tradeoffs": "Requires API rate-limit caching."},
            {"name": "Rule Engine", "tech": "Java / Go", "reason": "Executes complex stateful correlation logic across event streams.", "alternatives": ["Apache Flink"], "tradeoffs": "In-memory state requires snapshot persistence."},
            {"name": "Alert & Notification Service", "tech": "Node.js", "reason": "Dispatches high-priority security incident alerts to Slack, PagerDuty, and email.", "alternatives": ["Webhooks"], "tradeoffs": "Must handle rapid alert deduplication to prevent notification fatigue."},
            {"name": "SIEM Integration Service", "tech": "Go", "reason": "Exports normalized CEF/LEEF logs to Splunk, Datadog, and Elastic.", "alternatives": ["Logstash"], "tradeoffs": "High network egress if uncompressed."},
            {"name": "Audit & Compliance Logger", "tech": "Python", "reason": "Stores tamper-evident append-only security logs for SOC2 & HIPAA audits.", "alternatives": ["AWS CloudTrail"], "tradeoffs": "Immutable storage cost accumulation."}
        ],
        "db": "TimescaleDB (Time-series logs) + PostgreSQL (Metadata) + Redis (Active Threats)",
        "security_score": 96,
        "scalability_score": 92,
        "cost_score": 85,
        "critique": "Optimal domain alignment for SOC/threat analysis. Micro-segmentation enforced via mTLS."
    },
    "E-Commerce": {
        "services": [
            {"name": "Product Catalog Service", "tech": "Node.js", "reason": "High-throughput read-heavy catalog search and product metadata.", "alternatives": ["Elasticsearch"], "tradeoffs": "Requires aggressive Redis caching."},
            {"name": "Cart & Checkout Service", "tech": "Go", "reason": "Handles atomic cart mutations and session checkout state.", "alternatives": ["FastAPI"], "tradeoffs": "Requires distributed locking for stock allocation."},
            {"name": "Order Processing Service", "tech": "Java / Spring Boot", "reason": "Orchestrates order state workflow and fulfillment dispatch.", "alternatives": ["Temporal.io"], "tradeoffs": "Requires transactional outbox pattern for events."},
            {"name": "Payment Gateway Service", "tech": "Python", "reason": "Integrates securely with Stripe/PayPal APIs with PCI-DSS boundary compliance.", "alternatives": ["Adyen"], "tradeoffs": "Third-party latency dependencies."},
            {"name": "Recommendation Engine", "tech": "Python (PyTorch / FastAPI)", "reason": "Generates personalized product suggestions based on user browsing history.", "alternatives": ["Redis Vector Search"], "tradeoffs": "Higher GPU/Compute costs."}
        ],
        "db": "PostgreSQL (ACID Orders/Cart) + MongoDB (Catalog) + Redis (Session Cache)",
        "security_score": 90,
        "scalability_score": 94,
        "cost_score": 88,
        "critique": "Solid separation of concerns between catalog reads and payment execution."
    },
    "FinTech": {
        "services": [
            {"name": "Core Ledger Engine", "tech": "Rust / C++", "reason": "Double-entry immutable ledger accounting for financial transactions.", "alternatives": ["TigerBeetle"], "tradeoffs": "Strict serializability reduces raw write throughput."},
            {"name": "Payment Processing Gateway", "tech": "Go", "reason": "ISO 20022 message routing and bank ACH/Wire transfers.", "alternatives": ["Java"], "tradeoffs": "High regulatory compliance requirements."},
            {"name": "Fraud Detection Service", "tech": "Python / LightGBM", "reason": "Real-time transaction scoring against known fraudulent patterns.", "alternatives": ["ONNX Runtime"], "tradeoffs": "Sub-50ms inference requirement."},
            {"name": "KYC / AML Service", "tech": "FastAPI", "reason": "Identity verification and sanction list matching.", "alternatives": ["Sumsub API"], "tradeoffs": "Third-party API availability requirement."}
        ],
        "db": "PostgreSQL (Multi-region active-active) + Redis (Locking)",
        "security_score": 98,
        "scalability_score": 89,
        "cost_score": 82,
        "critique": "Strict compliance and zero-data-loss posture. Immutable audit logs configured."
    },
    "Healthcare": {
        "services": [
            {"name": "Patient Portal Service", "tech": "Node.js", "reason": "Secure FHIR-compliant patient records access.", "alternatives": ["Django"], "tradeoffs": "Requires strict OAuth2 scope control."},
            {"name": "Telehealth Gateway", "tech": "Go / WebRTC", "reason": "Encrypted video & messaging relay between doctor and patient.", "alternatives": ["Twilio Video"], "tradeoffs": "High bandwidth requirements."},
            {"name": "HIPAA Audit Logger", "tech": "Python", "reason": "Encrypts and logs every PHI access event for HIPAA compliance.", "alternatives": ["Vault Audit"], "tradeoffs": "High volume audit log storage."}
        ],
        "db": "PostgreSQL (Encrypted at rest AES-256) + S3 (DICOM Images)",
        "security_score": 99,
        "scalability_score": 87,
        "cost_score": 84,
        "critique": "HIPAA compliant architecture. Strong encryption at rest and in transit."
    },
    "Real-Time Chat": {
        "services": [
            {"name": "WebSocket Connection Gateway", "tech": "Go / Erlang", "reason": "Maintains persistent socket connections for millions of concurrent users.", "alternatives": ["Node.js"], "tradeoffs": "Memory overhead per active socket connection."},
            {"name": "Message Dispatcher & Router", "tech": "Rust", "reason": "Routes messages instantly to recipient socket instances.", "alternatives": ["RabbitMQ"], "tradeoffs": "Complex cluster state sync."},
            {"name": "Presence Tracking Service", "tech": "Node.js / Redis", "reason": "Tracks online/offline/typing state of active users.", "alternatives": ["Memcached"], "tradeoffs": "High heartbeat ping load."}
        ],
        "db": "Cassandra / ScyllaDB (Messages) + PostgreSQL (User Metadata) + Redis (Presence)",
        "security_score": 91,
        "scalability_score": 97,
        "cost_score": 90,
        "critique": "Optimized for extreme concurrent WebSocket connections and fast message delivery."
    },
    "SaaS Platform": {
        "services": [
            {"name": "Auth & Tenant Management", "tech": "FastAPI (Python)", "reason": "Multi-tenant user authentication, RBAC, and organization isolation.", "alternatives": ["Auth0"], "tradeoffs": "Token revocation tracking required."},
            {"name": "Core Business API Service", "tech": "Node.js / Go", "reason": "Executes domain workflows and business logic for tenant requests.", "alternatives": ["Python"], "tradeoffs": "Requires horizontal Pod autoscaling."},
            {"name": "Reporting & Analytics Service", "tech": "Python", "reason": "Aggregates tenant metrics and exports PDF/CSV reports.", "alternatives": ["DuckDB"], "tradeoffs": "Background job queue execution needed."}
        ],
        "db": "PostgreSQL (Multi-tenant partition) + Redis Distributed Cache",
        "security_score": 92,
        "scalability_score": 91,
        "cost_score": 92,
        "critique": "Flexible general SaaS architecture with strong tenant data boundaries."
    }
}

def classify_domain(business_problem: str) -> str:
    p = business_problem.lower()
    if any(k in p for k in ["cybersecurity", "security", "threat", "soc", "siem", "endpoint", "malware", "vulnerability", "firewall", "ids"]):
        return "Cybersecurity"
    elif any(k in p for k in ["e-commerce", "ecommerce", "shop", "cart", "checkout", "retail", "store"]):
        return "E-Commerce"
    elif any(k in p for k in ["fintech", "bank", "payment", "ledger", "fraud", "trading", "crypto", "wallet"]):
        return "FinTech"
    elif any(k in p for k in ["health", "patient", "medical", "fhir", "hipaa", "telehealth", "hospital"]):
        return "Healthcare"
    elif any(k in p for k in ["chat", "messaging", "websocket", "slack", "messenger", "communication"]):
        return "Real-Time Chat"
    else:
        return "SaaS Platform"

def select_pattern_by_scale(scale_estimates: dict) -> tuple[str, str]:
    users_str = str(scale_estimates.get("users", "10000")).lower()
    # parse numbers out
    num = 10000
    try:
        clean = ''.join(c for c in users_str if c.isdigit())
        if "k" in users_str:
            num = int(clean) * 1000 if clean else 10000
        elif "m" in users_str:
            num = int(clean) * 1000000 if clean else 1000000
        elif clean:
            num = int(clean)
    except Exception:
        num = 10000

    if num < 5000:
        return "Modular Monolith", f"With ~{num:,} users, a Modular Monolith offers maximum developer velocity and simple deployment without microservice network overhead."
    elif num < 100000:
        return "Microservices Architecture", f"With ~{num:,} users, Microservices provide clear service boundaries and independent scalability for high-traffic components."
    else:
        return "Event-Driven Microservices (EDA)", f"With ~{num:,} users, an Event-Driven Architecture using Kafka/RabbitMQ guarantees high concurrency and non-blocking asynchronous decoupling."

def generate_high_contrast_mermaid(domain: str, components: list) -> str:
    """
    Produces high-contrast Mermaid flowchart designed for dark-mode.
    Uses explicit stroke color and crisp white text (#ffffff) on dark rich node backgrounds.
    """
    comp_lines = []
    # Pick 4 main services for visual diagram
    svcs = components[:4]
    
    mermaid_code = f"""graph TD
    %% High-Contrast Dark-Mode Theme Definitions
    classDef client fill:#1e1b4b,stroke:#818cf8,color:#ffffff,stroke-width:2px;
    classDef edge_gw fill:#311042,stroke:#c084fc,color:#ffffff,stroke-width:2px;
    classDef svc fill:#064e3b,stroke:#34d399,color:#ffffff,stroke-width:2px;
    classDef db fill:#431407,stroke:#fb923c,color:#ffffff,stroke-width:2px;
    classDef sec fill:#450a0a,stroke:#f87171,color:#ffffff,stroke-width:2px;

    Client[Web / Mobile Client]:::client
    CDN[Cloudflare WAF / Edge CDN]:::edge_gw
    APIGW[API Gateway - Kong / Ocelot]:::sec

    Client -->|HTTPS / TLS| CDN
    CDN -->|Forward Request| APIGW
"""

    for i, s in enumerate(svcs):
        node_id = f"Svc{i+1}"
        s_name = s["name"]
        mermaid_code += f"    {node_id}[{s_name}]:::svc\n"
        mermaid_code += f"    APIGW -->|Dispatch| {node_id}\n"

    # Infrastructure & Storage
    mermaid_code += """
    RedisCache[(Redis Distributed Cache)]:::db
    MainDB[(Primary Storage Engine)]:::db

    Svc1 -->|Session & State| RedisCache
    Svc2 -->|Read / Write| MainDB
"""
    return mermaid_code

def get_mock_analysis(business_problem: str, scale_estimates: dict, constraints: list) -> dict:
    domain = classify_domain(business_problem)
    kb_data = DOMAIN_KNOWLEDGE_BASE.get(domain, DOMAIN_KNOWLEDGE_BASE["SaaS Platform"])
    
    users = scale_estimates.get("users", "50,000")
    requests = scale_estimates.get("daily_requests", "1,000,000")
    budget = scale_estimates.get("budget", "$5,000/month")
    
    pattern, pattern_justification = select_pattern_by_scale(scale_estimates)
    components = kb_data["services"]
    
    # Render Mermaid diagram
    mermaid_diagram = generate_high_contrast_mermaid(domain, components)
    
    # ASCII diagram
    ascii_diagram = f"""
+-----------------+      +--------------------+      +-----------------------+
|  User Clients   | ---> |  Cloudflare WAF    | ---> |  API Gateway (Kong)   |
+-----------------+      +--------------------+      +-----------------------+
                                                                 |
                                  +------------------------------+------------------------------+
                                  |                              |                              |
                                  v                              v                              v
                      +----------------------+      +----------------------+      +----------------------+
                      | {components[0]['name']:<20} |      | {components[1]['name']:<20} |      | {components[2]['name']:<20} |
                      +----------------------+      +----------------------+      +----------------------+
                                  |                              |                              |
                                  v                              v                              v
                      +----------------------------------------------------------------------------------+
                      | Storage Layer: {kb_data['db']:<65} |
                      +----------------------------------------------------------------------------------+
"""

    return {
        "domain": domain,
        "requirements": {
            "functional": [
                f"Domain Focus ({domain}): Automated workflow handling for core operational entities.",
                f"User Access: Support role-based access control (RBAC) and OAuth2/OIDC authentication for {users} active users.",
                f"Service Decoupling: Provide dedicated endpoints for {components[0]['name']} and {components[1]['name']}.",
                "Event Notification: Real-time alerting and audit trail emission on key state changes.",
                "Analytics & Export: Generate periodic tenant usage logs and operational telemetry dashboards."
            ],
            "non_functional": [
                f"Scalability: Designed to handle up to {requests} daily requests with auto-scaling container runtimes.",
                "Availability: Target 99.95% uptime SLA via Multi-AZ database deployments and active health probes.",
                f"Budget Limit: Infrastructure optimized to stay within target budget of {budget}.",
                "Performance: P95 latency < 150ms for read requests and < 350ms for transaction writes.",
                f"Security & Compliance: Dedicated audit logging and compliance alignment for {domain} standards."
            ]
        },
        "architecture_design": {
            "system_type": f"{domain} Architecture",
            "pattern": pattern,
            "justification": f"{pattern_justification} Selected specifically for the {domain} domain to ensure maximum component isolation, ease of maintainability, and clean data boundaries.",
            "components": [
                {
                    "name": comp["name"],
                    "description": f"Domain service powering {comp['name'].lower()} workflows in the {domain} pipeline.",
                    "technology": comp["tech"],
                    "reason": comp["reason"],
                    "alternatives": comp["alternatives"],
                    "tradeoffs": comp["tradeoffs"]
                } for comp in components
            ]
        },
        "database_schema": {
            "database_type": kb_data["db"],
            "justification": f"Selected to suit the access patterns of {domain}. Ensures strong transactional integrity where needed and fast low-latency lookups for operational data.",
            "schemas": [
                {
                    "table_name": "domain_events",
                    "sql": "CREATE TABLE domain_events (\n  id UUID PRIMARY KEY,\n  event_type VARCHAR(100) NOT NULL,\n  payload JSONB NOT NULL,\n  status VARCHAR(50) NOT NULL,\n  created_at TIMESTAMP DEFAULT NOW()\n);"
                },
                {
                    "table_name": "audit_logs",
                    "sql": "CREATE TABLE audit_logs (\n  id UUID PRIMARY KEY,\n  actor_id UUID NOT NULL,\n  action VARCHAR(255) NOT NULL,\n  resource_id VARCHAR(255) NOT NULL,\n  ip_address VARCHAR(45),\n  timestamp TIMESTAMP DEFAULT NOW()\n);"
                }
            ],
            "indexing_strategies": [
                "Index idx_domain_events_type ON domain_events(event_type, created_at DESC) for event queries.",
                "Index idx_audit_logs_actor ON audit_logs(actor_id, timestamp DESC) for compliance auditing."
            ]
        },
        "api_specification": {
            "protocol": "REST HTTP / JSON & gRPC Internal",
            "endpoints": [
                {
                    "method": "POST",
                    "path": "/api/v1/events",
                    "description": f"Ingests operational events into the {components[0]['name']}.",
                    "request_body": "{\n  \"event_type\": \"string\",\n  \"data\": {}\n}",
                    "response_body": "{\n  \"status\": \"received\",\n  \"event_id\": \"uuid\"\n}"
                },
                {
                    "method": "GET",
                    "path": "/api/v1/metrics",
                    "description": f"Retrieves real-time aggregated metrics from {components[1]['name']}.",
                    "query_params": "timeframe=1h, limit=50",
                    "response_body": "{\n  \"metrics\": [],\n  \"count\": 50\n}"
                }
            ]
        },
        "deployment_config": {
            "infrastructure_as_code": "Terraform",
            "orchestration": "AWS ECS (Fargate) / Kubernetes (EKS)",
            "terraform_sample": """# main.tf - Production IaC Definition
provider "aws" {
  region = "us-east-1"
}

module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  name   = "maasa-domain-vpc"
  cidr   = "10.0.0.0/16"
  azs    = ["us-east-1a", "us-east-1b"]
  
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets = ["10.0.10.0/24", "10.0.11.0/24"]
  enable_nat_gateway = true
}""",
            "kubernetes_manifest": """# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: domain-service-deployment
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
        image: maasa-service:latest
        ports:
        - containerPort: 8000
"""
        },
        "security_audit": {
            "vulnerability_mitigations": [
                f"Domain Security ({domain}): Network segmentation prevents unauthenticated lateral movement.",
                "Authentication: JWT tokens signed with RS256 algorithm.",
                "WAF Edge: Cloudflare Web Application Firewall blocks SQLi, XSS, and bot scrapers."
            ],
            "compliance": f"Tailored for {domain} compliance requirements with tamper-evident audit logs.",
            "scores": {
                "security": kb_data["security_score"],
                "scalability": kb_data["scalability_score"],
                "cost": kb_data["cost_score"]
            },
            "reviewer_critique": kb_data["critique"]
        },
        "performance_strategies": {
            "caching": "Redis Cache with TTL policies tailored for domain queries.",
            "optimization": "Gzip/Brotli compression at API Gateway and database connection pooling."
        },
        "diagrams": {
            "mermaid": mermaid_diagram,
            "ascii": ascii_diagram
        }
    }
