# backend/routers/chat.py
import re
import random
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.database import get_db, User, Analysis, ChatHistory
from backend.auth import get_current_user
from backend.config import settings

router = APIRouter(prefix="/chat", tags=["Architecture Discussion Chat"])

class ChatMessageRequest(BaseModel):
    content: str

class ChatMessageResponse(BaseModel):
    response: str
    follow_up_suggestions: List[str]
    conversation_length: int

SULAIMAN_DIALOGUES = {
    "greetings": [
        "Njan Sulaiman alla... Hanuman aanu. Pande ennod PWD officer Thamarassery Churam erangiyappo chodichathaa. 😄 Ningal sheriaya sthalath aanu vannirikkunnath, doubt okke namukku fix cheyyam."
    ],
    "doubt": [
        "Athre ullu? Deyy ippo sheriakki theraam. 😄",
        "Ohoo ithaano karyam? Deyy ippo sheriakki theraam."
    ],
    "debugging": [
        "Karim ee aa cheriya spanner ing eduthe... dee ippo sheriakki theraam. 🔧"
    ],
    "argument": [
        "Enthaanu thaamasha aakaano? Heh... venda ketto. 😅"
    ],
    "success": [
        "Kando... paranjille, ippo sheri aaki theraam nn. 😎",
        "Athaanu nammade pani. System set! 🚀"
    ]
}

def generate_contextual_response(question: str, analysis: Analysis) -> tuple[str, List[str]]:
    q = question.lower().strip()
    
    # Contextual metadata from analysis
    arch = analysis.architecture_design or {}
    pattern = arch.get("pattern", "Microservices Architecture")
    sys_type = arch.get("system_type", "Domain Architecture")
    tier = arch.get("architecture_tier", "Professional")
    components = arch.get("components", [])
    comp_names = [c.get("name", "Service") for c in components] if components else ["Core API Service", "Auth Service"]
    
    db_schema = analysis.database_schema or {}
    db_type = db_schema.get("database_type", "PostgreSQL")
    
    sec_audit = analysis.security_audit or {}
    compliance = sec_audit.get("compliance", "SOC2 / GDPR compliance")
    sec_score = sec_audit.get("scores", {}).get("security", 92)
    
    api_spec = analysis.api_specification or {}
    endpoints = api_spec.get("endpoints", [])
    
    prefix_quote = ""
    
    # 1. Check for Greetings / Intros
    if any(re.search(r'\b' + k + r'\b', q) for k in ["hi", "hello", "hey", "hai", "good morning", "greetings", "who are you"]):
        prefix_quote = random.choice(SULAIMAN_DIALOGUES["greetings"]) + "\n\n"
        comp_str = ", ".join(comp_names[:4]) if comp_names else "Core Services"
        ans = (
            f"{prefix_quote}"
            f"**System Blueprint Summary ({tier} Tier):**\n"
            f"- **System Type:** {sys_type}\n"
            f"- **Pattern:** {pattern}\n"
            f"- **Core Building Blocks:** {comp_str}\n"
            f"- **Database Engine:** {db_type}\n"
            f"- **Security Score:** {sec_score}/100 🛡️ ({compliance})\n\n"
            f"What specific component, API endpoint, or cloud deployment strategy would you like to discuss today? 😄"
        )
        suggestions = ["Why did you choose this architecture?", "Explain database choices", "List all API endpoints"]

    # 2. Check for Arguments / Objections / Disagreements
    elif any(k in q for k in ["wrong", "you are wrong", "no", "not correct", "argue", "terrible", "bad"]):
        prefix_quote = random.choice(SULAIMAN_DIALOGUES["argument"]) + "\n\n"
        ans = (
            f"{prefix_quote}"
            f"Let's look at the trade-offs! For **{analysis.business_problem[:50]}...**, the choice of **{pattern}** was made because:\n"
            f"1. **Fault Isolation:** High load spikes in one worker won't crash user auth.\n"
            f"2. **Scaling:** Individual components like `{comp_names[0] if comp_names else 'API Service'}` scale independently.\n\n"
            f"If you prefer a simpler layout (like Monolith), we can adjust the Architecture Tier to **Basic**! 💡"
        )
        suggestions = ["Show monolith alternative", "Explain trade-offs", "What about budget?"]

    # 3. Check for Bugs / Crashes / Errors
    elif any(k in q for k in ["bug", "not working", "crash", "error", "failed", "broken", "issue"]):
        prefix_quote = random.choice(SULAIMAN_DIALOGUES["debugging"]) + "\n\n"
        ans = (
            f"{prefix_quote}"
            f"Here is how our architecture prevents and recovers from system errors:\n"
            f"- **Circuit Breakers:** API Gateway (Kong) immediately stops cascading failure if backend pods slow down.\n"
            f"- **Dead Letter Queues (DLQ):** Failed asynchronous event messages are safely stored for auto-retry.\n"
            f"- **Health Probes:** Kubernetes liveness/readiness probes restart unhealthy container pods within seconds! ⚡"
        )
        suggestions = ["How does failover work?", "Show security audit", "What are retry policies?"]

    # 4. Check for Success / Praise / Thanks
    elif any(k in q for k in ["fixed", "worked", "thanks", "thank you", "wow", "solved", "great", "awesome"]):
        prefix_quote = random.choice(SULAIMAN_DIALOGUES["success"]) + "\n\n"
        ans = (
            f"{prefix_quote}"
            f"Glad you loved the design! You can export your full architecture report as **Markdown (.md)** or **JSON**, "
            f"or copy the Terraform IaC scripts under the Deployment tab to spin up infrastructure instantly. 🚀"
        )
        suggestions = ["Download Markdown report", "View Terraform IaC", "Ask another question"]

    # 5. Check for Architecture Selection / "Why did you choose" (with fuzzy match for typos like "whu did u chose")
    elif any(k in q for k in ["why", "chose", "choose", "whu", "pattern", "topology", "reason", "decision"]):
        prefix_quote = random.choice(SULAIMAN_DIALOGUES["doubt"]) + "\n\n"
        justification = arch.get("justification", f"Selected {pattern} for optimal component isolation.")
        ans = (
            f"{prefix_quote}"
            f"**Architecture Decision Record (ADR):**\n\n"
            f"We selected **{pattern}** at the **{tier} Tier**.\n\n"
            f"**Rationale:**\n{justification}\n\n"
            f"**Key Engineering Benefits:**\n"
            f"1. **High Concurrency:** Independent worker pools process incoming requests without blocking.\n"
            f"2. **Zero Downtime Deployments:** Rolling upgrades allow updating individual services without global outages.\n"
            f"3. **Clean Team Boundaries:** Engineering teams can own dedicated service repos independently. ⚡"
        )
        suggestions = ["What are the trade-offs?", "Migration path from monolith?", "Explain component choices"]

    # 6. Check for Component / Technology Questions
    elif any(k in q for k in ["component", "service", "stack", "technology", "tech", "node", "building block", "redis", "postgres"]):
        prefix_quote = random.choice(SULAIMAN_DIALOGUES["doubt"]) + "\n\n"
        comp_details = ""
        for c in components[:5]:
            c_name = c.get("name", "Service")
            c_tech = c.get("technology", "FastAPI / Node.js")
            c_reason = c.get("reason", "Handles domain workflows.")
            comp_details += f"- **{c_name}** (`{c_tech}`): {c_reason}\n"
            
        ans = (
            f"{prefix_quote}"
            f"Here is the breakdown of components designed for your system:\n\n"
            f"{comp_details}\n"
            f"All components communicate asynchronously via event streams or gRPC internal protocols. 🔧"
        )
        suggestions = ["Explain database schema", "Show API endpoints", "What about security?"]

    # 7. Database Questions
    elif any(k in q for k in ["database", "db", "sql", "postgres", "schema", "tables", "storage", "cache"]):
        prefix_quote = random.choice(SULAIMAN_DIALOGUES["doubt"]) + "\n\n"
        tables = db_schema.get("schemas", [])
        tbl_names = [t.get("table_name", "entities") for t in tables] if tables else ["users", "events"]
        ans = (
            f"{prefix_quote}"
            f"**Database & Storage Layout:**\n\n"
            f"- **Primary Storage:** `{db_type}`\n"
            f"- **Core Tables:** `{', '.join(tbl_names)}`\n"
            f"- **Session Cache:** Redis Distributed Cache (1-hour TTL)\n"
            f"- **ACID Protection:** Strict transactional isolation enforced for financial/state mutations. 🛢️"
        )
        suggestions = ["Show SQL DDL code", "What is Redis?", "How is indexing configured?"]

    # 8. API / Endpoint Questions
    elif any(k in q for k in ["api", "endpoint", "rest", "swagger", "openapi", "route", "dispatch"]):
        prefix_quote = random.choice(SULAIMAN_DIALOGUES["doubt"]) + "\n\n"
        ep_text = ""
        for ep in endpoints[:3]:
            ep_text += f"- `{ep.get('method', 'GET')}` **{ep.get('path', '/api/v1')}**: {ep.get('description', '')}\n"
            
        ans = (
            f"{prefix_quote}"
            f"**API Specifications ({api_spec.get('protocol', 'REST HTTP / JSON')}):**\n\n"
            f"{ep_text if ep_text else '- POST /api/v1/events: Ingest operational events'}\n"
            f"All requests pass through the API Gateway (Kong) where JWT tokens are validated before reaching backend services. 🛡️"
        )
        suggestions = ["How are tokens validated?", "Is there rate limiting?", "Show request payloads"]

    # 9. Security & Compliance
    elif any(k in q for k in ["security", "vulnerability", "auth", "jwt", "compliance", "hipaa", "soc2", "audit"]):
        prefix_quote = random.choice(SULAIMAN_DIALOGUES["doubt"]) + "\n\n"
        mitigations = sec_audit.get("vulnerability_mitigations", [])
        mit_text = "\n".join([f"- {m}" for m in mitigations[:3]])
        ans = (
            f"{prefix_quote}"
            f"**Security Audit Summary (Score: {sec_score}/100 🛡️):**\n\n"
            f"**Compliance Target:** {compliance}\n\n"
            f"**Vulnerability Mitigations:**\n"
            f"{mit_text}\n\n"
            f"Intra-service traffic is strictly encrypted using TLS 1.3 mTLS tunnels."
        )
        suggestions = ["How to audit API keys?", "Can we add 2FA?", "How is data encrypted at rest?"]

    # 10. Cost & Infrastructure Questions
    elif any(k in q for k in ["cost", "aws", "budget", "price", "cloud", "terraform", "k8s", "kubernetes"]):
        prefix_quote = random.choice(SULAIMAN_DIALOGUES["doubt"]) + "\n\n"
        ans = (
            f"{prefix_quote}"
            f"**Cloud Budget Breakdown (AWS Target - {tier} Tier):**\n\n"
            f"| Component | Technology | Monthly Est. |\n"
            f"| --- | --- | --- |\n"
            f"| **WAF / API Gateway** | Cloudflare WAF + AWS ALB | $25.00 |\n"
            f"| **Compute Runtimes** | AWS ECS Fargate / EKS | $65.00 |\n"
            f"| **Database Cluster** | Amazon RDS ({db_type.split('+')[0]}) | $120.00 |\n"
            f"| **Cache & Queue** | ElastiCache Redis | $30.00 |\n"
            f"| **Total Projected** | **Production Grade** | **~$240.00/mo** |\n\n"
            f"IaC Terraform templates and Kubernetes manifests are ready under the Deployment tab! ☁️"
        )
        suggestions = ["How to reduce costs?", "Can we run on Kubernetes?", "What if traffic doubles?"]

    # 11. General Fallback with Sulaiman Persona
    else:
        prefix_quote = random.choice(SULAIMAN_DIALOGUES["doubt"]) + "\n\n"
        ans = (
            f"{prefix_quote}"
            f"Great question regarding **{question}** for your system! 😄\n\n"
            f"In this **{pattern}** ({tier} Tier), we handle `{question}` by delegating work to **{comp_names[0] if comp_names else 'Core Service'}** "
            f"and persisting state to **{db_type}**.\n\n"
            f"**Key Highlights:**\n"
            f"1. **Operational Isolation:** Service bounds ensure zero crash propagation.\n"
            f"2. **Resilience:** Automatic retry policies with exponential backoff at the gateway.\n"
            f"3. **Observability:** Centralized audit and log streaming.\n\n"
            f"What else would you like me to detail for you?"
        )
        suggestions = ["Explain component interactions", "Show security details", "What is the cost breakdown?"]

    return ans, suggestions

@router.post("/{analysis_id}/send", response_model=ChatMessageResponse)
def send_chat_message(
    analysis_id: str,
    payload: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == current_user.id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    # Get or create chat history
    chat = db.query(ChatHistory).filter(
        ChatHistory.analysis_id == analysis_id,
        ChatHistory.user_id == current_user.id
    ).first()
    
    if not chat:
        chat = ChatHistory(
            analysis_id=analysis_id,
            user_id=current_user.id,
            messages=[]
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)
        
    # User message
    user_msg = {
        "role": "user",
        "content": payload.content,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Generate bot response with Sulaiman AI persona
    ans_content, suggestions = generate_contextual_response(payload.content, analysis)
    
    bot_msg = {
        "role": "assistant",
        "content": ans_content,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Update messages
    msgs = list(chat.messages)
    msgs.append(user_msg)
    msgs.append(bot_msg)
    chat.messages = msgs
    
    db.commit()
    
    return ChatMessageResponse(
        response=ans_content,
        follow_up_suggestions=suggestions,
        conversation_length=len(msgs)
    )

@router.get("/{analysis_id}/history")
def get_chat_history(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = db.query(ChatHistory).filter(
        ChatHistory.analysis_id == analysis_id,
        ChatHistory.user_id == current_user.id
    ).first()
    
    if not chat:
        return {"messages": []}
        
    return {"messages": chat.messages}

@router.post("/{analysis_id}/clear")
def clear_chat_history(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = db.query(ChatHistory).filter(
        ChatHistory.analysis_id == analysis_id,
        ChatHistory.user_id == current_user.id
    ).first()
    
    if chat:
        chat.messages = []
        db.commit()
        
    return {"success": True}
