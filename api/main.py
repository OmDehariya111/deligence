from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from api.database import engine, Base
from api.routes import router as main_router
from api.auth_routes import router as auth_router
from api.admin_routes import router as admin_router
from api.payments_routes import router as payments_router
from api.cache_config import init_cache

# Create all tables (if they don't exist)
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_cache()
    yield
    # Shutdown

app = FastAPI(
    title="DeligenX Platform API",
    description="Backend API for the DeligenX Due Diligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Apply GZip Middleware for payload compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

import os

# CORS middleware for frontend access
# In production with Vercel rewrites, requests appear same-origin so CORS isn't
# strictly needed. But we configure it for direct API access, webhooks, and dev.
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
allowed_origins = [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(main_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(payments_router)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "DeligenX API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
