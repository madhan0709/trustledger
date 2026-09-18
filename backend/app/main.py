from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routers import auth, applications

app = FastAPI(title="TrustLedger API")

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(applications.router)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred", "type": str(type(exc).__name__)}
    )

@app.get("/")
def read_root():
    return {"message": "TrustLedger API is running"}

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "trustledger-api"
    }
