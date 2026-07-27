# backend/routers/chat.py
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

def generate_contextual_response(question: str, analysis: Analysis) -> tuple[str, List[str]]:
    q = question.lower().strip()
    
    # Extract contextual metadata from analysis
    arch = analysis.architecture_design or {}
    pattern = arch.get("pattern", "Microservices Architecture")
    sys_type = arch.get("system_type", "Domain Architecture")
    components = arch.get("components", [])
    comp_names = [c.get("name", "Service") for c in components] if components else ["Core API Service", "Auth Service"]
    
    db_schema = analysis.database_schema or {}
    db_type = db_schema.get("database_type", "PostgreSQL")
    
    sec_audit = analysis.security_audit or {}
    compliance = sec_audit.get("compliance", "SOC2 / GDPR compliance")
    scores = sec_audit.get("scores", {})
    sec_score = scores.get("security", 90)
    
    api_spec = analysis.api_specification or {}
    endpoints = api_spec.get("endpoints", [])
    
    # 1. Greetings & System Overview
    if any(k in q for k in ["hi", "hello", "hey", "describe", "explain my project", "overview", "what is this system", "tell me about"]):
        comp_str = ", ".join(comp_names[:4]) if comp_names else "Core Services"
        ans = (
            f"Hello! I am your AI Lead Architect for **{analysis.business_problem[:60]}...**\n\n"
            f"**System Architecture Overview:**\n"
            f"- **System Type:** {sys_type}\n"
            f"- **Pattern:** {pattern}\n"
            f"- **Core Building Blocks:** {comp_str}\n"
            f"- **Database Stack:** {db_type}\n"
            f"- **Security Score:** {sec_score}/100 ({compliance})\n\n"
            f"What specific component, API endpoint, or cloud deployment strategy would you like to discuss?"
        )
        suggestions = ["Why this architecture pattern?", "List all API endpoints", "Explain the database schema"]

    # 2. Architecture Pattern & Justification
    elif any(k in q for k in ["why", "pattern", "microservices", "monolith", "topology", "architecture"]):
        justification = arch.get("justification", f"Selected {pattern} for optimal component isolation.")
        ans = (
            f"**Architecture Decision Record (ADR):**\n\n"
            f"We selected **{pattern}** for your system.\n\n"
            f"**Rationale:**\n{justification}\n\n"
            f"**Key Benefits:**\n"
            f"- **Fault Domain Isolation:** Failures in background workloads won't crash user authentication or telemetry ingestion.\n"
            f"- **Targeted Autoscaling:** High-traffic services ({comp_names[0] if comp_names else 'API Gateway'}) can scale independently.\n"
            f"- **Maintainability:** Clear boundaries reduce code coupling as team size scales."
        )
        suggestions = ["What are the trade-offs?", "Migration path from monolith?", "How does load balancing work?"]

    # 3. Component Details & Technology Choices
    elif any(k in q for k in ["component", "service", "stack", "technology", "tech", "node", "building block"]):
        comp_details = ""
        for c in components[:5]:
            c_name = c.get("name", "Service")
            c_tech = c.get("technology", "FastAPI / Node.js")
            c_reason = c.get("reason", "Handles domain workflows.")
            comp_details += f"- **{c_name}** (`{c_tech}`): {c_reason}\n"
            
        ans = (
            f"Here are the core service components designed for this system:\n\n"
            f"{comp_details}\n"
            f"Each service communicates asynchronously via event streams or gRPC internal protocols."
        )
        suggestions = ["How do components handle failures?", "Explain database choices", "What is the security design?"]

    # 4. Database Schema & Storage
    elif any(k in q for k in ["database", "db", "sql", "postgres", "schema", "tables", "storage", "redis"]):
        tables = db_schema.get("schemas", [])
        tbl_names = [t.get("table_name", "entities") for t in tables] if tables else ["users", "events"]
        ans = (
            f"**Database Architecture:**\n\n"
            f"Primary Storage: **{db_type}**\n\n"
            f"**Core Schemas & Partitioning:**\n"
            f"- Defined Tables: `{', '.join(tbl_names)}`\n"
            f"- **ACID Guarantees:** Strict transactional safety enforced for financial and state mutations.\n"
            f"- **Indexing:** B-Tree indexes configured on primary lookup keys for sub-10ms query execution."
        )
        suggestions = ["Show me the SQL DDL?", "How is caching configured?", "What if database load spikes?"]

    # 5. API Specification & Endpoints
    elif any(k in q for k in ["api", "endpoint", "rest", "swagger", "openapi", "grpc", "routes"]):
        ep_text = ""
        for ep in endpoints[:3]:
            ep_text += f"- `{ep.get('method', 'GET')}` **{ep.get('path', '/api/v1')}**: {ep.get('description', '')}\n"
            
        ans = (
            f"**API Specifications:**\n\n"
            f"Protocol: **{api_spec.get('protocol', 'REST HTTP / JSON')}**\n\n"
            f"**Key Endpoints:**\n{ep_text if ep_text else '- POST /api/v1/events: Ingest operational events'}\n"
            f"All endpoints enforce Bearer JWT Authentication and rate-limiting at the API Gateway level."
        )
        suggestions = ["How are API tokens validated?", "Is there rate limiting?", "Show payload examples"]

    # 6. Security & Vulnerabilities
    elif any(k in q for k in ["security", "vulnerability", "auth", "jwt", "compliance", "hipaa", "soc2", "audit"]):
        mitigations = sec_audit.get("vulnerability_mitigations", [])
        mit_text = "\n".join([f"- {m}" for m in mitigations[:3]])
        ans = (
            f"**Security Audit Summary (Score: {sec_score}/100):**\n\n"
            f"**Compliance Target:** {compliance}\n\n"
            f"**Vulnerability Mitigations:**\n"
            f"{mit_text}\n\n"
            f"**Zero-Trust Security:** All intra-service communications use TLS 1.3 encryption with strict IAM role access."
        )
        suggestions = ["How to prepare for SOC2 audit?", "Can we add 2FA?", "How is data encrypted at rest?"]

    # 7. Costs & Cloud Infrastructure
    elif any(k in q for k in ["cost", "aws", "budget", "price", "cloud", "terraform", "k8s", "kubernetes"]):
        ans = (
            f"**Cloud Budget & Infrastructure Breakdown (AWS Target):**\n\n"
            f"| Component | Technology | Estimated Cost/mo |\n"
            f"| --- | --- | --- |\n"
            f"| **API Gateway / CDN** | Cloudflare WAF + AWS ALB | $25.00 |\n"
            f"| **Compute Containers** | AWS ECS Fargate / EKS | $65.00 |\n"
            f"| **Database Cluster** | Amazon RDS ({db_type.split('+')[0]}) | $120.00 |\n"
            f"| **Cache & Queue** | ElastiCache Redis | $30.00 |\n"
            f"| **Total Projected** | **Production Grade** | **~$240.00/month** |\n\n"
            f"Terraform IaC scripts and Kubernetes manifests are ready under the Deployment tab."
        )
        suggestions = ["How to reduce database costs?", "Can we deploy on Kubernetes?", "What if traffic doubles?"]

    # 8. Fallback (Contextual Dynamic Answer)
    else:
        ans = (
            f"Great question regarding **{question}** for your system!\n\n"
            f"In this **{pattern}** design for **{sys_type}**, we handle `{question}` by leveraging the **{comp_names[0] if comp_names else 'Core API'}** "
            f"and our **{db_type}** storage layer.\n\n"
            f"Key considerations:\n"
            f"1. **Isolation:** Ensured by component boundaries so other services remain unaffected.\n"
            f"2. **Resilience:** Automatic retry policies with exponential backoff at the gateway.\n"
            f"3. **Monitoring:** Centralized log ingestion via audit pipelines.\n\n"
            f"Would you like me to elaborate on the implementation code, database locks, or security controls for this?"
        )
        suggestions = ["Explain component interaction", "Show security details", "What is the cost breakdown?"]

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
    
    # Generate bot response
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
