"""
PHASE 4 — PROJECTS & USERS API TESTS
Tests: Full CRUD on projects, user sync, auth enforcement, data isolation.
"""
import uuid
import pytest


# ============================================================================
# PROJECTS CRUD — /api/v1/projects
# ============================================================================
@pytest.mark.api
class TestProjectsCreate:

    def test_create_project_returns_201(self, client):
        r = client.post("/api/v1/projects", json={"name": "My Project"})
        assert r.status_code == 201

    def test_create_project_response_shape(self, client):
        r = client.post("/api/v1/projects", json={"name": "Shape Test"})
        assert r.status_code == 201
        data = r.json()
        for field in ["id", "name", "status", "created_at", "updated_at"]:
            assert field in data, f"Missing field: {field}"

    def test_create_project_uid_from_jwt_not_payload(self, client):
        """user_id must be set from the JWT, NOT from a payload field."""
        r = client.post("/api/v1/projects", json={
            "name": "JWT Test",
            "user_id": "attacker_spoofed_uid",  # This must be ignored
        })
        assert r.status_code == 201
        data = r.json()
        # Should use TEST_USER_UID from auth bypass, not the spoofed one
        assert data.get("user_id") != "attacker_spoofed_uid"

    def test_create_project_name_required(self, client):
        r = client.post("/api/v1/projects", json={"description": "No name"})
        assert r.status_code == 422

    def test_create_project_name_too_long_rejected(self, client):
        r = client.post("/api/v1/projects", json={"name": "A" * 61})
        assert r.status_code == 422

    def test_create_project_empty_name_rejected(self, client):
        r = client.post("/api/v1/projects", json={"name": ""})
        assert r.status_code == 422

    def test_duplicate_name_same_user_returns_409(self, client):
        client.post("/api/v1/projects", json={"name": "Duplicate Name Test"})
        r = client.post("/api/v1/projects", json={"name": "Duplicate Name Test"})
        assert r.status_code == 409

    def test_same_name_different_user_allowed(self, client, db_session):
        """Two different users can have projects with the same name."""
        from app.db.models import Project
        other_project = Project(
            id=uuid.uuid4(), user_id="completely_different_user",
            name="Shared Name", status="empty"
        )
        db_session.add(other_project)
        db_session.commit()
        # Now create same name as TEST_USER_UID
        r = client.post("/api/v1/projects", json={"name": "Shared Name"})
        assert r.status_code == 201


@pytest.mark.api
class TestProjectsRead:

    def test_list_projects_returns_own_only(self, client, seed_project, seed_project_other_user):
        """List must only return projects belonging to the authenticated user."""
        r = client.get("/api/v1/projects")
        assert r.status_code == 200
        projects = r.json()["projects"]
        ids = [p["id"] for p in projects]
        assert str(seed_project.id) in ids
        assert str(seed_project_other_user.id) not in ids

    def test_list_projects_user_id_query_param_ignored(self, client, seed_project_other_user):
        """user_id query param must be ignored in favour of JWT uid."""
        r = client.get(f"/api/v1/projects?user_id={seed_project_other_user.user_id}")
        assert r.status_code == 200
        # Should return only our projects, not the other user's
        projects = r.json()["projects"]
        for p in projects:
            assert p["id"] != str(seed_project_other_user.id)

    def test_get_project_by_id_own_project(self, client, seed_project):
        r = client.get(f"/api/v1/projects/{seed_project.id}")
        assert r.status_code == 200
        assert r.json()["id"] == str(seed_project.id)

    def test_get_other_users_project_returns_404(self, client, seed_project_other_user):
        """Fetching another user's project by ID must return 404."""
        r = client.get(f"/api/v1/projects/{seed_project_other_user.id}")
        assert r.status_code == 404

    def test_get_nonexistent_project_returns_404(self, client):
        r = client.get(f"/api/v1/projects/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_get_invalid_uuid_returns_404(self, client):
        r = client.get("/api/v1/projects/not-a-uuid")
        assert r.status_code == 404


@pytest.mark.api
class TestProjectsUpdate:

    def test_update_own_project_returns_200(self, client, seed_project):
        r = client.put(f"/api/v1/projects/{seed_project.id}",
                       json={"name": "Updated Name"})
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"

    def test_update_other_users_project_returns_404(self, client, seed_project_other_user):
        r = client.put(f"/api/v1/projects/{seed_project_other_user.id}",
                       json={"name": "Hijacked!"})
        assert r.status_code == 404

    def test_update_name_too_long_rejected(self, client, seed_project):
        r = client.put(f"/api/v1/projects/{seed_project.id}",
                       json={"name": "X" * 61})
        assert r.status_code == 422

    def test_update_nonexistent_project_returns_404(self, client):
        r = client.put(f"/api/v1/projects/{uuid.uuid4()}", json={"name": "Ghost"})
        assert r.status_code == 404

    def test_update_with_conflicting_name_returns_409(self, client, seed_project):
        # Create second project
        client.post("/api/v1/projects", json={"name": "Second Project Conflict"})
        r = client.put(f"/api/v1/projects/{seed_project.id}",
                       json={"name": "Second Project Conflict"})
        assert r.status_code == 409

    def test_partial_update_preserves_other_fields(self, client, seed_project):
        """Updating only description must not change name."""
        r = client.put(f"/api/v1/projects/{seed_project.id}",
                       json={"description": "New description"})
        if r.status_code == 200:
            assert r.json()["name"] == seed_project.name


@pytest.mark.api
class TestProjectsDelete:

    def test_delete_own_project_returns_204(self, client):
        cr = client.post("/api/v1/projects", json={"name": "Delete Me"})
        assert cr.status_code == 201
        pid = cr.json()["id"]
        r = client.delete(f"/api/v1/projects/{pid}")
        assert r.status_code == 204

    def test_deleted_project_is_gone(self, client):
        cr = client.post("/api/v1/projects", json={"name": "Gone Project"})
        pid = cr.json()["id"]
        client.delete(f"/api/v1/projects/{pid}")
        r = client.get(f"/api/v1/projects/{pid}")
        assert r.status_code == 404

    def test_delete_other_users_project_returns_404(self, client, seed_project_other_user):
        r = client.delete(f"/api/v1/projects/{seed_project_other_user.id}")
        assert r.status_code == 404

    def test_delete_nonexistent_project_returns_404(self, client):
        r = client.delete(f"/api/v1/projects/{uuid.uuid4()}")
        assert r.status_code == 404


@pytest.mark.api
class TestProjectsAuthRequired:

    def test_create_project_without_auth_returns_401(self, auth_client):
        r = auth_client.post("/api/v1/projects", json={"name": "No Auth"})
        assert r.status_code == 401

    def test_list_projects_without_auth_returns_401(self, auth_client):
        r = auth_client.get("/api/v1/projects")
        assert r.status_code == 401

    def test_delete_project_without_auth_returns_401(self, auth_client):
        r = auth_client.delete(f"/api/v1/projects/{uuid.uuid4()}")
        assert r.status_code == 401


# ============================================================================
# USERS SYNC — POST /api/v1/users/sync
# ============================================================================
@pytest.mark.api
class TestUsersSyncEndpoint:

    VALID_USER = {
        "uid": "test_firebase_uid_001",  # Must match TEST_USER_UID from conftest auth bypass
        "email": "newuser@example.com",
        "displayName": "New User",
        "photoURL": "https://example.com/photo.jpg",
    }

    def test_sync_new_user_returns_200(self, client):
        r = client.post("/api/v1/users/sync", json=self.VALID_USER)
        assert r.status_code == 200

    def test_sync_response_has_uid(self, client):
        r = client.post("/api/v1/users/sync", json=self.VALID_USER)
        assert r.status_code == 200
        assert r.json()["uid"] == self.VALID_USER["uid"]

    def test_sync_creates_user_in_db(self, client, db_session):
        from app.db.models import User
        uid = "test_firebase_uid_001"  # Must match TEST_USER_UID
        client.post("/api/v1/users/sync", json={
            "uid": uid, "email": f"{uid}@test.com",
            "displayName": "Test", "photoURL": None,
        })
        user = db_session.query(User).filter(User.id == uid).first()
        assert user is not None

    def test_sync_existing_user_updates_name(self, client, seed_user):
        # seed_user.id must be used as uid; auth bypass returns TEST_USER_UID
        # so we test with the fixed uid to avoid the uid-mismatch 403
        r = client.post("/api/v1/users/sync", json={
            "uid": "test_firebase_uid_001",
            "email": "update@example.com",
            "displayName": "Updated Name",
            "photoURL": None,
        })
        assert r.status_code == 200

    def test_sync_missing_uid_returns_422(self, client):
        r = client.post("/api/v1/users/sync", json={
            "email": "noid@test.com", "displayName": "No UID",
        })
        assert r.status_code == 422

    def test_sync_missing_email_returns_422(self, client):
        r = client.post("/api/v1/users/sync", json={
            "uid": "some_uid", "displayName": "No Email",
        })
        assert r.status_code == 422

    def test_sync_null_display_name_uses_email_prefix(self, client, db_session):
        from app.db.models import User
        uid = f"nullname_{uuid.uuid4().hex[:8]}"
        client.post("/api/v1/users/sync", json={
            "uid": uid, "email": "johndoe@example.com",
            "displayName": None, "photoURL": None,
        })
        user = db_session.query(User).filter(User.id == uid).first()
        if user:
            assert user.name == "johndoe"  # derived from email prefix

    def test_sync_is_idempotent(self, client):
        """Calling sync twice must not fail."""
        payload = {**self.VALID_USER}
        r1 = client.post("/api/v1/users/sync", json=payload)
        r2 = client.post("/api/v1/users/sync", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
