# backend/routers/chat.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.database import get_db, User, Analysis, ChatHistory
from backend.auth import get_current_user
from backend.config import settings

router = APIRouter(prefix="/api/v1/chat", tags=["Architecture Discussion Chat"])

class ChatMessageRequest(BaseModel):
    content: str

class ChatMessageResponse(BaseModel):
    response: str
    follow_up_suggestions: List[str]
    conversation_length: int

def generate_contextual_response(question: str, analysis: Analysis) -> tuple[str, List[str]]:
    q = question.lower()
    pattern = analysis.architecture_design.get("pattern", "Microservices") if analysis.architecture_design else "Microservices"
    db_type = analysis.database_schema.get("database_type", "PostgreSQL") if analysis.database_schema else "PostgreSQL"
    
    # Pre-canned/highly contextual senior architect answers for standard developer queries
    if "why" in q and ("pattern" in q or "microservices" in q or "monolith" in q):
        ans = (
            f"Based on your requirements, the choice of **{pattern}** was made to satisfy high scalability constraints.\n\n"
            f"**Key reasons:**\n"
            f"- **Fault Isolation:** A crash in a background process (e.g., checkout/billing) won't bring down user authentication.\n"
            f"- **Independent Scaling:** Services with high traffic (like catalog cataloging) can scale to 10+ pods while billing runs on 1 pod, saving cloud costs.\n"
            f"- **Team Autonomy:** Enables multiple engineering teams to ship components in parallel without branch collision."
        )
        suggestions = ["Migration path from monolith?", "What is the team size needed?", "Detail the networking layout."]
    elif "migration" in q or "migrate" in q:
        ans = (
            f"To migrate from a legacy monolith to this **{pattern}** design, I recommend a **Strangler Fig Pattern**:\n\n"
            f"1. **Phase 1 (Weeks 1-2):** Deploy a reverse-proxy (e.g., Kong API Gateway) in front of your monolith.\n"
            f"2. **Phase 2 (Weeks 3-5):** Build the new User Auth service. Route `/api/v1/auth` traffic to it while routing other requests to the monolith.\n"
            f"3. **Phase 3 (Weeks 6-8):** Break out database tables for checkout. Implement dual-writes to synchronize the old monolith DB and the new PostgreSQL database, then shift traffic."
        )
        suggestions = ["How do we handle database replication?", "What's the cost difference?", "How does this handle failures?"]
    elif "cost" in q or "aws" in q or "budget" in q:
        ans = (
            f"Here is a detailed cloud budget cost projection on **AWS**:\n\n"
            f"| Component | Detail | Monthly Cost |\n"
            f"| --- | --- | --- |\n"
            f"| **API Gateway** | AWS Kong Gateway / ALB | $24.00 |\n"
            f"| **Compute** | AWS ECS Fargate (2 Tasks, 0.5 CPU, 1GB RAM) | $48.00 |\n"
            f"| **Database** | Amazon RDS PostgreSQL (db.t3.medium Multi-AZ) | $130.00 |\n"
            f"| **Cache** | Amazon ElastiCache Redis (cache.t3.micro) | $26.00 |\n"
            f"| **Total Est.** | **Production Infrastructure** | **~$228.00/month** |\n\n"
            f"This is well within your constraints and optimized for standard scaling needs."
        )
        suggestions = ["How to reduce database costs?", "Can we run this on Kubernetes instead?", "What if traffic doubles?"]
    elif "security" in q or "vulnerability" in q:
        ans = (
            f"Security audits for this architecture recommend the following layered approach:\n\n"
            f"1. **Data Isolation:** All database transactions run in private subnets, accessible only from the backend container security groups.\n"
            f"2. **Token Safety:** JWTs are hashed with a HMAC SHA-256 algorithm and stored in HTTP-only cookies on web clients.\n"
            f"3. **WAF Layer:** Cloudflare CDN performs SSL offloading and automatically blocks common SQLi/XSS scripts before hitting the API Gateway."
        )
        suggestions = ["What compliance mappings apply?", "How do we audit API keys?", "Can we add 2FA?"]
    else:
        # Default smart fallback utilizing analysis variables
        ans = (
            f"Regarding your query about *'{question}'* in reference to the system:\n\n"
            f"The architecture uses a **{pattern}** with **{db_type}**. "
            f"For this layout, you should ensure that components remain loosely coupled by communicating via REST APIs or event streams. "
            f"Let me know if you would like me to detail the API endpoints, explain database locks, or write the Dockerfiles."
        )
        suggestions = ["Why this architecture pattern?", "Migration path from monolith?", "What's the cost in AWS?"]
        
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
    
    # Update messages (make copy to trigger mutation check in SQLAlchemy)
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
