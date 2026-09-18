-- Seed Data for TrustLedger Schema
-- Note: This data uses fixed UUIDs for relationship consistency and strictly demo usage.

INSERT INTO profiles (id, full_name, email, role)
VALUES 
    ('11111111-1111-1111-1111-111111111111', 'Admin User', 'admin@trustledger.demo', 'admin'),
    ('22222222-2222-2222-2222-222222222222', 'Demo Underwriter', 'underwriter@trustledger.demo', 'underwriter')
ON CONFLICT (id) DO NOTHING;

INSERT INTO applications (id, application_number, applicant_name, business_name, phone, email, loan_amount, status, risk_score, risk_level, created_by)
VALUES 
    ('33333333-3333-3333-3333-333333333333', 'APP-2023-001', 'John Doe', 'Doe Tech LLC', '+1555010001', 'john.doe@example.com', 50000.00, 'under_review', 15.5, 'low', '22222222-2222-2222-2222-222222222222'),
    ('44444444-4444-4444-4444-444444444444', 'APP-2023-002', 'Jane Smith', 'Smith Consulting', '+1555010002', 'jane.smith@example.com', 120000.00, 'flagged', 85.0, 'high', '22222222-2222-2222-2222-222222222222')
ON CONFLICT (id) DO NOTHING;

INSERT INTO documents (id, application_id, document_type, original_filename, storage_path, file_hash, file_size, mime_type, verification_status, uploaded_by)
VALUES
    ('55555555-5555-5555-5555-555555555555', '33333333-3333-3333-3333-333333333333', 'bank_statement', 'bank_stmt_jan.pdf', 'docs/33333333-3333-3333-3333-333333333333/bank_stmt.pdf', 'hash123', 1024500, 'application/pdf', 'verified', '22222222-2222-2222-2222-222222222222'),
    ('66666666-6666-6666-6666-666666666666', '44444444-4444-4444-4444-444444444444', 'identity', 'passport_scan.jpg', 'docs/44444444-4444-4444-4444-444444444444/passport.jpg', 'hash456', 2048000, 'image/jpeg', 'pending', '22222222-2222-2222-2222-222222222222')
ON CONFLICT (id) DO NOTHING;

INSERT INTO document_analysis (id, document_id, metadata_score, visual_score, ocr_score, structure_score, overall_risk_score, risk_level, findings)
VALUES
    ('77777777-7777-7777-7777-777777777777', '55555555-5555-5555-5555-555555555555', 10, 5, 2, 5, 5.5, 'low', '{"details": "Document authentic, fonts align."}'::jsonb),
    ('88888888-8888-8888-8888-888888888888', '66666666-6666-6666-6666-666666666666', 80, 95, 70, 60, 85.0, 'critical', '{"details": "Image manipulation detected."}'::jsonb)
ON CONFLICT (id) DO NOTHING;

INSERT INTO identity_signals (id, application_id, device_fingerprint, ip_hash, phone_hash, bank_account_fragment_hash)
VALUES
    ('99999999-9999-9999-9999-999999999999', '33333333-3333-3333-3333-333333333333', 'deviceA1', 'ipHashA1', 'phoneHashA1', 'bankHashA1'),
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '44444444-4444-4444-4444-444444444444', 'deviceA1', 'ipHashB2', 'phoneHashB2', 'bankHashB2')
ON CONFLICT (id) DO NOTHING;

INSERT INTO fraud_connections (id, application_id, connected_application_id, connection_type, connection_strength)
VALUES
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '33333333-3333-3333-3333-333333333333', '44444444-4444-4444-4444-444444444444', 'shared_device', 80.0)
ON CONFLICT (id) DO NOTHING;
