"""
document_forensics.py
─────────────────────
Phase 7 – Document Forensics Service

Implements four independent forensic components for PDF and image files:
  A. Metadata analysis
  B. PDF structural analysis
  C. Visual / image analysis
  D. OCR / text-layer analysis

Each component returns:
  - score   : 0 (no risk) → 100 (maximum risk)
  - signals : list of finding dicts

Overall score (weighted):
  metadata   20%
  visual     25%
  ocr        20%
  structure  35%

Risk levels (overall_risk_score):
  0–24   → low
  25–49  → medium
  50–74  → high
  75–100 → critical

NO random scores. Every score is derived from observed signals.
"""

from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ─── Weights ─────────────────────────────────────────────────────────────────
WEIGHT_METADATA  = 0.20
WEIGHT_VISUAL    = 0.25
WEIGHT_OCR       = 0.20
WEIGHT_STRUCTURE = 0.35

# ─── Thresholds ───────────────────────────────────────────────────────────────
RISK_THRESHOLDS = [
    (0,  24,  "low"),
    (25, 49,  "medium"),
    (50, 74,  "high"),
    (75, 100, "critical"),
]


def _risk_label(score: float) -> str:
    for lo, hi, label in RISK_THRESHOLDS:
        if lo <= score <= hi:
            return label
    return "critical"


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


# ─── Finding builder ──────────────────────────────────────────────────────────

def _signal(
    category: str,
    severity: str,
    title: str,
    description: str,
    evidence: dict | None = None,
) -> dict:
    return {
        "category":    category,
        "severity":    severity,
        "title":       title,
        "description": description,
        "evidence":    evidence or {},
    }


# ─── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class ComponentResult:
    score:   float
    signals: list[dict] = field(default_factory=list)

    def add(
        self,
        severity: str,
        title: str,
        description: str,
        category: str,
        evidence: dict | None = None,
    ):
        self.signals.append(_signal(category, severity, title, description, evidence))


@dataclass
class ForensicsResult:
    metadata_score:     float
    visual_score:       float
    ocr_score:          float
    structure_score:    float
    overall_risk_score: float
    risk_level:         str
    findings:           dict
    hash_verified:      bool


# ═══════════════════════════════════════════════════════════════════════════════
# A.  METADATA ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_metadata_pdf(doc) -> ComponentResult:
    """Inspect PDF metadata for forensic signals."""
    import fitz  # PyMuPDF

    result = ComponentResult(score=0.0)
    meta   = doc.metadata or {}

    producer = meta.get("producer", "") or ""
    creator  = meta.get("creator",  "") or ""
    author   = meta.get("author",   "") or ""
    creation = meta.get("creationDate", "") or ""
    mod      = meta.get("modDate",      "") or ""

    evidence = {
        "producer":     producer or None,
        "creator":      creator  or None,
        "author":       author   or None,
        "creation_date": creation or None,
        "mod_date":      mod      or None,
        "pdf_version":  doc.pdf_version() if hasattr(doc, "pdf_version") else None,
    }

    # Missing producer is mildly suspicious
    if not producer:
        result.score += 15
        result.add("medium", "Missing PDF producer",
                   "PDF producer metadata is absent. Legitimate generators typically identify themselves.",
                   "metadata", {"field": "producer"})
    else:
        result.add("info", "PDF producer present",
                   f"Producer field present: '{producer[:80]}'.",
                   "metadata", {"producer": producer[:80]})

    # Suspicious editing-tool patterns (generic, not PDF-writer specific)
    suspicious_tools = ["inkscape", "gimp", "photoshop", "canva", "illustrator"]
    for tool in suspicious_tools:
        if tool in producer.lower() or tool in creator.lower():
            result.score += 20
            result.add("medium", "Image editor used as PDF producer",
                       f"Producer/creator suggests the document may have been composited in an image editor ('{tool}'). "
                       "This is not conclusive but warrants review.",
                       "metadata", {"tool": tool})
            break

    # Modification after creation is a red flag
    if creation and mod and mod.strip() and creation.strip() and mod != creation:
        result.score += 20
        result.add("medium", "Modification date differs from creation date",
                   "The PDF was modified after creation. This may indicate post-generation editing.",
                   "metadata", {"creation_date": creation, "mod_date": mod})

    result.add("info", "PDF metadata inspection complete",
               "Metadata fields were examined for common forensic signals.",
               "metadata", evidence)

    result.score = _clamp(result.score)
    return result


def _analyze_metadata_image(img_bytes: bytes, mime_type: str) -> ComponentResult:
    """Inspect image EXIF / basic metadata."""
    from PIL import Image
    from PIL.ExifTags import TAGS

    result = ComponentResult(score=0.0)
    try:
        img  = Image.open(io.BytesIO(img_bytes))
        exif = img._getexif() if hasattr(img, "_getexif") else None

        if not exif:
            result.score += 10
            result.add("low", "No EXIF metadata",
                       "The image contains no EXIF metadata. This is common for screenshots or processed images.",
                       "metadata", {})
        else:
            readable = {TAGS.get(k, k): str(v)[:120] for k, v in exif.items() if v}
            # Check for modification inconsistency
            dt_orig = readable.get("DateTimeOriginal")
            dt_mod  = readable.get("DateTime")
            if dt_orig and dt_mod and dt_orig != dt_mod:
                result.score += 15
                result.add("medium", "EXIF datetime inconsistency",
                           "Original capture time differs from EXIF modification time.",
                           "metadata", {"DateTimeOriginal": dt_orig, "DateTime": dt_mod})
            else:
                result.add("info", "EXIF metadata present",
                           "Image EXIF metadata is available and was inspected.",
                           "metadata", {"fields_found": list(readable.keys())[:10]})
    except Exception as e:
        result.add("low", "EXIF extraction failed",
                   "Could not extract EXIF data from the image file. Treating as limitation.",
                   "metadata", {"error": str(e)[:100]})

    result.score = _clamp(result.score)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# B.  PDF STRUCTURAL ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_structure_pdf(doc, file_bytes: bytes) -> ComponentResult:
    """Inspect PDF logical structure for forensic signals."""
    result = ComponentResult(score=0.0)

    page_count = len(doc)
    if page_count == 0:
        result.score += 40
        result.add("high", "Empty PDF", "PDF has no pages.", "structure",
                   {"page_count": page_count})
        result.score = _clamp(result.score)
        return result

    result.add("info", f"PDF has {page_count} page(s)",
               "Page count noted.", "structure", {"page_count": page_count})

    total_text      = 0
    total_images    = 0
    font_families: set[str] = set()
    dim_anomaly     = False
    annotation_flag = False

    for page_num in range(page_count):
        page = doc[page_num]

        # Text
        text = page.get_text("text")
        total_text += len(text.strip())

        # Images
        img_list = page.get_images(full=True)
        total_images += len(img_list)

        # Fonts
        for font in page.get_fonts():
            name = font[3] or font[4] or ""
            if name:
                # Take the base family name (strip subset prefix like 'ABCDEF+')
                clean = name.split("+")[-1].split("-")[0].strip()
                if clean:
                    font_families.add(clean)

        # Page dimensions — flag highly unusual sizes
        rect = page.rect
        w, h = rect.width, rect.height
        if w < 10 or h < 10 or w > 5000 or h > 5000:
            dim_anomaly = True

        # Annotations (forms, comments, etc.)
        annots = page.annots()
        if annots and len(list(annots)) > 0:
            annotation_flag = True

    # Scoring
    if total_text == 0:
        result.score += 25
        result.add("medium", "No text layer in PDF",
                   "The PDF contains no extractable text. It may be a scanned image without OCR, "
                   "or the text layer was deliberately removed.",
                   "structure", {"total_chars": 0})
    else:
        result.add("info", "Text layer present",
                   f"PDF contains approximately {total_text} characters of extractable text.",
                   "structure", {"total_chars": total_text})

    if total_images > 0:
        # Images in a PDF are normal for statements/IDs; only flag excessive use
        if total_images > 20:
            result.score += 15
            result.add("medium", "High image count",
                       f"PDF contains {total_images} embedded images. "
                       "A very high image count may indicate a composited document.",
                       "structure", {"image_count": total_images})
        else:
            result.add("info", "Embedded images detected",
                       f"{total_images} image(s) found. Normal for scanned documents.",
                       "structure", {"image_count": total_images})

    if len(font_families) > 6:
        result.score += 15
        result.add("medium", "Multiple font families",
                   f"{len(font_families)} distinct font families detected. "
                   "An unusually large number may indicate content was assembled from multiple sources.",
                   "structure", {"font_count": len(font_families),
                                 "sample": list(font_families)[:8]})
    elif font_families:
        result.add("info", "Font information",
                   f"{len(font_families)} font family/families detected.",
                   "structure", {"fonts": list(font_families)[:8]})

    if dim_anomaly:
        result.score += 10
        result.add("low", "Unusual page dimensions",
                   "At least one page has non-standard dimensions.",
                   "structure", {})

    if annotation_flag:
        result.score += 10
        result.add("low", "Annotations or form fields detected",
                   "The PDF contains annotations or interactive form fields.",
                   "structure", {})

    result.score = _clamp(result.score)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# C.  VISUAL ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_visual_image(img_bytes: bytes) -> ComponentResult:
    """Run visual forensic checks on an image."""
    import cv2
    import numpy as np
    from PIL import Image

    result = ComponentResult(score=0.0)

    try:
        img_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img_arr = np.array(img_pil)
        img_cv  = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)
        gray    = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        h, w = gray.shape

        # Dimensions
        result.add("info", "Image dimensions", f"{w}×{h} pixels.", "visual",
                   {"width": w, "height": h})

        if w < 100 or h < 100:
            result.score += 25
            result.add("medium", "Very small image",
                       f"Image is only {w}×{h} px. Legitimate ID/document scans are typically larger.",
                       "visual", {"width": w, "height": h})

        # Blur — Laplacian variance; low = blurry
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if lap_var < 20:
            result.score += 20
            result.add("medium", "High blur detected",
                       f"Laplacian variance {lap_var:.1f} indicates significant blurring, "
                       "which may obscure document details.",
                       "visual", {"laplacian_variance": round(lap_var, 2)})
        else:
            result.add("info", "Blur level acceptable",
                       f"Laplacian variance {lap_var:.1f} — sharpness is within acceptable range.",
                       "visual", {"laplacian_variance": round(lap_var, 2)})

        # Brightness — mean pixel value
        mean_bright = float(gray.mean())
        if mean_bright < 30:
            result.score += 15
            result.add("medium", "Very dark image",
                       "Image is unusually dark. Content may be obscured.",
                       "visual", {"mean_brightness": round(mean_bright, 2)})
        elif mean_bright > 240:
            result.score += 10
            result.add("low", "Overexposed / near-blank image",
                       "Image is nearly white. Useful content may be absent.",
                       "visual", {"mean_brightness": round(mean_bright, 2)})
        else:
            result.add("info", "Brightness normal",
                       f"Mean brightness {mean_bright:.1f}.",
                       "visual", {"mean_brightness": round(mean_bright, 2)})

        # Contrast — standard deviation
        std_dev = float(gray.std())
        if std_dev < 10:
            result.score += 10
            result.add("low", "Very low contrast",
                       "Image contrast is extremely low; details may be invisible.",
                       "visual", {"std_dev": round(std_dev, 2)})
        else:
            result.add("info", "Contrast level acceptable",
                       f"Grey-channel std deviation {std_dev:.1f}.",
                       "visual", {"std_dev": round(std_dev, 2)})

    except Exception as e:
        result.score += 10
        result.add("low", "Visual analysis limitation",
                   f"Visual checks could not fully complete: {str(e)[:120]}",
                   "visual", {})

    result.score = _clamp(result.score)
    return result


def _analyze_visual_pdf(doc) -> ComponentResult:
    """Render the first PDF page and run image-quality checks on it."""
    result = ComponentResult(score=0.0)
    try:
        page  = doc[0]
        mat   = page.get_pixmap(matrix=page.transformation_matrix).samples
        # get_pixmap returns raw RGB bytes via .samples; wrap and analyze
        pix   = doc[0].get_pixmap()
        raw   = pix.tobytes("png")
        return _analyze_visual_image(raw)
    except Exception as e:
        result.add("low", "PDF visual rendering limitation",
                   f"Could not render PDF page for visual analysis: {str(e)[:120]}",
                   "visual", {})
    result.score = _clamp(result.score)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# D.  OCR / TEXT ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_ocr_pdf(doc) -> ComponentResult:
    """Use PyMuPDF text extraction as the OCR/text-layer component."""
    result = ComponentResult(score=0.0)
    all_text = ""
    for page in doc:
        all_text += page.get_text("text")

    char_count = len(all_text.strip())
    page_count = max(len(doc), 1)
    density    = char_count / page_count

    evidence = {"total_chars": char_count, "density_per_page": round(density, 1)}

    if char_count == 0:
        result.score += 30
        result.add("high", "No extractable text",
                   "No text could be extracted from the PDF. "
                   "The document may be a pure image scan without a text layer. "
                   "OCR not available in this pipeline.",
                   "ocr", evidence)
    elif density < 50:
        result.score += 15
        result.add("medium", "Low text density",
                   f"Only ~{char_count} characters across {page_count} page(s). "
                   "Text density is lower than expected for a legitimate document.",
                   "ocr", evidence)
    elif density > 10000:
        result.add("info", "High text density",
                   "Document is text-rich, consistent with generated statements or reports.",
                   "ocr", evidence)
    else:
        result.add("info", "Text extraction successful",
                   f"Extracted ~{char_count} characters at {density:.0f} chars/page.",
                   "ocr", evidence)

    result.score = _clamp(result.score)
    return result


def _analyze_ocr_image(img_bytes: bytes) -> ComponentResult:
    """For images, OCR is not included in this pipeline. Record as a limitation."""
    result = ComponentResult(score=0.0)
    # Treat absence of a text layer in an image as informational, not inherently risky.
    result.add("info", "OCR not available for images",
               "Images do not have an embedded text layer. "
               "OCR integration is noted as a future enhancement.",
               "ocr", {})
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_overall_score(
    metadata_score: float,
    visual_score:   float,
    ocr_score:      float,
    structure_score: float,
) -> float:
    """
    Transparent weighted aggregation.
    Weights: metadata=20%, visual=25%, ocr=20%, structure=35%
    """
    return _clamp(
        metadata_score  * WEIGHT_METADATA
        + visual_score   * WEIGHT_VISUAL
        + ocr_score      * WEIGHT_OCR
        + structure_score * WEIGHT_STRUCTURE
    )


def analyze_document(
    file_bytes:      bytes,
    mime_type:       str,
    stored_hash:     str,
) -> ForensicsResult:
    """
    Run the full four-component forensic analysis on the provided bytes.

    Parameters
    ----------
    file_bytes   : exact bytes downloaded from private Supabase Storage
    mime_type    : MIME type as stored in documents.mime_type
    stored_hash  : SHA-256 hex digest from documents.file_hash

    Returns
    -------
    ForensicsResult with all scores, risk_level, findings, and hash_verified flag
    """

    signals:     list[dict] = []
    limitations: list[str]  = []

    # ── Hash verification ──────────────────────────────────────────────────────
    computed_hash = hashlib.sha256(file_bytes).hexdigest()
    hash_verified = computed_hash == stored_hash

    if not hash_verified:
        signals.append(_signal(
            "integrity", "critical",
            "SHA-256 hash mismatch",
            "The computed hash of the downloaded file does not match the stored hash. "
            "The file may have been tampered with after upload.",
            {"stored_hash": stored_hash, "computed_hash": computed_hash},
        ))
    else:
        signals.append(_signal(
            "integrity", "info",
            "SHA-256 hash verified",
            "The downloaded file exactly matches the original upload. Integrity check passed.",
            {"hash": computed_hash[:16] + "..."},
        ))

    # ── Per-type analysis ──────────────────────────────────────────────────────
    is_pdf = mime_type == "application/pdf"

    try:
        if is_pdf:
            import fitz
            doc = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")

            meta_result = _analyze_metadata_pdf(doc)
            vis_result  = _analyze_visual_pdf(doc)
            ocr_result  = _analyze_ocr_pdf(doc)
            strct_result = _analyze_structure_pdf(doc, file_bytes)
            doc.close()
        else:
            meta_result  = _analyze_metadata_image(file_bytes, mime_type)
            vis_result   = _analyze_visual_image(file_bytes)
            ocr_result   = _analyze_ocr_image(file_bytes)
            # Structural analysis not applicable to flat images
            strct_result = ComponentResult(score=0.0, signals=[
                _signal("structure", "info",
                        "Structural analysis not applicable",
                        "PDF structure analysis is only available for PDF documents.",
                        {})
            ])

    except Exception as e:
        logger.error("Forensics analysis engine error: %s", str(e))
        # Return a partial error result rather than crashing
        limitations.append(f"Analysis engine error: {str(e)[:200]}")
        empty = ComponentResult(score=0.0)
        meta_result = vis_result = ocr_result = strct_result = empty

    # ── Hash mismatch amplifies all scores by 30 points ───────────────────────
    boost = 30.0 if not hash_verified else 0.0

    ms = _clamp(meta_result.score   + boost)
    vs = _clamp(vis_result.score    + boost)
    os = _clamp(ocr_result.score    + boost)
    ss = _clamp(strct_result.score  + boost)

    overall = calculate_overall_score(ms, vs, os, ss)
    risk    = _risk_label(overall)

    # ── Collect all signals ────────────────────────────────────────────────────
    for r in [meta_result, vis_result, ocr_result, strct_result]:
        signals.extend(r.signals)

    findings = {
        "summary":     f"Document forensics completed. Overall risk: {risk}.",
        "hash_verified": hash_verified,
        "signals":     signals,
        "limitations": limitations,
    }

    return ForensicsResult(
        metadata_score=     round(ms, 2),
        visual_score=       round(vs, 2),
        ocr_score=          round(os, 2),
        structure_score=    round(ss, 2),
        overall_risk_score= round(overall, 2),
        risk_level=         risk,
        findings=           findings,
        hash_verified=      hash_verified,
    )
