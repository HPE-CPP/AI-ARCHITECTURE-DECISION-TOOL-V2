"""
Projects router — full CRUD backed by PostgreSQL.
Response shapes are identical to the original in-memory implementation.
"""
import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
from app.core.security import verify_firebase_token

router = APIRouter()
logger = logging.getLogger(__name__)


def _to_response(project: Project) -> dict:
    """Serialise ORM Project to the original API response shape."""
    return {
        "id": str(project.id),
        "user_id": project.user_id,
        "name": project.name,
        "description": project.description or "",
        "status": project.status,
        "analysis_id": project.analysis_id,
        "mode": project.mode,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# POST /api/v1/projects  — create
# ---------------------------------------------------------------------------
@router.post("/projects", status_code=201)
def create_project(
    data: ProjectCreate,
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token)
):
    """Create a new project."""
    user_id = uid if uid else data.user_id
    if not user_id:
        raise HTTPException(401, "Authentication required: Must provide a valid token or guest user_id")
    if not uid and not user_id.startswith("guest_"):
        raise HTTPException(401, "Authentication required for non-guest users")

    # Enforce unique name per user_id
    existing = db.query(Project).filter(
        Project.user_id == user_id,
        Project.name == data.name.strip(),
    ).first()
    if existing:
        raise HTTPException(409, f"A project named '{data.name.strip()}' already exists.")

    now = datetime.utcnow()
    project = Project(
        id=uuid.uuid4(),
        user_id=user_id,
        name=data.name.strip(),
        description=(data.description or "").strip(),
        status="empty",
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_response(project)


# ---------------------------------------------------------------------------
# GET /api/v1/projects  — list (filter by user_id)
# ---------------------------------------------------------------------------
@router.get("/projects")
def list_projects(
    user_id: Optional[str] = Query(default=None),
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token)
):
    """List all projects for the authenticated user."""
    actual_user_id = uid if uid else user_id
    if not actual_user_id:
        raise HTTPException(401, "Authentication required")
    if not uid and not actual_user_id.startswith("guest_"):
        raise HTTPException(401, "Authentication required for non-guest users")

    q = db.query(Project).filter(Project.user_id == actual_user_id)
    projects = q.order_by(Project.updated_at.desc()).all()
    return {"projects": [_to_response(p) for p in projects]}


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------
@router.get("/projects/{project_id}")
def get_project(
    project_id: str,
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token)
):
    """Get a single project by ID."""
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(404, "Project not found")

    project = q.first()
    if not project:
        raise HTTPException(404, "Project not found")

    if not uid and not project.user_id.startswith("guest_"):
        raise HTTPException(401, "Authentication required for non-guest users")

    return _to_response(project)


# ---------------------------------------------------------------------------
# PUT /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------
@router.put("/projects/{project_id}")
def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token)
):
    """Update a project's metadata."""
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(404, "Project not found")

    q = db.query(Project).filter(Project.id == pid)
    if uid:
        q = q.filter(Project.user_id == uid)

    project = q.first()
    if not project:
        raise HTTPException(404, "Project not found")

    if not uid and not project.user_id.startswith("guest_"):
        raise HTTPException(401, "Authentication required for non-guest users")

    if data.name is not None:
        # Check name uniqueness (skip if same project)
        conflict = db.query(Project).filter(
            Project.user_id == project.user_id,
            Project.name == data.name.strip(),
            Project.id != pid,
        ).first()
        if conflict:
            raise HTTPException(409, f"A project named '{data.name.strip()}' already exists.")
        project.name = data.name.strip()

    if data.description is not None:
        project.description = data.description.strip()
    if data.status is not None:
        project.status = data.status
    # SEC-002 FIX: data.user_id removed from schema — ownership is immutable
    if data.analysis_id is not None:
        project.analysis_id = data.analysis_id
    if data.mode is not None:
        project.mode = data.mode

    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return _to_response(project)


# ---------------------------------------------------------------------------
# DELETE /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------
@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token)
):
    """Delete a project."""
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(404, "Project not found")

    q = db.query(Project).filter(Project.id == pid)
    if uid:
        q = q.filter(Project.user_id == uid)

    project = q.first()
    if not project:
        raise HTTPException(404, "Project not found")

    if not uid and not project.user_id.startswith("guest_"):
        raise HTTPException(401, "Authentication required for non-guest users")

    db.delete(project)
    db.commit()
    return None
