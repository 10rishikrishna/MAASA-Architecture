# backend/agents/mock_data.py

def get_mock_analysis(business_problem: str, scale_estimates: dict, constraints: list) -> dict:
    users = scale_estimates.get("users", "100K")
    requests = scale_estimates.get("daily_requests", "1M")
    budget = scale_estimates.get("budget", "$5,000/month")
    
    # Determine basic type
    problem_lower = business_problem.lower()
    is_ecommerce = "e-commerce" in problem_lower or "shop" in problem_lower or "retail" in problem_lower or "sales" in problem_lower
    is_chat = "chat" in problem_lower or "messenger" in problem_lower or "communication" in problem_lower or "slack" in problem_lower
    is_crm = "crm" in problem_lower or "customer" in problem_lower or "salesforce" in problem_lower
    
    if is_ecommerce:
        sys_type = "E-Commerce Platform"
        primary_pattern = "Microservices Architecture"
        db_choice = "PostgreSQL (Primary + 2 Read Replicas) + Redis Cluster"
        components = ["Auth Service", "Product Catalog Service", "Cart & Checkout Service", "Order Processing Service", "Payment Gateway Integration Service"]
    elif is_chat:
        sys_type = "Real-Time Chat Application"
        primary_pattern = "Hybrid Microservices & Event-Driven (WebSockets)"
        db_choice = "PostgreSQL (User metadata) + MongoDB (Chat history) + Redis (Pub/Sub)"
        components = ["User Auth Service", "Chat Gateway (WebSocket Handler)", "Message Storage Service", "Push Notification Service", "Presence Tracking Service"]
    elif is_crm:
        sys_type = "SaaS CRM System"
        primary_pattern = "Modular Monolith (for high cohesion & transactional integrity)"
        db_choice = "PostgreSQL with multi-tenant schema partitioning"
        components = ["Auth & Subscription Module", "Contact Management Module", "Sales Pipeline Module", "Reporting & Analytics Module", "Integrations Engine"]
    else:
        sys_type = "SaaS Platform"
        primary_pattern = "Microservices Architecture"
        db_choice = "PostgreSQL + Redis"
        components = ["Auth Service", "Core API Service", "Billing/Subscription Service", "Reporting Service", "Background Worker Queue"]

    # Mermaid diagram text
    mermaid_diagram = f"""graph TD
    %% Styling
    classDef client fill:#eef2ff,stroke:#6366f1,stroke-width:2px;
    classDef edge_gw fill:#faf5ff,stroke:#a855f7,stroke-width:2px;
    classDef svc fill:#f0fdf4,stroke:#22c55e,stroke-width:2px;
    classDef db fill:#fff7ed,stroke:#f97316,stroke-width:2px;
    
    Users[Web & Mobile Clients]:::client
    CDN[Cloudflare CDN / WAF]:::edge_gw
    ALB[Application Load Balancer]:::edge_gw
    APIGW[API Gateway - Kong/Ocelot]:::edge_gw
    
    %% Services
    AuthSvc[{components[0]}]:::svc
    CoreSvc1[{components[1]}]:::svc
    CoreSvc2[{components[2]}]:::svc
    CoreSvc3[{components[3]}]:::svc
    
    %% Shared Infrastructure
    RedisCache[(Redis Distributed Cache)]:::db
    KafkaQueue[(Kafka / RabbitMQ Event Bus)]:::db
    
    %% Databases
    MainDB[(Primary PostgreSQL)]:::db
    ReplicaDB[(Read Replica PostgreSQL)]:::db
    
    Users -->|HTTPS| CDN
    CDN -->|Forward Request| ALB
    ALB -->|Route| APIGW
    
    APIGW -->|Validate Token| AuthSvc
    APIGW -->|Dispatch| CoreSvc1
    APIGW -->|Dispatch| CoreSvc2
    APIGW -->|Dispatch| CoreSvc3
    
    CoreSvc1 -->|Session Cache| RedisCache
    CoreSvc2 -->|Read/Write| MainDB
    CoreSvc3 -->|Publish Events| KafkaQueue
    
    KafkaQueue -->|Consume Events| CoreSvc1
    MainDB -->|Replication| ReplicaDB
    CoreSvc2 -->|Read Analytics| ReplicaDB
"""

    return {
        "requirements": {
            "functional": [
                f"User registration, login, and Role-Based Access Control (RBAC) supporting at least {users} users.",
                f"Core service workflow: {components[1]} and {components[2]} operations with low latency.",
                "Real-time alerts and state updates across client platforms.",
                "Exportable data dashboards and usage reports for tenants/admins.",
                "Third-party system integrations (OAuth, Stripe, notifications)."
            ],
            "non_functional": [
                f"Scalability: Designed to handle up to {requests} daily requests with automatic scaling rules.",
                "Availability: 99.9% Uptime SLA using multi-AZ database replication and active health checks.",
                f"Cost Constraints: Total infrastructure target under {budget} utilizing managed container runtimes.",
                "Latency: P95 API response times under 200ms for read operations and under 500ms for write operations.",
                "Compliance: GDPR data deletion compliance and AES-256 database storage encryption."
            ]
        },
        "architecture_design": {
            "system_type": sys_type,
            "pattern": primary_pattern,
            "justification": f"Based on the scale requirements of {users} active users and the target budget of {budget}, a {primary_pattern} represents the optimal balance. It provides independent service scalability for heavy write traffic bottlenecks, high operational isolation (preventing single service failures from crashing the system), and clear domain separation for development teams.",
            "components": [
                {
                    "name": comp,
                    "description": f"Responsible for handling core actions in the {comp.lower()} domain. Uses isolated database schemas or caches for performance.",
                    "technology": "FastAPI (Python) / Node.js"
                } for comp in components
            ]
        },
        "database_schema": {
            "database_type": "PostgreSQL",
            "justification": "ACID compliance ensures absolute financial/state transactional safety. JSONB support allows structured yet flexible metadata logs. Scale-out read replicas solve the high read ratio common in this usecase.",
            "schemas": [
                {
                    "table_name": "users",
                    "sql": "CREATE TABLE users (\n  id UUID PRIMARY KEY,\n  email VARCHAR(255) UNIQUE NOT NULL,\n  password_hash VARCHAR(255) NOT NULL,\n  name VARCHAR(255) NOT NULL,\n  plan VARCHAR(50) DEFAULT 'free',\n  created_at TIMESTAMP DEFAULT NOW()\n);"
                },
                {
                    "table_name": "entities",
                    "sql": "CREATE TABLE entities (\n  id UUID PRIMARY KEY,\n  user_id UUID REFERENCES users(id) ON DELETE CASCADE,\n  title VARCHAR(255) NOT NULL,\n  metadata JSONB DEFAULT '{}',\n  status VARCHAR(50) NOT NULL,\n  created_at TIMESTAMP DEFAULT NOW()\n);"
                }
            ],
            "indexing_strategies": [
                "Index idx_entities_user_id ON entities(user_id) for rapid dashboard lookups.",
                "Index idx_entities_status_created ON entities(status, created_at DESC) for list filter optimizations."
            ]
        },
        "api_specification": {
            "protocol": "REST HTTP / JSON",
            "endpoints": [
                {
                    "method": "POST",
                    "path": "/api/v1/auth/register",
                    "description": "Registers a new user and provisions default resources.",
                    "request_body": "{\n  \"email\": \"string\",\n  \"password\": \"string\",\n  \"name\": \"string\"\n}",
                    "response_body": "{\n  \"user_id\": \"uuid\",\n  \"token\": \"jwt_string\"\n}"
                },
                {
                    "method": "GET",
                    "path": "/api/v1/items",
                    "description": "Retrieves paged list of active assets.",
                    "query_params": "limit=20, offset=0, filter=active",
                    "response_body": "{\n  \"items\": [{\"id\": \"uuid\", \"title\": \"string\"}],\n  \"total\": 120\n}"
                }
            ]
        },
        "deployment_config": {
            "infrastructure_as_code": "Terraform",
            "orchestration": "AWS ECS (Fargate) or Kubernetes (EKS)",
            "terraform_sample": """# main.tf - AWS Infrastructure Provisioning
provider "aws" {
  region = "us-east-1"
}

module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  name   = "maasa-production-vpc"
  cidr   = "10.0.0.0/16"
  azs    = ["us-east-1a", "us-east-1b"]
  
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets = ["10.0.10.0/24", "10.0.11.0/24"]
  
  enable_nat_gateway = true
  single_nat_gateway = true
}

resource "aws_ecs_cluster" "main" {
  name = "maasa-ecs-cluster"
}""",
            "kubernetes_manifest": """# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: core-service-deployment
  labels:
    app: core-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: core-service
  template:
    metadata:
      labels:
        app: core-service
    spec:
      containers:
      - name: core-service
        image: maasa-core-service:latest
        ports:
        - containerPort: 8000
        resources:
          limits:
            cpu: "500m"
            memory: "512Mi"
          requests:
            cpu: "250m"
            memory: "256Mi"
"""
        },
        "security_audit": {
            "vulnerability_mitigations": [
                "CORS Policy: Strict setup to reject requests from non-domain origins.",
                "SQL Injection: SQLAlchemy ORM enforces parameterized inputs automatically.",
                "DDoS/Rate Limiting: Kong Gateway enforces limit of 100 req/min per IP/API token."
            ],
            "compliance": "GDPR (Right to be Forgotten) implemented via cascade deletion rules on user ID in database."
        },
        "performance_strategies": {
            "caching": "Redis Cache layer with 1-hour TTL for catalog queries and 1-minute TTL for active list views.",
            "optimization": "Load Balancer employs round-robin targeting, offloading SSL decryption directly at the WAF edge to keep application servers lightweight."
        },
        "diagrams": {
            "mermaid": mermaid_diagram,
            "ascii": "+------------+      +------------------+      +-----------------+\n| User Client | ---> | Cloudflare CDN   | ---> | Load Balancer   |\n+------------+      +------------------+      +-----------------+\n                                                       |\n                                                       v\n                                              +-----------------+\n                                              | API Gateway     |\n                                              +-----------------+\n                                                /       |       \\\n                                               v        v        v\n                                            +-----+  +-----+  +-----+\n                                            | Svc1|  | Svc2|  | Svc3|\n                                            +-----+  +-----+  +-----+"
        }
    }
