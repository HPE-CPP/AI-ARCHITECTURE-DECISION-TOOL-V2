import os
import json
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Lazy import of firebase_admin — allows the module to be imported
# even in test environments where firebase-admin may not be installed,
# as long as verify_firebase_token is overridden by the test fixtures.
try:
    import firebase_admin
    from firebase_admin import credentials, auth as fb_auth
    _FIREBASE_AVAILABLE = True
except ImportError:
    _FIREBASE_AVAILABLE = False
    firebase_admin = None  # type: ignore
    fb_auth = None  # type: ignore

# Initialize Firebase Admin
_firebase_app = None


def _get_firebase_app():
    global _firebase_app
    if not _FIREBASE_AVAILABLE:
        raise RuntimeError(
            "firebase-admin is not installed. "
            "Run: pip install firebase-admin==6.5.0"
        )
    if _firebase_app:
        return _firebase_app

    try:
        # Check if we have credentials in env or file
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)
            return _firebase_app

        cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if cred_json:
            cred_dict = json.loads(cred_json)
            cred = credentials.Certificate(cred_dict)
            _firebase_app = firebase_admin.initialize_app(cred)
            return _firebase_app

        # Fallback: attempt default initialization (uses GOOGLE_APPLICATION_CREDENTIALS)
        _firebase_app = firebase_admin.initialize_app()
    except Exception as e:
        print(f"Warning: Failed to initialize Firebase Admin: {e}")

    return _firebase_app


# The security scheme
security = HTTPBearer(auto_error=False)


from typing import Optional

def verify_firebase_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> Optional[str]:
    """
    Verify the Firebase JWT token and return the user's UID.
    Returns None if no token is provided.
    """
    if credentials is None:
        return None

    # For local development/testing without firebase credentials
    if os.getenv("ENVIRONMENT") == "development" and credentials.credentials == "dev-token":
        return "dev-user-id"

    if not _FIREBASE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable — firebase-admin not installed",
        )

    _get_firebase_app()

    try:
        decoded_token = fb_auth.verify_id_token(credentials.credentials)
        uid = decoded_token.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token: No UID found")
        return uid
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
