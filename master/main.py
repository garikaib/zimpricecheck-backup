import logging
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from master.core.config import get_settings
from master.core.logging_config import setup_logging, get_logger
from master.api.v1.endpoints import auth, nodes, stats, users, sites, activity_logs, settings as settings_router, storage, communications, backups, logs, metrics
from fastapi import APIRouter

# Initialize Sentry for error tracking
sentry_sdk.init(
    dsn="https://0e517d0fa9f105e17db8cb1831006665@o4510604827230208.ingest.de.sentry.io/4510604843286608",
    # Add data like request headers and IP for users
    send_default_pii=True,
    # Set traces_sample_rate to capture performance data
    traces_sample_rate=0.1,  # 10% of requests for performance monitoring
    # Set profiles_sample_rate to profile requests
    profiles_sample_rate=0.1,
    # Environment tag
    environment="production",
)

# Configure logging with file handlers and JSON output
setup_logging()
logger = get_logger(__name__)
logger.info("Sentry error tracking initialized")

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Debug middleware to log headers for /nodes/ requests
class HeaderLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if "/nodes" in request.url.path:
            print(f"[HEADERS] {request.method} {request.url.path}")
            print(f"[HEADERS] Origin: {request.headers.get('origin', 'NO ORIGIN')}")
            print(f"[HEADERS] Authorization: {request.headers.get('authorization', 'NO AUTH HEADER')[:80] if request.headers.get('authorization') else 'NO AUTH HEADER'}")
            print(f"[HEADERS] All headers: {dict(request.headers)}")
        response = await call_next(request)
        return response

app.add_middleware(HeaderLoggingMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://zimpricecheck.com",
        "https://wp.zimpricecheck.com"
    ],
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(nodes.router, prefix="/nodes", tags=["nodes"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(sites.router, prefix="/sites", tags=["sites"])
api_router.include_router(activity_logs.router, prefix="/activity-logs", tags=["activity-logs"])
api_router.include_router(settings_router.router, prefix="/settings", tags=["settings"])
api_router.include_router(storage.router, prefix="/storage", tags=["storage"])
api_router.include_router(communications.router, prefix="/communications", tags=["communications"])
api_router.include_router(backups.router, prefix="", tags=["backups"])  # Routes already have /sites and /backups prefixes
api_router.include_router(logs.router, prefix="/logs", tags=["logs"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])

# Import jobs router (requires daemon module)
try:
    from master.api.v1.endpoints import jobs
    api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
except ImportError:
    pass  # Daemon module not available

# Import daemon router for scan/backup control
try:
    from daemon.api import router as daemon_router
    api_router.include_router(daemon_router)
except ImportError:
    pass  # Daemon module not available

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "WordPress Backup Master API", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
