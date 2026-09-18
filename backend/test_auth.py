import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_authentication():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    email = os.environ.get("TEST_EMAIL")
    password = os.environ.get("TEST_PASSWORD")

    if not all([url, key, email, password]):
        print("Error: Missing required environment variables.")
        print(f"SUPABASE_URL found: {bool(url)}")
        print(f"SUPABASE_ANON_KEY found: {bool(key)}")
        print(f"TEST_EMAIL found: {bool(email)}")
        print(f"TEST_PASSWORD found: {bool(password)}")
        return

    try:
        print(f"Attempting to sign in test user: {email}...")
        # Initialize Supabase client using explicitly the anon/publishable key
        # to properly impersonate standard frontend auth procedures.
        supabase: Client = create_client(url, key)
        
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        session = response.session
        if session:
            print("\n----- SUCCESS -----")
            print("Authentication succeeded!")
            print(f"User ID: {session.user.id}")
            print(f"\nAccess Token:\n{session.access_token}\n")
            print("-------------------")
        else:
            print("\nAuthentication failed: No session returned.")
            
    except Exception as e:
        print(f"\nAuthentication failed with error: {str(e)}")

if __name__ == "__main__":
    test_authentication()
