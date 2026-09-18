from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
import uuid

from app.dependencies import require_underwriter_or_admin, get_supabase_client
from supabase import Client

router = APIRouter(prefix="/api/applications", tags=["applications"])

class ApplicationCreate(BaseModel):
    applicant_name: str = Field(..., min_length=1)
    business_name: Optional[str] = None
    phone: str = Field(..., min_length=5)
    email: str 
    loan_amount: float = Field(..., gt=0)

class ApplicationUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|under_review|approved|rejected|flagged)$")

@router.post("", status_code=status.HTTP_201_CREATED)
def create_application(
    app_in: ApplicationCreate,
    current_user: dict = Depends(require_underwriter_or_admin),
    supabase: Client = Depends(get_supabase_client)
):
    app_number = f"APP-{uuid.uuid4().hex[:8].upper()}"
    data = app_in.model_dump()
    data["application_number"] = app_number
    data["created_by"] = current_user["user_id"]
    
    try:
        response = supabase.table("applications").insert(data).execute()
        if not response.data:
            raise Exception("No data returned")
        return response.data[0]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create application"
        )

@router.get("")
def list_applications(
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(require_underwriter_or_admin),
    supabase: Client = Depends(get_supabase_client)
):
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20
        
    start = (page - 1) * page_size
    end = start + page_size - 1
    
    try:
        response = supabase.table("applications").select("*", count="exact").range(start, end).execute()
        return {
            "items": response.data,
            "page": page,
            "page_size": page_size,
            "total": response.count if response.count is not None else 0
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch applications")

@router.get("/{application_id}")
def get_application(
    application_id: UUID,
    current_user: dict = Depends(require_underwriter_or_admin),
    supabase: Client = Depends(get_supabase_client)
):
    try:
        response = supabase.table("applications").select("*").eq("id", str(application_id)).execute()
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch application")

@router.patch("/{application_id}")
def update_application(
    application_id: UUID,
    app_update: ApplicationUpdate,
    current_user: dict = Depends(require_underwriter_or_admin),
    supabase: Client = Depends(get_supabase_client)
):
    try:
        response = supabase.table("applications").update({"status": app_update.status}).eq("id", str(application_id)).execute()
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found or access denied")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update application")
