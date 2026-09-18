# TrustLedger Backend

## Overview
This is the backend for the TrustLedger platform, utilizing FastAPI for high-performance Python deployment and interaction directly with Supabase via Service-Role securely avoiding frontend compromises.

## Structure
- `/app/main.py`: FastAPI application setup, global error handling, and basic health endpoints.
- `/app/config.py`: Configuration model using `pydantic-settings` to robustly parse `.env` files.
- `/app/dependencies.py`: Dependency injection functionality, instantiating the Supabase client safely with the `service_role` key.
- `/app/routers/`: Future modular route definitions.
- `/app/services/`: Core logic decoupled from routing.

## Local Development
1. **Virtual Environment**: 
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
2. **Install Dependencies**: `pip install -r requirements.txt`
3. **Configuration**: Copy `.env.example` to `.env` and fill the variables. NEVER copy actual `.env` credentials or the `service_role` key into your frontend project.
4. **Run Server**: 
   ```bash
   python -m uvicorn app.main:app --reload
   ```

*The API will start locally and serve paths like `GET /health`.*
