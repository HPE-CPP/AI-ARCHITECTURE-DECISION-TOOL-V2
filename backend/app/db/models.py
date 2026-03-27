"""
All SQLAlchemy ORM models for the AI Architecture Decision Platform.
Tables: User, Project, Session, Signal, Result

Timestamps: all stored as TIMESTAMP WITH TIME ZONE (UTC).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Text, Float, Integer, DateTime, ForeignKey, Index, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def now_utc() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # Firebase UID
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="google")
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    projects: Mapped[list["Project"]] = relationship(
        "Project", 
        back_populates="user", 
        primaryjoin="User.id == Project.user_id",
        foreign_keys="Project.user_id"
    )


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="empty")
    analysis_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    user: Mapped["User | None"] = relationship(
        "User", 
        back_populates="projects", 
        primaryjoin="Project.user_id == User.id",
        foreign_keys=[user_id]
    )
    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="project")


# ---------------------------------------------------------------------------
# Session  (one analysis run = one session)
# ---------------------------------------------------------------------------
class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        SAEnum("draft", "processing", "completed", "error", name="session_status_enum"),
        nullable=False,
        default="draft",
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="openai")
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    project: Mapped["Project | None"] = relationship("Project", back_populates="sessions")
    signals: Mapped[list["Signal"]] = relationship(
        "Signal", back_populates="session", cascade="all, delete-orphan"
    )
    result: Mapped["Result | None"] = relationship(
        "Result", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Signal  (one row per signal per session)
# ---------------------------------------------------------------------------
class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signal_name: Mapped[str] = mapped_column(String(60), nullable=False)
    value: Mapped[str | None] = mapped_column(String(60), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    session: Mapped["Session"] = relationship("Session", back_populates="signals")


# ---------------------------------------------------------------------------
# Result  (one row per session)
# ---------------------------------------------------------------------------
class Result(Base):
    __tablename__ = "results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    recommended_architecture: Mapped[str] = mapped_column(String(60), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ranking: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    decision_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    why_not: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    suitability: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    followup_questions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    sensitivity: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    decision_trace: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    architecture_details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )

    session: Mapped["Session"] = relationship("Session", back_populates="result")
