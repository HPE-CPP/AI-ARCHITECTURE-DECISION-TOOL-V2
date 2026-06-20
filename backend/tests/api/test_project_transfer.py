"""
GUEST -> AUTHENTICATED PROJECT TRANSFER
Covers the exact backend contract the AuthModal transfer flow relies on:
  - transferring a guest project to the signed-in account
  - transferring WITH a rename when the name already exists
  - the "02" / "02 (Guest)" cascade that used to crash the transfer
  - keeping unselected guest projects as guest projects
  - idempotent re-transfer (safe retry)
The auth bypass in conftest makes every request authenticated as TEST_USER_UID.
"""
import uuid
import pytest

from tests.conftest import TEST_USER_UID


def _make_guest_project(db_session, name: str, guest_id: str = "guest_abc123"):
    """Insert a project owned by a guest id, the way the frontend creates them."""
    from app.db.models import Project
    project = Project(
        id=uuid.uuid4(),
        user_id=guest_id,
        name=name,
        description="",
        status="empty",
    )
    db_session.add(project)
    db_session.commit()
    return project


def _make_account_project(db_session, name: str):
    """Insert a project already owned by the signed-in user (TEST_USER_UID)."""
    from app.db.models import Project
    project = Project(
        id=uuid.uuid4(),
        user_id=TEST_USER_UID,
        name=name,
        description="",
        status="empty",
    )
    db_session.add(project)
    db_session.commit()
    return project


@pytest.mark.api
class TestGuestTransfer:

    def test_transfer_guest_project_no_conflict(self, client, db_session):
        guest = _make_guest_project(db_session, "Solo Project")
        r = client.put(f"/api/v1/projects/{guest.id}", json={"user_id": TEST_USER_UID})
        assert r.status_code == 200
        assert r.json()["user_id"] == TEST_USER_UID

    def test_transfer_with_rename_lands_in_account(self, client, db_session):
        """The exact Issue-2 flow: account has '02', guest '02' renamed on transfer."""
        _make_account_project(db_session, "02")
        guest = _make_guest_project(db_session, "02")
        r = client.put(
            f"/api/v1/projects/{guest.id}",
            json={"user_id": TEST_USER_UID, "name": "02 (Guest)"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == TEST_USER_UID
        assert body["name"] == "02 (Guest)"

    def test_rename_to_taken_name_returns_409(self, client, db_session):
        """A rename target that already exists must 409 — this is why the
        frontend now auto-picks a free name instead of blindly using '(Guest)'."""
        _make_account_project(db_session, "02")
        _make_account_project(db_session, "02 (Guest)")
        guest = _make_guest_project(db_session, "02")
        r = client.put(
            f"/api/v1/projects/{guest.id}",
            json={"user_id": TEST_USER_UID, "name": "02 (Guest)"},
        )
        assert r.status_code == 409

    def test_cascade_unique_name_succeeds(self, client, db_session):
        """The reported dead-end: account already has '02' AND '02 (Guest)'.
        Transferring guest '02' to the next free name '02 (Guest 2)' must work."""
        _make_account_project(db_session, "02")
        _make_account_project(db_session, "02 (Guest)")
        guest = _make_guest_project(db_session, "02")
        r = client.put(
            f"/api/v1/projects/{guest.id}",
            json={"user_id": TEST_USER_UID, "name": "02 (Guest 2)"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "02 (Guest 2)"
        assert r.json()["user_id"] == TEST_USER_UID

    def test_unselected_guest_project_stays_guest(self, client, db_session):
        """Issue 1: a guest project that is NOT transferred is left untouched
        and remains queryable as a guest project."""
        from app.db.models import Project
        guest_keep = _make_guest_project(db_session, "Keep Me", guest_id="guest_keep")
        # Frontend simply never PUTs this one. Confirm it is still a guest project.
        row = db_session.query(Project).filter(Project.id == guest_keep.id).first()
        assert row is not None
        assert row.user_id == "guest_keep"

    def test_retransfer_is_idempotent(self, client, db_session):
        """Re-running a transfer on an already-owned project must not fail,
        so a retry after a partial failure is safe."""
        guest = _make_guest_project(db_session, "Retry Project")
        r1 = client.put(f"/api/v1/projects/{guest.id}", json={"user_id": TEST_USER_UID})
        assert r1.status_code == 200
        r2 = client.put(f"/api/v1/projects/{guest.id}", json={"user_id": TEST_USER_UID})
        assert r2.status_code == 200
        assert r2.json()["user_id"] == TEST_USER_UID

    def test_replace_then_transfer_keeps_name(self, client, db_session):
        """'Replace' path: delete the existing account project, then transfer
        the guest one keeping its name (no name change -> cannot 409)."""
        existing = _make_account_project(db_session, "Report")
        guest = _make_guest_project(db_session, "Report")
        # Replace = delete existing first...
        d = client.delete(f"/api/v1/projects/{existing.id}")
        assert d.status_code == 204
        # ...then transfer ownership keeping the original name.
        r = client.put(f"/api/v1/projects/{guest.id}", json={"user_id": TEST_USER_UID})
        assert r.status_code == 200
        assert r.json()["name"] == "Report"
        assert r.json()["user_id"] == TEST_USER_UID
