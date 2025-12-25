import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from master.core.config import get_settings
from master.api.v1.endpoints import auth, nodes, stats
from fastapi import APIRouter

# Configure logging to show our debug messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

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

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "WordPress Backup Master API", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
