from fastapi import APIRouter, Depends
from app.dependencies import get_current_user, require_underwriter_or_admin

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """
    Returns the authenticated user's profile information based securely on DB records.
    Requires a valid Supabase JWT Bearer token.
    """
    return current_user

@router.get("/protected-test")
def protected_test(current_user: dict = Depends(require_underwriter_or_admin)):
    """
    Test endpoint only accessible to underwriters and admins.
    """
    return {
        "authenticated": True,
        "message": "Authentication successful",
        "role": current_user["role"]
    }
