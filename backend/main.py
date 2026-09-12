from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.api.routes.investigations import router as investigations_router
from backend.api.routes.tts import router as tts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup initialization
    print(f"🚀 [Forensic Auditor API] Initialized successfully in {settings.ENVIRONMENT} mode.")
    yield
    # Teardown / Cleanup
    print("🛑 [Forensic Auditor API] Shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="High-performance Forensic AML Engine with deterministic graph pruning, SSE thoughts streaming, and ElevenLabs TTS proxy.",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router Registration
app.include_router(investigations_router, prefix=settings.API_V1_STR)
app.include_router(tts_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint for container orchestrators and monitoring."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
