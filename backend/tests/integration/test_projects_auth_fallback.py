import base64
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _make_jwt(payload: dict) -> str:
    def _b64(data: dict) -> str:
        raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    return f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(payload)}.signature"


@pytest.mark.integration
def test_try_get_firebase_uid_falls_back_to_unverified_jwt_payload():
    from fastapi.security import HTTPAuthorizationCredentials

    from app.core.security import try_get_firebase_uid

    token = _make_jwt({"sub": "firebase-user-123"})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    assert try_get_firebase_uid(creds) == "firebase-user-123"
