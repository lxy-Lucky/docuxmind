from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    # Initialise DB schema on startup
    from app.db.session import init_db
    init_db()
    get_logger().info("startup.ready", llm_provider=settings.llm_provider)
    yield


app = FastAPI(title="DocuMind", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers — imported here to keep startup cheap and avoid circular imports.
from app.api import health, folders, docs, upload, chat, sessions
from app.api import settings as settings_api

app.include_router(health.router, prefix="/api")
app.include_router(folders.router, prefix="/api")
app.include_router(docs.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
