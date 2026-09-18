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
