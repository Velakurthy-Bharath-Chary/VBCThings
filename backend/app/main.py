from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import Base, engine
from app import models  # noqa: F401 - register all ORM tables before create_all.
from app.config import settings
from app.core.rate_limit import in_memory_rate_limit
from app.core.observability import RequestObservabilityMiddleware
from app.api.notebooks import router as notebooks_router
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.rag import router as rag_router
from app.api.orchestrator import router as orchestrator_router
from app.api.image import router as image_router
from app.api.chats import router as chats_router
from app.api.speech import router as speech_router
from app.api.studio import router as studio_router
from app.api.resources import router as resources_router
from app.api.quiz_attempts import router as quiz_attempts_router
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Create missing SQLAlchemy tables when the API starts locally."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="VBC Things", version="0.1.0", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(notebooks_router)
app.include_router(documents_router)
app.include_router(rag_router)
app.include_router(orchestrator_router)
app.include_router(image_router)
app.include_router(chats_router)
app.include_router(speech_router)
app.include_router(studio_router)
app.include_router(resources_router)
app.include_router(quiz_attempts_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        *settings.allowed_origins,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestObservabilityMiddleware)
app.middleware("http")(in_memory_rate_limit)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "VBC Things",
    }


@app.get("/health/db")
def database_health():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))

    return {
        "status": "healthy",
        "database": result.scalar(),
    }


@app.get("/health/ready")
def readiness_check():
    """Report whether the database is accepting requests."""
    checks = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unavailable"

    ready = all(value == "healthy" for value in checks.values())
    return_status = "ready" if ready else "not_ready"
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": return_status, "checks": checks},
    )


# FILE PURPOSE:
# Defines the FastAPI application, API routers, configurable CORS,
# application/database health checks, and request observability.
