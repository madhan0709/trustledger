from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from app.config import settings
import os

security = HTTPBearer()

def get_supabase_client() -> Client:
    """
    Returns a configured Supabase client using the service role key.
    Used for backend database interactions safely bypassing RLS if needed.
    """
    url = settings.supabase_url
    key = settings.supabase_service_role_key
    
    if not url or not key:
        # Fallback to os.environ if Config fails to load during some tests
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        raise ValueError("Supabase URL and Service Role Key must be set in the environment variables.")
        
    return create_client(url, key)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    supabase: Client = Depends(get_supabase_client)
) -> dict:
    """
    Dependency to securely verify the Supabase JWT and retrieve user profile.
    """
    token = credentials.credentials
    try:
        # Securely verify token natively with Supabase GoTrue server
        user_response = supabase.auth.get_user(token)
        user = user_response.user
        if not user:
            raise Exception("User not found in token")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Securely retrieve the user's role from the database schema
    try:
        profile_response = supabase.table("profiles").select("*").eq("id", user.id).execute()
        if not profile_response.data or len(profile_response.data) == 0:
            raise Exception("Profile missing")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User profile not found or access denied."
        )
        
    profile = profile_response.data[0]
    
    # Return predictable authenticated-user object per requirements
    return {
        "user_id": profile["id"],
        "email": profile["email"],
        "full_name": profile["full_name"],
        "role": profile["role"] # We fetch it exclusively from DB natively
    }

def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Dependency that enforces exclusively admin-level access.
    """
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required."
        )
    return current_user

def require_underwriter_or_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Dependency that enforces underwriter or admin-level access.
    """
    if current_user["role"] not in ["admin", "underwriter"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Underwriter or Admin access required."
        )
    return current_user
