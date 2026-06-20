"""
Projects router — full CRUD backed by PostgreSQL.
Response shapes are identical to the original in-memory implementation.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.core.security import verify_firebase_token

router = APIRouter()
logger = logging.getLogger(__name__)


def _to_response(project: Project, db: DBSession = None, arch_map: dict = None) -> dict:
    """Serialise ORM Project to the original API response shape."""
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
    return {
        "id": str(project.id),
        "user_id": project.user_id,
        "name": project.name,
        "description": project.description or "",
        "status": project.status,
        "analysis_id": project.analysis_id,
        "mode": project.mode,
        "recommended_architecture": recommended_arch,
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

    now = datetime.now(timezone.utc)
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
    return _to_response(project, db=db)


# ---------------------------------------------------------------------------
# GET /api/v1/projects  — list (filter by user_id)
# ---------------------------------------------------------------------------
@router.get("/projects")
def list_projects(
    user_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token)
):
    """List projects — filter by user_id.

    When the caller is authenticated (uid is set), they can query:
    - Their own projects (user_id == uid)
    - Guest projects (user_id starts with "guest_") — needed to discover
      anonymous projects for the transfer flow after signing in.
    """
    if uid:
        # Authenticated — allow querying own projects or guest projects
        if user_id and user_id.startswith("guest_"):
            actual_user_id = user_id
        else:
            actual_user_id = uid
    else:
        # Unauthenticated — must provide a guest user_id
        actual_user_id = user_id
        if not actual_user_id:
            raise HTTPException(401, "Authentication required")
        if not actual_user_id.startswith("guest_"):
            raise HTTPException(401, "Authentication required for non-guest users")

    q = db.query(Project).filter(Project.user_id == actual_user_id)
    total = q.count()
    projects = q.order_by(Project.updated_at.desc()).offset(offset).limit(limit).all()

    # Batch fetch recommended architectures to prevent N+1 query overhead
    arch_map = {}
    analysis_ids = [p.analysis_id for p in projects if p.status == "completed" and p.analysis_id]
    if analysis_ids:
        from app.db.models import Result
        valid_uuids = []
        for aid in analysis_ids:
            try:
                valid_uuids.append(uuid.UUID(aid))
            except ValueError:
                pass
        if valid_uuids:
            results = db.query(Result.session_id, Result.recommended_architecture).filter(
                Result.session_id.in_(valid_uuids)
            ).all()
            arch_map = {str(r.session_id): r.recommended_architecture for r in results}

    return {
        "projects": [_to_response(p, db=db, arch_map=arch_map) for p in projects],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------
@router.get("/projects/{project_id}")
def get_project(
    project_id: str,
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token)
):
    """Get a single project by ID.

    SEC-003 FIX: Previous version called `q.first()` before `q` was ever
    assigned, causing a guaranteed NameError on every request to this endpoint.
    Now builds the query properly, applying the user_id scope when a JWT is
    present so users cannot enumerate other users' projects.
    """
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(404, "Project not found")

    q = db.query(Project).filter(Project.id == pid)
    if uid:
        # Scope to the authenticated user — prevents cross-user enumeration
        q = q.filter(Project.user_id == uid)

    project = q.first()
    if not project:
        raise HTTPException(404, "Project not found")

    if not uid and not project.user_id.startswith("guest_"):
        raise HTTPException(401, "Authentication required for non-guest users")

    return _to_response(project, db=db)


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

    # Find the project — when authenticated, try uid-scoped first, then fall back
    # to guest projects so the transfer flow works.
    project = db.query(Project).filter(Project.id == pid).first()
    if not project:
        raise HTTPException(404, "Project not found")

    if uid:
        # Authenticated caller — must own the project OR it must be a guest project
        if project.user_id != uid and not project.user_id.startswith("guest_"):
            raise HTTPException(403, "You do not have permission to update this project")
    else:
        # Unauthenticated caller — must match guest ID
        if not project.user_id.startswith("guest_"):
            raise HTTPException(401, "Authentication required for non-guest users")

    if data.user_id is not None:
        # Only allow user_id reassignment for guest-to-authenticated transfer
        if not uid:
            raise HTTPException(401, "Authentication required to transfer project ownership")
        if not project.user_id.startswith("guest_"):
            raise HTTPException(400, "Can only transfer projects owned by a guest user")
        if data.user_id != uid:
            raise HTTPException(403, "Project can only be transferred to your own account")
        project.user_id = data.user_id

    if data.name is not None:
        # Check name uniqueness under the (possibly new) user_id
        effective_user_id = data.user_id if data.user_id is not None else project.user_id
        conflict = db.query(Project).filter(
            Project.user_id == effective_user_id,
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
    if data.analysis_id is not None:
        project.analysis_id = data.analysis_id
    if data.mode is not None:
        project.mode = data.mode

    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    return _to_response(project, db=db)


# ---------------------------------------------------------------------------
# DELETE /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------
@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token)
):
    """Delete a project. Allows guests to delete their own projects."""
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(404, "Project not found")

    project = db.query(Project).filter(Project.id == pid).first()
    if not project:
        raise HTTPException(404, "Project not found")

    if uid:
        # Authenticated — must own the project OR it must be a guest project.
        # Guest projects can be deleted by any authenticated user during the
        # sign-in transfer flow (discard unselected / discard-all).
        if project.user_id != uid and not project.user_id.startswith("guest_"):
            raise HTTPException(403, "You do not have permission to delete this project")
    else:
        # Unauthenticated — must be a guest project
        if not project.user_id.startswith("guest_"):
            raise HTTPException(401, "Authentication required for non-guest projects")

    db.delete(project)
    db.commit()
    return None
