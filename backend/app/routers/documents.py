import hashlib
import logging
import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from supabase import Client

from app.dependencies import get_supabase_client, require_underwriter_or_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/applications",
    tags=["documents"],
)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_MIME_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

ALLOWED_DOCUMENT_TYPES = {"gst", "bank_statement", "identity", "other"}

STORAGE_BUCKET = "trustledger-documents"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sanitize_filename(name: str) -> str:
    """
    Strip path components and dangerous characters from a user-supplied filename.
    Keeps only alphanumerics, dots, hyphens, and underscores.
    """
    # Take only the basename — blocks ../ traversal
    name = name.replace("\\", "/").split("/")[-1]
    # Remove anything that isn't safe
    name = re.sub(r"[^\w.\-]", "_", name)
    # Collapse consecutive dots to prevent extension tricks like 'file..php'
    name = re.sub(r"\.{2,}", ".", name)
    return name or "upload"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/{application_id}/documents",
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    application_id: uuid.UUID,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_underwriter_or_admin),
    supabase: Client = Depends(get_supabase_client),
):
    """
    Upload a document for a loan application.

    - Auth:         Bearer token (underwriter or admin)
    - Multipart:    file + document_type
    - Max size:     10 MB
    - Allowed:      PDF, PNG, JPEG
    - Document types: gst, bank_statement, identity, other
    """

    # ── 1. Validate document_type ────────────────────────────────────────────
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid document_type. Allowed: {sorted(ALLOWED_DOCUMENT_TYPES)}",
        )

    # ── 2. Validate MIME type (server-side, not just extension) ─────────────
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{content_type}'. Allowed: PDF, PNG, JPEG.",
        )

    # ── 3. Read file bytes & validate size ───────────────────────────────────
    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.",
        )

    # ── 4. Verify application exists ─────────────────────────────────────────
    try:
        app_resp = (
            supabase.table("applications")
            .select("id")
            .eq("id", str(application_id))
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify application.",
        )

    if not app_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    # ── 5. Build safe storage path ───────────────────────────────────────────
    safe_name = _sanitize_filename(file.filename or "upload")
    file_uuid = uuid.uuid4()
    storage_path = f"applications/{application_id}/{file_uuid}_{safe_name}"

    # ── 6. Compute SHA-256 of the exact uploaded bytes ───────────────────────
    file_hash = _sha256(file_bytes)

    # ── 7. Upload to Supabase Storage ────────────────────────────────────────
    storage_uploaded = False
    try:
        supabase.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type},
        )
        storage_uploaded = True
    except Exception as upload_err:
        logger.error("Storage upload failed: %s", str(upload_err))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage.",
        )

    # ── 8. Insert database record ─────────────────────────────────────────────
    doc_record = {
        "application_id": str(application_id),
        "document_type": document_type,
        "original_filename": safe_name,
        "storage_path": storage_path,
        "file_hash": file_hash,
        "file_size": len(file_bytes),
        "mime_type": content_type,
        "verification_status": "pending",
        "uploaded_by": current_user["user_id"],
    }

    try:
        db_resp = supabase.table("documents").insert(doc_record).execute()
        if not db_resp.data:
            raise Exception("No data returned from DB insert")
        return db_resp.data[0]
    except Exception as db_err:
        # ── 9. Rollback: attempt storage cleanup ─────────────────────────────
        if storage_uploaded:
            try:
                supabase.storage.from_(STORAGE_BUCKET).remove([storage_path])
                logger.warning(
                    "DB insert failed after storage upload. Orphaned file cleaned up: %s",
                    storage_path,
                )
            except Exception as cleanup_err:
                logger.error(
                    "CRITICAL: DB insert failed AND storage cleanup failed for path '%s': %s",
                    storage_path,
                    str(cleanup_err),
                )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document stored but database record failed. Upload rolled back.",
        )
