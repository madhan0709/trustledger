# TrustLedger Database

This directory contains the database schema and seed data for the TrustLedger platform, designed for Supabase PostgreSQL.

## Tables and Relationships
- **`profiles`**: Stores application users (Underwriters, Admins). `id` aligns with Supabase Auth `auth.users`.
- **`applications`**: Central hub linking everything for a loan application. Contains applicant data.
- **`documents`**: Metadata for uploaded documents. Links via Foreign Key to `applications`.
- **`document_analysis`**: AI forensics results per document. Has a 1-to-1 relationship with `documents`.
- **`video_sessions`**: AI video-KYC metadata per application. Links via Foreign Key to `applications`.
- **`identity_signals`**: Stores non-sensitive, hashed signals (IP, device fingerprint) for networking tracking. Links to `applications`.
- **`fraud_connections`**: Graph representing edges (shared details) safely linking separate loan applications together. Self-referencing via `applications`.
- **`risk_scores`**: Unified final risk score per application. 1-to-1 relationship with `applications`.
- **`ledger_blocks`**: Immutable, tamper-evident log linking document additions together as a blockchain-lite mechanism.
- **`audit_logs`**: Crucial system for security tracking sensitive events like review approvals.

## How to Deploy
1. **Apply Schema**: Run the contents of `schema.sql` via the Supabase SQL Editor. This will create all tables, indexes, relations, and enable Row Level Security.
2. **Apply Demo Data**: Run the contents of `seed.sql` to insert non-sensitive, dummy testing data to test FastAPI integrations locally.
3. **Apply Security Policies**: Run the contents of `rls.sql` in the Supabase SQL Editor. This establishes the secure boundary controlling data access for authenticated users, admins, and underwriters.

## RLS (Row Level Security) Policies
RLS is a critical part of the TrustLedger security boundary. No application logic should bypass these rules for client interactions.

### Role-Based Access
- **Admin Access**: Admins are granted `ALL` (CRUD) operations across the entire dataset. This permits them to manage configurations, adjust profiles, view full system audit logs, and oversee the entire fraud graph globally.
- **Underwriter Access**: Underwriters represent the investigative user base. They are granted `SELECT` access across applications, documents, AI analyses, fraud signals, and ledgers in order to perform their investigations. They are also given precise `UPDATE` access to change application statuses and `INSERT` access to safely leave audit trails, without seeing the entire system's audit log.

### Security Warnings
- **Service Role Key**: NEVER expose the Supabase `service_role` key in frontend code. It deliberately bypasses RLS. Only use it in secure backend servers (e.g., FastAPI AI workers).
- **Anonymous Access**: There are strictly NO public/anonymous access policies. All interaction requires proper Supabase Authentication (`auth.uid()`).
