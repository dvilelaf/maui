from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from src.utils.config import Config
from src.database.core import db, init_db
from src.database.models import create_tables
from src.webapp.routers import tasks, lists, invites

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Database...")
    init_db(Config.DATABASE_URL.replace("sqlite:///", ""))
    db.connect()
    create_tables()

    # Coordinator init (optional if lazy loaded, but good to check)
    # coordinator already init in state.py

    yield
    # Shutdown
    logger.info("Closing Database...")
    if not db.is_closed():
        db.close()


app = FastAPI(title="Maui Web App", lifespan=lifespan)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(tasks.router)
app.include_router(lists.router)
app.include_router(invites.router)

# Serve Frontend - Must be last
app.mount("/", StaticFiles(directory="src/webapp/static", html=True), name="static")
