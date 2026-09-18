-- TrustLedger RLS Policies

-- Helper function to prevent infinite recursion when checking roles against the profiles table.
-- Using SECURITY DEFINER allows this function to bypass RLS to read the role,
-- avoiding a recursive loop when profiles RLS policies are evaluated.
CREATE OR REPLACE FUNCTION public.get_auth_role()
RETURNS TEXT
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT role FROM profiles WHERE id = auth.uid();
$$;


-- 1. PROFILES
-- Admins can manage all profiles
CREATE POLICY "Admins can manage profiles" ON profiles
    FOR ALL
    TO authenticated
    USING (public.get_auth_role() = 'admin');

-- Users can read their own profile
CREATE POLICY "Users can read own profile" ON profiles
    FOR SELECT
    TO authenticated
    USING (id = auth.uid());

-- 2. APPLICATIONS
-- Admins can do everything
CREATE POLICY "Admins can manage applications" ON applications
    FOR ALL
    TO authenticated
    USING (public.get_auth_role() = 'admin');

-- Underwriters can view and update applications
CREATE POLICY "Underwriters can view applications" ON applications
    FOR SELECT
    TO authenticated
    USING (public.get_auth_role() = 'underwriter');

CREATE POLICY "Underwriters can update applications" ON applications
    FOR UPDATE
    TO authenticated
    USING (public.get_auth_role() = 'underwriter');

-- 3. DOCUMENTS
CREATE POLICY "Admins can manage documents" ON documents
    FOR ALL TO authenticated USING (public.get_auth_role() = 'admin');
CREATE POLICY "Underwriters can view documents" ON documents
    FOR SELECT TO authenticated USING (public.get_auth_role() = 'underwriter');

-- 4. DOCUMENT ANALYSIS
CREATE POLICY "Admins can manage document_analysis" ON document_analysis
    FOR ALL TO authenticated USING (public.get_auth_role() = 'admin');
CREATE POLICY "Underwriters can view document_analysis" ON document_analysis
    FOR SELECT TO authenticated USING (public.get_auth_role() = 'underwriter');

-- 5. VIDEO SESSIONS
CREATE POLICY "Admins can manage video_sessions" ON video_sessions
    FOR ALL TO authenticated USING (public.get_auth_role() = 'admin');
CREATE POLICY "Underwriters can view video_sessions" ON video_sessions
    FOR SELECT TO authenticated USING (public.get_auth_role() = 'underwriter');

-- 6. IDENTITY SIGNALS
CREATE POLICY "Admins can manage identity_signals" ON identity_signals
    FOR ALL TO authenticated USING (public.get_auth_role() = 'admin');
CREATE POLICY "Underwriters can view identity_signals" ON identity_signals
    FOR SELECT TO authenticated USING (public.get_auth_role() = 'underwriter');

-- 7. FRAUD CONNECTIONS
CREATE POLICY "Admins can manage fraud_connections" ON fraud_connections
    FOR ALL TO authenticated USING (public.get_auth_role() = 'admin');
CREATE POLICY "Underwriters can view fraud_connections" ON fraud_connections
    FOR SELECT TO authenticated USING (public.get_auth_role() = 'underwriter');

-- 8. RISK SCORES
CREATE POLICY "Admins can manage risk_scores" ON risk_scores
    FOR ALL TO authenticated USING (public.get_auth_role() = 'admin');
CREATE POLICY "Underwriters can view risk_scores" ON risk_scores
    FOR SELECT TO authenticated USING (public.get_auth_role() = 'underwriter');

-- 9. LEDGER BLOCKS
CREATE POLICY "Admins can manage ledger_blocks" ON ledger_blocks
    FOR ALL TO authenticated USING (public.get_auth_role() = 'admin');
CREATE POLICY "Underwriters can view ledger_blocks" ON ledger_blocks
    FOR SELECT TO authenticated USING (public.get_auth_role() = 'underwriter');

-- 10. AUDIT LOGS
CREATE POLICY "Admins can view and manage audit_logs" ON audit_logs
    FOR ALL TO authenticated USING (public.get_auth_role() = 'admin');

-- Underwriters can insert audit logs for their own actions but cannot read the full log
CREATE POLICY "Underwriters can insert audit_logs" ON audit_logs
    FOR INSERT TO authenticated
    WITH CHECK (public.get_auth_role() = 'underwriter' AND user_id = auth.uid());
