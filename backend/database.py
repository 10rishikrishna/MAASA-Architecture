import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import sessionmaker, relationship, DeclarativeBase
from backend.config import settings

# Setup engine and session
# connect_args={"check_same_thread": False} is required only for SQLite.
engine_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Generate UUID utility
def generate_uuid():
    return str(uuid.uuid4())

# Models definition based on PRD schemas

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    profile_picture_url = Column(Text, nullable=True)
    plan = Column(String(50), default="free")  # free, starter, pro, enterprise
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    analyses = relationship("Analysis", back_populates="user")
    projects = relationship("Project", back_populates="user")
    teams_owned = relationship("Team", back_populates="owner")
    team_memberships = relationship("TeamMember", back_populates="user")
    api_keys = relationship("ApiKey", back_populates="user")

class Analysis(Base):
    __tablename__ = "analyses"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    business_problem = Column(Text, nullable=False)
    
    # Store agents' outputs as structured JSON
    requirements = Column(JSON, nullable=True)
    architecture_design = Column(JSON, nullable=True)
    database_schema = Column(JSON, nullable=True)
    api_specification = Column(JSON, nullable=True)
    deployment_config = Column(JSON, nullable=True)
    security_audit = Column(JSON, nullable=True)
    performance_strategies = Column(JSON, nullable=True)
    diagrams = Column(JSON, nullable=True)  # { "mermaid": str, "ascii": str }
    
    status = Column(String(50), default="processing")  # processing, completed, failed
    analysis_time_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="analyses")
    chat_histories = relationship("ChatHistory", back_populates="analysis")

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # SQLite does not support native array types easily, so we store them as JSON lists
    analysis_ids = Column(JSON, default=list)  # list of strings (UUIDs)
    tags = Column(JSON, default=list)          # list of strings
    visibility = Column(String(50), default="private")  # private, public
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="projects")
    team = relationship("Team", back_populates="projects")
    shares = relationship("ProjectShare", back_populates="project")

class ChatHistory(Base):
    __tablename__ = "chat_histories"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Store list of messages: [{"role": "user"|"assistant", "content": str, "timestamp": str}]
    messages = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    analysis = relationship("Analysis", back_populates="chat_histories")

class Team(Base):
    __tablename__ = "teams"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    owner = relationship("User", back_populates="teams_owned")
    members = relationship("TeamMember", back_populates="team")
    projects = relationship("Project", back_populates="team")

class TeamMember(Base):
    __tablename__ = "team_members"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(50), default="member")  # admin, member, viewer
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")

class ProjectShare(Base):
    __tablename__ = "project_shares"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    shared_with_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    shared_with_team_id = Column(String(36), ForeignKey("teams.id"), nullable=True)
    permission = Column(String(50), default="view")  # view, comment, edit
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="shares")

class ApiKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="api_keys")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=True, index=True)
    action = Column(String(255), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(36), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

# Helper to initialize DB
def init_db():
    Base.metadata.create_all(bind=engine)
