# TrustLedger Backend API Contract

All endpoints below require a valid standard Bearer token retrieved from Supabase Authentication inside the `Authorization` header.

## Applications API

The core Applications API allows authenticated internal users (Underwriters and Admins) to track and manage cybersecurity lending analyses. 

### `POST /api/applications`
Creates a brand new loan application internally tracking logic.
* **Auth Requirement**: Underwriter or Admin
* **Request Body** (JSON):
```json
{
  "applicant_name": "John Doe",
  "business_name": "Doe Tech LLC",
  "phone": "+1555010001",
  "email": "john.doe@example.com",
  "loan_amount": 500000.00
}
```
* **Response** (201 Created): Retuns full DB application object.
```json
{
  "id": "33333333-3333-3333-3333-333333333333",
  "application_number": "APP-2E4F9A",
  "applicant_name": "John Doe",
  "business_name": "Doe Tech LLC",
  "phone": "+1555010001",
  "email": "john.doe@example.com",
  "loan_amount": 500000.00,
  "status": "pending",
  "risk_score": null,
  "risk_level": null,
  "created_by": "11111111-1111-1111-1111-111111111111",
  "created_at": "2023-11-20T10:00:00Z",
  "updated_at": "2023-11-20T10:00:00Z"
}
```

### `GET /api/applications`
Retrieves a paginated list of applications matching permissions.
* **Auth Requirement**: Underwriter or Admin
* **Query Parameters**: `?page=1&page_size=20`
* **Response** (200 OK):
```json
{
  "items": [
    { /* application object */ }
  ],
  "page": 1,
  "page_size": 20,
  "total": 5
}
```

### `GET /api/applications/{application_id}`
Retrieves a single application by its precise database UUID identifier.
* **Auth Requirement**: Underwriter or Admin
* **Response** (200 OK): Returns the application JSON object mapping exactly to PostgreSQL.

### `PATCH /api/applications/{application_id}`
Updates permissible details on the target application structure safely.
* **Auth Requirement**: Underwriter or Admin
* **Request Body** (JSON): Note, we actively constrain client inputs strictly to `status` to prevent manipulation of security scoring.
```json
{
  "status": "approved"
}
```
Supported statuses identically mirroring the PostgreSQL `CHECK` constraint: `pending`, `under_review`, `approved`, `rejected`, `flagged`.
* **Response** (200 OK): Returns the newly updated application state object.

---

## Documents API

### `POST /api/applications/{application_id}/documents`

Uploads a document file for a specific loan application.

* **Auth Requirement**: Underwriter or Admin (`Authorization: Bearer <token>`)
* **Content-Type**: `multipart/form-data`

**Multipart Fields:**

| Field           | Type   | Required | Description                                         |
|----------------|--------|----------|-----------------------------------------------------|
| `file`          | file   | Yes      | The document file to upload                         |
| `document_type` | string | Yes      | One of: `gst`, `bank_statement`, `identity`, `other` |

**Supported File Formats:**

| MIME Type         | Extension |
|------------------|-----------|
| `application/pdf` | `.pdf`    |
| `image/png`       | `.png`    |
| `image/jpeg`      | `.jpg`    |

**Validation Rules:**
- Maximum file size: **10 MB** (enforced server-side on raw bytes)
- Empty files are rejected (400/422)
- MIME type is validated server-side (not just extension)
- `document_type` must match allowed values from the DB CHECK constraint
- User-supplied filenames are sanitized: path traversal characters (`../`, `/`, `\`) are stripped
- `uploaded_by` is always derived from the authenticated token — never accepted from the request body

**SHA-256 Behavior:**
- The exact uploaded bytes are hashed using SHA-256
- The resulting hex digest is stored in `documents.file_hash`
- The hash can be independently verified by downloading the original file and running `sha256sum`

**Storage Behavior:**
- Files are stored in the **private** Supabase Storage bucket: `trustledger-documents`
- Storage path format: `applications/{application_id}/{uuid}_{sanitized_filename}`
- No public URLs are generated
- The `service_role` key is used server-side only; never exposed to the frontend

**Rollback Behavior:**
- If storage upload succeeds but DB insert fails → the uploaded file is deleted from storage
- If storage upload fails → no DB insert is attempted

**Response** (201 Created):
```json
{
  "id": "uuid",
  "application_id": "uuid",
  "document_type": "bank_statement",
  "original_filename": "bank_stmt_jan.pdf",
  "storage_path": "applications/{app_id}/{uuid}_bank_stmt_jan.pdf",
  "file_hash": "sha256hexdigest",
  "file_size": 204800,
  "mime_type": "application/pdf",
  "verification_status": "pending",
  "uploaded_by": "user_uuid",
  "uploaded_at": "2026-09-18T18:00:00Z"
}
```

**Error Responses:**

| Code | Reason                              |
|------|-------------------------------------|
| 401  | Missing or invalid Bearer token     |
| 403  | Role not permitted (not underwriter/admin) |
| 404  | Application not found               |
| 413  | File exceeds 10 MB limit            |
| 422  | Invalid document_type or MIME type, empty file |
| 500  | Storage or database error           |

---

## Document Forensics API

### `POST /api/documents/{document_id}/analyze`

Triggers forensic analysis for an existing document. Downloads the original file from secure storage, verifies the SHA-256 hash, runs the 4-component AI forensic pipeline (Metadata, Structural, Visual, OCR), and saves the result to the `document_analysis` PostgreSQL table.

* **Auth Requirement**: Underwriter or Admin (`Authorization: Bearer <token>`)

**Validation Rules:**
- Authenticates the user and verifies access via backend dependencies
- Validates that `document_id` exists and is a valid UUID
- Prevents redundant multi-inserts in `document_analysis` via UPSERT

**Scoring Behavior:**
- 4 Component Scores (0 = no risk, 100 = max risk): `metadata`, `visual`, `ocr`, `structure`.
- Aggregate Score weighting (out of 100): `metadata=20%`, `visual=25%`, `ocr=20%`, `structure=35%`
- Output Risk Level mappings:
  - 0–24: `low`
  - 25–49: `medium`
  - 50–74: `high`
  - 75–100: `critical`

**Findings Structure:**
- The JSON response payload `findings` field contains a summary paragraph and a `signals` array. 
- Each signal contains `category`, `severity`, `title`, `description`, and `evidence`.

**Response** (201 Created):
```json
{
  "id": "analysis-uuid",
  "document_id": "document-uuid",
  "metadata_score": 15.00,
  "visual_score": 10.00,
  "ocr_score": 0.00,
  "structure_score": 25.00,
  "overall_risk_score": 14.25,
  "risk_level": "low",
  "findings": {
    "summary": "Document forensics completed. Overall risk: low.",
    "hash_verified": true,
    "signals": [
      {
        "category": "metadata",
        "severity": "info",
        "title": "PDF producer present",
        "description": "Producer field present.",
        "evidence": {"producer": "Example PDF Generator"}
      }
    ],
    "limitations": []
  },
  "analyzed_at": "2026-09-18T18:00:00Z"
}
```

**Error Responses:**

| Code | Reason                              |
|------|-------------------------------------|
| 401  | Missing or invalid Bearer token     |
| 403  | Role not permitted (not underwriter/admin) |
| 404  | Document not found / Application not found |
| 422  | Invalid document UUID parameter     |
| 500  | Storage download, hashing, DB Upsert, or API analysis crash |

