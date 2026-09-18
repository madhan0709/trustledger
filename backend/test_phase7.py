"""
test_phase7.py
Phase 7 Validation Tests for Document Forensics API
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "http://127.0.0.1:8000"
DOC_ID = os.environ.get("TEST_DOCUMENT_ID", "b7a09a06-2be0-4036-bf51-62c75c148230")
ANALYZE_URL = f"{BASE}/api/documents/{DOC_ID}/analyze"

TOKEN = os.environ.get("TEST_TOKEN", "")
if not TOKEN and os.environ.get("TEST_EMAIL") and os.environ.get("TEST_PASSWORD"):
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    if url and key:
        print("Authenticating automatically via Supabase...")
        client = create_client(url, key)
        res = client.auth.sign_in_with_password({
            "email": os.environ.get("TEST_EMAIL"),
            "password": os.environ.get("TEST_PASSWORD")
        })
        if res.session:
            TOKEN = res.session.access_token
            print("Authentication successful! Acquired JWT token.\n")

AUTH_HEADER = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

passed = 0
failed = 0

def check(name: str, got: int, expected: int):
    global passed, failed
    if got == expected:
        print(f"  PASS [{name}] → {got}")
        passed += 1
    else:
        print(f"  FAIL [{name}] → got {got}, expected {expected}")
        failed += 1

print("\n=== TEST 1: No auth ===")
r = requests.post(ANALYZE_URL)
check("no-auth", r.status_code, 401)

print("\n=== TEST 2: Invalid token ===")
r = requests.post(ANALYZE_URL, headers={"Authorization": "Bearer invalid-token-xyz"})
check("invalid-token", r.status_code, 401)

if TOKEN:
    print("\n=== TEST 3: Invalid document UUID ===")
    r = requests.post(f"{BASE}/api/documents/invalid-uuid-format/analyze", headers=AUTH_HEADER)
    check("invalid-uuid", r.status_code, 422)

    print("\n=== TEST 4: Nonexistent document ===")
    r = requests.post(f"{BASE}/api/documents/aaaabbbb-cccc-dddd-eeee-ffffffff0000/analyze", headers=AUTH_HEADER)
    check("not-found", r.status_code, 404)

    print("\n=== TEST 5-10: Analyze valid document ===")
    print("Sending POST to", ANALYZE_URL)
    r = requests.post(ANALYZE_URL, headers=AUTH_HEADER)
    print("Response status:", r.status_code)
    try:
        body = r.json()
        print(body)
    except:
        print(r.text)

else:
    print("\n[SKIPPED] Tests 3-10 require TEST_TOKEN environment variable.")
    print("Run: $env:TEST_TOKEN='your_bearer_token'; python test_phase7.py")

print(f"\n{'='*40}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*40}\n")

# Do not sys.exit(1) if unauth tests pass as expected.
if failed > 0:
    sys.exit(1)
