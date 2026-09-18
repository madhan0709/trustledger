-- Profiles
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY, -- Compatible with auth.users
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'underwriter')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Applications
CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_number TEXT UNIQUE NOT NULL,
    applicant_name TEXT NOT NULL,
    business_name TEXT,
    phone TEXT NOT NULL,
    email TEXT NOT NULL,
    loan_amount NUMERIC(15, 2) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'under_review', 'approved', 'rejected', 'flagged')) DEFAULT 'pending',
    risk_score NUMERIC(5, 2),
    risk_level TEXT CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    created_by UUID REFERENCES profiles(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_applications_app_number ON applications(application_number);
CREATE INDEX idx_applications_created_by ON applications(created_by);

-- Documents
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type TEXT NOT NULL CHECK (document_type IN ('gst', 'bank_statement', 'identity', 'other')),
    original_filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    file_hash TEXT,
    file_size BIGINT,
    mime_type TEXT,
    verification_status TEXT DEFAULT 'pending',
    uploaded_by UUID REFERENCES profiles(id),
    uploaded_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_documents_app_id ON documents(application_id);
CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by);

-- Document Analysis
CREATE TABLE IF NOT EXISTS document_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
    metadata_score NUMERIC(5, 2),
    visual_score NUMERIC(5, 2),
    ocr_score NUMERIC(5, 2),
    structure_score NUMERIC(5, 2),
    overall_risk_score NUMERIC(5, 2),
    risk_level TEXT CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    findings JSONB,
    analyzed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Video Sessions
CREATE TABLE IF NOT EXISTS video_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    video_path TEXT NOT NULL,
    liveness_score NUMERIC(5, 2),
    deepfake_score NUMERIC(5, 2),
    face_match_score NUMERIC(5, 2),
    overall_risk_score NUMERIC(5, 2),
    risk_level TEXT CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    findings JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_video_sessions_app_id ON video_sessions(application_id);

-- Identity Signals
CREATE TABLE IF NOT EXISTS identity_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    device_fingerprint TEXT,
    ip_hash TEXT,
    phone_hash TEXT,
    bank_account_fragment_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ident_sig_app_id ON identity_signals(application_id);
CREATE INDEX idx_ident_sig_device ON identity_signals(device_fingerprint);
CREATE INDEX idx_ident_sig_ip ON identity_signals(ip_hash);
CREATE INDEX idx_ident_sig_phone ON identity_signals(phone_hash);

-- Fraud Connections
CREATE TABLE IF NOT EXISTS fraud_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    connected_application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    connection_type TEXT NOT NULL CHECK (connection_type IN ('shared_device', 'shared_ip', 'shared_phone', 'shared_bank_fragment', 'other')),
    connection_strength NUMERIC(5, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT fraud_conn_no_self CHECK (application_id != connected_application_id),
    UNIQUE(application_id, connected_application_id, connection_type)
);
CREATE INDEX idx_fraud_conn_app_id ON fraud_connections(application_id);
CREATE INDEX idx_fraud_conn_conn_id ON fraud_connections(connected_application_id);

-- Risk Scores
CREATE TABLE IF NOT EXISTS risk_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL UNIQUE REFERENCES applications(id) ON DELETE CASCADE,
    document_risk NUMERIC(5, 2),
    video_risk NUMERIC(5, 2),
    graph_risk NUMERIC(5, 2),
    identity_risk NUMERIC(5, 2),
    overall_score NUMERIC(5, 2),
    risk_level TEXT CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    reasons JSONB,
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ledger Blocks
CREATE TABLE IF NOT EXISTS ledger_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    document_hash TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    block_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ledger_blocks_app_id ON ledger_blocks(application_id);
CREATE INDEX idx_ledger_blocks_prev_hash ON ledger_blocks(previous_hash);

-- Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);

-- Updated_at triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Enable RLS
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE identity_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE fraud_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
