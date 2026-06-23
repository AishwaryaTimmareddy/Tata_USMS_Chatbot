from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .azure_clients import get_azure_clients
from .config import get_settings
from .routers import admin, auth, chat

settings = get_settings()

if settings.applicationinsights_connection_string:
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(
        connection_string=settings.applicationinsights_connection_string,
        instrumentation_options={"fastapi": {"enabled": False}},
        sampling_ratio=1.0,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    clients = get_azure_clients()
    try:
        await clients.warm_credentials()
        yield
    finally:
        await clients.close()
        get_azure_clients.cache_clear()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Azure-only RAG chatbot API for USMS Saffron.",
    lifespan=lifespan,
    openapi_url=None if settings.app_env == "production" else "/openapi.json",
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
)
if settings.applicationinsights_connection_string:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, excluded_urls="/api/health")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(auth.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    checks = settings.readiness()
    services = {
        name: {"configured": not missing, "missing": missing}
        for name, missing in checks.items()
    }
    return {"ready": all(item["configured"] for item in services.values()), "services": services}


static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
