# Mosaic Studio - Virtual Architecture Workspace

AI-powered platform that generates comprehensive system architecture blueprints from a business problem description. Eight specialized AI agents collaborate to produce requirements, database schemas, API specs, deployment configs, security audits, performance strategies, and diagrams.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19 + TypeScript + Vite |
| **Backend** | Python FastAPI + SQLAlchemy + SQLite |
| **Auth** | JWT (python-jose + bcrypt) + Refresh Tokens |
| **LLM** | OpenAI GPT-4 (optional, falls back to rich mock data) |
| **Cache/Queue** | Redis + Celery |
| **Observability** | Prometheus + Grafana + Jaeger + ELK |
| **Load Balancer** | Nginx with upstream + rate limiting |
| **Fault Tolerance** | Circuit Breaker + Retry + Bulkhead |

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose (recommended)

### Quick Start with Docker

```bash
docker-compose up --build
```

This starts all services:
- Frontend: http://localhost:80
- Backend API: http://localhost:8000
- Load Balancer: http://localhost:8080
- Grafana: http://localhost:3001
- Jaeger UI: http://localhost:16686
- Kibana: http://localhost:5601
- Prometheus: http://localhost:9090

### Manual Setup

#### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

cp ../.env.example ../.env
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

#### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Environment Variables

See `.env.example` for all configuration options:

- `JWT_SECRET` - Secret key for JWT tokens (required for production)
- `DATABASE_URL` - Database connection string (default: SQLite)
- `OPENAI_API_KEY` - OpenAI API key (optional, enables real LLM analysis)
- `REDIS_URL` - Redis connection for cache and message queue
- `CELERY_BROKER_URL` - Celery broker for background tasks
- `JAEGER_ENDPOINT` - Jaeger tracing endpoint
- `PROMETHEUS_PORT` - Prometheus metrics port
- `ELASTICSEARCH_URL` - Elasticsearch for log aggregation

## Features

- **Multi-Agent Analysis** - 8 specialized AI agents collaborate on architecture design
- **Real-time Streaming** - Watch agents work via SSE progress events
- **Rich Report** - Requirements, architecture, DB schemas, API specs, deployment, security, performance, diagrams
- **3-Tier Explanations** - Brief, Long, and Detailed explanation modes for all features
- **Mermaid Diagrams** - Auto-generated architecture diagrams
- **Context-Aware Chat** - AI-powered chatbot with architecture context
- **Export** - Download reports as Markdown or JSON
- **Projects** - Organize analyses into projects
- **Teams** - Collaborate with team members
- **API Keys** - Generate and manage API keys
- **Observability** - Prometheus metrics, Grafana dashboards, Jaeger tracing, ELK logs
- **Load Balancing** - Nginx upstream with health checks and rate limiting
- **Fault Tolerance** - Circuit breaker, retry with backoff, bulkhead patterns
- **Message Queue** - Redis + Celery for async background processing
- **Refresh Tokens** - Secure token rotation with revocation support

## Architecture

```
User -> CDN/WAF -> Load Balancer (Nginx) -> Backend (FastAPI) -> Database
                                         -> Redis Cache/Queue
                                         -> Celery Worker

Observability Pipeline:
App -> OpenTelemetry -> Jaeger (Traces)
App -> Prometheus -> Grafana (Metrics)
App -> Structured Logs -> Elasticsearch -> Kibana (Logs)
```

## Project Structure

```
.
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings (Pydantic)
│   ├── database.py          # SQLAlchemy models (12 tables)
│   ├── auth.py              # JWT + password hashing + refresh tokens
│   ├── fault_tolerance.py   # Circuit breaker, retry, bulkhead
│   ├── celery_app.py        # Background task processing
│   ├── agents/
│   │   ├── engine.py        # Agent orchestrator
│   │   ├── mock_data.py     # Rich mock data generator
│   │   └── prompt_templates.py  # LLM prompt templates
│   └── routers/
│       ├── auth_router.py   # Auth + refresh tokens
│       ├── analyze_router.py # Analysis CRUD + streaming
│       ├── projects_router.py # Project management
│       ├── chat_router.py   # Context-aware chat
│       ├── teams_router.py  # Team management
│       ├── shares_router.py # Project sharing
│       ├── apikeys_router.py # API key management
│       └── audit_router.py  # Audit logs
├── frontend/
│   └── src/
│       ├── api/client.ts    # API client + types
│       ├── context/         # Auth context with refresh
│       ├── components/      # Layout, Sidebar, MermaidDiagram
│       └── pages/           # All page components
├── monitoring/
│   ├── prometheus.yml       # Prometheus config
│   ├── alert_rules.yml      # Alert rules
│   └── grafana/             # Grafana dashboards + datasources
├── nginx-lb.conf            # Load balancer config
├── docker-compose.yml       # Full stack orchestration
└── .env.example
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Observability

- **Metrics**: http://localhost:9090 (Prometheus)
- **Dashboards**: http://localhost:3001 (Grafana)
- **Tracing**: http://localhost:16686 (Jaeger)
- **Logs**: http://localhost:5601 (Kibana)
