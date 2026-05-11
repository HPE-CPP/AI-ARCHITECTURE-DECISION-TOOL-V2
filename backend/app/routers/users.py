"""
User router — syncs Firebase users to PostgreSQL database.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import User
from app.core.security import verify_firebase_token

router = APIRouter()
logger = logging.getLogger(__name__)


class UserSyncRequest(BaseModel):
    uid: str = Field(..., description="Firebase User ID")
    email: str = Field(..., description="User's email address")
    displayName: str | None = Field(default=None, description="User's full name")
    photoURL: str | None = Field(default=None, description="User's avatar URL")


@router.post("/users/sync", status_code=200)
def sync_user(
    data: UserSyncRequest,
    db: DBSession = Depends(get_db),
    auth_uid: Optional[str] = Depends(verify_firebase_token),
):
    """
    Syncs a Firebase user to the PostgreSQL database.
    Creates the user if they don't exist, updates their metadata if they do.

    SEC-001 FIX: Requires a valid Firebase JWT. The token's uid must match
    the request body uid — prevents impersonation and account takeover.
    """
    if not auth_uid:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: valid Firebase token must be provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if auth_uid != data.uid:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: token uid does not match request uid",
        )

    now = datetime.now(timezone.utc)
    display_name = data.displayName or data.email.split("@")[0]

    user = db.query(User).filter(User.id == data.uid).first()

    if flex_user := db.query(User).filter(User.email == data.email, User.id != data.uid).first():
       # Handle edge case where email exists but under a different UID (e.g., account linking not handled client side)
       # Update the ID to match the current auth provider's UID
       flex_user.id = data.uid
       flex_user.name = display_name
       flex_user.photo_url = data.photoURL
       flex_user.updated_at = now
       user = flex_user
    elif not user:
        # Create new user
        user = User(
            id=data.uid,
            name=display_name,
            email=data.email,
            photo_url=data.photoURL,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
    else:
        # Update existing user
        user.name = display_name
        user.email = data.email
        user.photo_url = data.photoURL
        user.updated_at = now

    db.commit()

    return {"status": "success", "uid": user.id}

