# MAASA - Multi-Agent Autonomous Software Architect

An AI-powered platform that generates comprehensive system architecture blueprints from a business problem description. Eight specialized AI agents collaborate to produce requirements, database schemas, API specs, deployment configs, security audits, performance strategies, and diagrams.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19 + TypeScript + Vite |
| **Backend** | Python FastAPI + SQLAlchemy + SQLite |
| **Auth** | JWT (python-jose + bcrypt) |
| **LLM** | OpenAI GPT-4 (optional, falls back to rich mock data) |

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Copy and configure environment variables
cp ../.env.example ../.env

# Start the server
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173`.

### Environment Variables

See `.env.example` for all configuration options:

- `JWT_SECRET` - Secret key for JWT tokens (required for production)
- `DATABASE_URL` - Database connection string (default: SQLite)
- `OPENAI_API_KEY` - OpenAI API key (optional, enables real LLM analysis)
- `ANTHROPIC_API_KEY` - Anthropic API key (optional, reserved for future use)

## Features

- **Multi-Agent Analysis** - 8 specialized AI agents collaborate on architecture design
- **Real-time Streaming** - Watch agents work via SSE progress events
- **Rich Report** - Requirements, architecture, DB schemas, API specs, deployment, security, performance, diagrams
- **Mermaid Diagrams** - Auto-generated architecture diagrams
- **Chat Interface** - Ask follow-up questions about your architecture
- **Export** - Download reports as Markdown or JSON
- **Projects** - Organize analyses into projects
- **Teams** - Collaborate with team members
- **API Keys** - Generate and manage API keys

## Project Structure

```
.
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings (Pydantic)
│   ├── database.py          # SQLAlchemy models (9 tables)
│   ├── auth.py              # JWT + password hashing
│   ├── agents/
│   │   ├── engine.py        # Agent orchestrator
│   │   ├── mock_data.py     # Rich mock data generator
│   │   └── prompt_templates.py  # LLM prompt templates
│   └── routers/
│       ├── auth_router.py   # Auth endpoints
│       ├── analyze_router.py # Analysis CRUD + streaming
│       ├── projects_router.py # Project management
│       ├── chat_router.py   # Chat with analysis
│       ├── teams_router.py  # Team management
│       ├── shares_router.py # Project sharing
│       ├── apikeys_router.py # API key management
│       └── audit_router.py  # Audit logs
├── frontend/
│   └── src/
│       ├── api/client.ts    # API client + types
│       ├── context/         # Auth context
│       ├── components/      # Layout, Sidebar, MermaidDiagram
│       └── pages/           # All page components
└── .env.example
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
