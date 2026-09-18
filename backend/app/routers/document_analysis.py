"""
document_analysis.py
────────────────────
Phase 7 – Document Forensics API Router

POST /api/documents/{document_id}/analyze
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.dependencies import get_supabase_client, require_underwriter_or_admin
from app.services.document_forensics import analyze_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["document_analysis"])

STORAGE_BUCKET = "trustledger-documents"


@router.post(
    "/{document_id}/analyze",
    status_code=status.HTTP_201_CREATED,
)
def analyze_document_endpoint(
    document_id: UUID,
    current_user: dict = Depends(require_underwriter_or_admin),
    supabase: Client = Depends(get_supabase_client),
):
    """
    Trigger forensic analysis for an existing uploaded document.

    1. Authenticate user.
    2. Fetch document record from DB.
    3. Verify linked application exists.
    4. Download file bytes from private Supabase Storage.
    5. Verify SHA-256 integrity.
    6. Run four-component forensic analysis.
    7. Upsert result into document_analysis (one row per document).
    8. Return the saved analysis record.
    """

    # ── 1. Fetch document record ──────────────────────────────────────────────
    try:
        doc_resp = (
            supabase.table("documents")
            .select("*")
            .eq("id", str(document_id))
            .execute()
        )
    except Exception as e:
        logger.error("DB lookup failed for document %s: %s", document_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document record.",
        )

    if not doc_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    doc = doc_resp.data[0]

    # ── 2. Verify application exists ──────────────────────────────────────────
    try:
        app_resp = (
            supabase.table("applications")
            .select("id")
            .eq("id", doc["application_id"])
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
            detail="Parent application not found.",
        )

    # ── 3. Download from private Supabase Storage ─────────────────────────────
    storage_path = doc.get("storage_path", "")
    if not storage_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document storage path is missing.",
        )

    try:
        file_bytes: bytes = supabase.storage.from_(STORAGE_BUCKET).download(storage_path)
    except Exception as e:
        logger.error("Storage download failed for path '%s': %s", storage_path, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download document from storage.",
        )

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Downloaded file is empty.",
        )

    # ── 4. Run forensic analysis ──────────────────────────────────────────────
    mime_type    = doc.get("mime_type", "application/octet-stream")
    stored_hash  = doc.get("file_hash", "")

    try:
        result = analyze_document(
            file_bytes=file_bytes,
            mime_type=mime_type,
            stored_hash=stored_hash,
        )
    except Exception as e:
        logger.error("Forensics analysis crashed for document %s: %s", document_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document analysis failed due to an internal error.",
        )

    # ── 5. Upsert into document_analysis ─────────────────────────────────────
    # document_id has a UNIQUE constraint — use upsert to handle re-analysis.
    analysis_record = {
        "document_id":       str(document_id),
        "metadata_score":    result.metadata_score,
        "visual_score":      result.visual_score,
        "ocr_score":         result.ocr_score,
        "structure_score":   result.structure_score,
        "overall_risk_score": result.overall_risk_score,
        "risk_level":        result.risk_level,
        "findings":          result.findings,
    }

    try:
        db_resp = (
            supabase.table("document_analysis")
            .upsert(analysis_record, on_conflict="document_id")
            .execute()
        )
        if not db_resp.data:
            raise Exception("No data returned from DB upsert")
        return db_resp.data[0]
    except Exception as e:
        logger.error("DB upsert failed for document_analysis (doc_id=%s): %s",
                     document_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis completed but failed to persist to database.",
        )
