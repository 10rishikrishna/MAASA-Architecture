import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Text, DateTime, Float, ForeignKey, JSON, Index, Boolean, Integer
from sqlalchemy.orm import sessionmaker, relationship, DeclarativeBase
from backend.config import settings

# Setup engine and session
engine_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}
else:
    engine_args["pool_size"] = 20
    engine_args["max_overflow"] = 10
    engine_args["pool_pre_ping"] = True
    engine_args["pool_recycle"] = 3600

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

def generate_uuid():
    return str(uuid.uuid4())


# ── Models ────────────────────────────────────────────────────────────────────

def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    profile_picture_url = Column(Text, nullable=True)
    plan = Column(String(50), default="free")
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    deleted_at = Column(DateTime, nullable=True)

    analyses = relationship("Analysis", back_populates="user")
    projects = relationship("Project", back_populates="user")
    teams_owned = relationship("Team", back_populates="owner")
    team_memberships = relationship("TeamMember", back_populates="user")
    api_keys = relationship("ApiKey", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")

    __table_args__ = (
        Index("idx_users_email_active", "email", "is_active"),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    device_info = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_refresh_tokens_user_active", "user_id", "revoked_at"),
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    device_info = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    last_activity_at = Column(DateTime, default=_utcnow)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("idx_sessions_user_active", "user_id", "expires_at"),
    )


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    business_problem = Column(Text, nullable=False)

    requirements = Column(JSON, nullable=True)
    architecture_design = Column(JSON, nullable=True)
    database_schema = Column(JSON, nullable=True)
    api_specification = Column(JSON, nullable=True)
    deployment_config = Column(JSON, nullable=True)
    security_audit = Column(JSON, nullable=True)
    performance_strategies = Column(JSON, nullable=True)
    diagrams = Column(JSON, nullable=True)

    status = Column(String(50), default="processing")
    analysis_time_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="analyses")
    chat_histories = relationship("ChatHistory", back_populates="analysis")

    __table_args__ = (
        Index("idx_analyses_user_status", "user_id", "status"),
        Index("idx_analyses_created", "created_at"),
    )


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    analysis_ids = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    visibility = Column(String(50), default="private")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="projects")
    team = relationship("Team", back_populates="projects")
    shares = relationship("ProjectShare", back_populates="project")

    __table_args__ = (
        Index("idx_projects_user_visibility", "user_id", "visibility"),
    )


class ChatHistory(Base):
    __tablename__ = "chat_histories"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    messages = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    analysis = relationship("Analysis", back_populates="chat_histories")

    __table_args__ = (
        Index("idx_chat_analysis_user", "analysis_id", "user_id"),
    )


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    owner = relationship("User", back_populates="teams_owned")
    members = relationship("TeamMember", back_populates="team")
    projects = relationship("Project", back_populates="team")


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(50), default="member")
    joined_at = Column(DateTime, default=_utcnow)

    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")

    __table_args__ = (
        Index("idx_team_members_unique", "team_id", "user_id", unique=True),
    )


class ProjectShare(Base):
    __tablename__ = "project_shares"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    shared_with_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    shared_with_team_id = Column(String(36), ForeignKey("teams.id"), nullable=True)
    permission = Column(String(50), default="view")
    created_at = Column(DateTime, default=_utcnow)

    project = relationship("Project", back_populates="shares")

    __table_args__ = (
        Index("idx_project_shares_project", "project_id"),
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    key_hash = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index("idx_api_keys_user", "user_id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=True, index=True)
    action = Column(String(255), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(36), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)

    __table_args__ = (
        Index("idx_audit_user_action", "user_id", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )


class RateLimit(Base):
    __tablename__ = "rate_limits"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    identifier = Column(String(255), nullable=False, index=True)
    endpoint = Column(String(255), nullable=False)
    request_count = Column(Integer, default=1)
    window_start = Column(DateTime, default=_utcnow)
    blocked_until = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_rate_limit_identifier", "identifier", "endpoint"),
    )


# Helper to initialize DB
def init_db():
    Base.metadata.create_all(bind=engine)
