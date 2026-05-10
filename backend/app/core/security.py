import os
import json
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import credentials, auth

# Initialize Firebase Admin
_firebase_app = None

def _get_firebase_app():
    global _firebase_app
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
            
        # Fallback for local development if not provided, but will fail if verify is called
        _firebase_app = firebase_admin.initialize_app()
    except Exception as e:
        print(f"Warning: Failed to initialize Firebase Admin: {e}")
        
    return _firebase_app

# The security scheme
security = HTTPBearer()

def verify_firebase_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Verify the Firebase JWT token and return the user's UID.
    """
    # For local development/testing without firebase credentials, we can bypass
    # if a special dev token is provided.
    if os.getenv("ENVIRONMENT") == "development" and credentials.credentials == "dev-token":
        return "dev-user-id"

    _get_firebase_app()
    
    try:
        decoded_token = auth.verify_id_token(credentials.credentials)
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
