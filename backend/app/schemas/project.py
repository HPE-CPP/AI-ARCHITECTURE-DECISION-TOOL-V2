"""
Pydantic schemas for Projects — request bodies and response shapes.
Mirrors the API contract of the original in-memory implementation exactly.
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ---------- Request bodies ----------

class ProjectCreate(BaseModel):
    user_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=60)
    description: Optional[str] = Field(default="", max_length=200)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    description: Optional[str] = Field(default=None, max_length=200)
    status: Optional[str] = None
    user_id: Optional[str] = None
    analysis_id: Optional[str] = None
    mode: Optional[str] = None


# ---------- Response ----------

class ProjectResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    name: str
    description: str
    status: str
    analysis_id: Optional[str] = None
    mode: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, project) -> "ProjectResponse":
        return cls(
            id=str(project.id),
            user_id=project.user_id,
            name=project.name,
            description=project.description or "",
            status=project.status,
            analysis_id=project.analysis_id,
            mode=project.mode,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
        )


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
