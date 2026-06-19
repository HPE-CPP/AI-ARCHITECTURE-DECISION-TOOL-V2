"""
Pydantic schemas for Projects — request bodies and response shapes.
Mirrors the API contract of the original in-memory implementation exactly.
"""
import uuid
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ---------- Request bodies ----------

class ProjectCreate(BaseModel):
    user_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=60)
    description: Optional[str] = Field(default="", max_length=200)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    description: Optional[str] = Field(default=None, max_length=200)
    status: Optional[str] = None
    user_id: Optional[str] = Field(default=None, max_length=255)
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
    recommended_architecture: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_model(cls, project, db=None, arch_map: dict = None) -> "ProjectResponse":
        recommended_arch = None
        if project.status == "completed" and project.analysis_id:
            if arch_map is not None and project.analysis_id in arch_map:
                recommended_arch = arch_map[project.analysis_id]
            elif db is not None:
                from app.db.models import Result
                try:
                    aid_uuid = uuid.UUID(project.analysis_id)
                    res = db.query(Result.recommended_architecture).filter(
                        Result.session_id == aid_uuid
                    ).first()
                    if res:
                        recommended_arch = res[0]
                except ValueError:
                    pass
            else:
                for session in project.sessions:
                    if str(session.id) == project.analysis_id:
                        if session.result:
                            recommended_arch = session.result.recommended_architecture
                        break
        return cls(
            id=str(project.id),
            user_id=project.user_id,
            name=project.name,
            description=project.description or "",
            status=project.status,
            analysis_id=project.analysis_id,
            mode=project.mode,
            recommended_architecture=recommended_arch,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
        )


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
