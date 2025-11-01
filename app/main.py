# app/main.py
import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import time
import csv

from app.config import Config
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import logging
from datetime import datetime
from app.services.settings import settings_service

# Load configuration
config = Config()

# Configure logging
logging.basicConfig(
    level=logging.INFO if not config.getboolean('DEFAULT', 'Debug') else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(config.get('PATHS', 'LogsDir'), 'application.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# At the beginning of app/main.py after loading config
# Ensure all required directories exist
required_directories = [
    config.get('PATHS', 'LogsDir'),
    config.get('PATHS', 'StaticDir'),
    config.get('PATHS', 'TemplatesDir'),
    os.path.dirname(config.get('DATABASE', 'CSVPath')),
    config.get('DATABASE', 'BackupDir'),
    os.path.join(config.get('PATHS', 'StaticDir'), "css"),
    os.path.join(config.get('PATHS', 'StaticDir'), "js"),
    os.path.join(config.get('PATHS', 'StaticDir'), "images"),
    os.path.join(config.get('PATHS', 'StaticDir'), "uploads"),
    os.path.join(config.get('PATHS', 'StaticDir'), "uploads/presentations"),
    os.path.join(config.get('PATHS', 'StaticDir'), "uploads/profile_photos"),
    os.path.join(config.get('PATHS', 'StaticDir'), "qr_codes"),
    os.path.join(config.get('PATHS', 'StaticDir'), "schedule")
]

for directory in required_directories:
    os.makedirs(directory, exist_ok=True)

# No dynamic template directory switching in simplified app

# Create FastAPI application
app = FastAPI(
    title="Conference Guest Management System",
    description="A comprehensive system for managing conference guests",
    version=config.get('DEFAULT', 'SoftwareVersion')
)

# Minimal app: QR/journey and other advanced features removed

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount(
    "/static",
    StaticFiles(directory=config.get('PATHS', 'StaticDir')),
    name="static"
)

# Initialize templates
from datetime import datetime

# Initialize templates with global variables
templates = Jinja2Templates(directory=config.get('PATHS', 'TemplatesDir'))
templates.env.globals["now"] = datetime.now()

# Jinja text normalization filter (fix common dash mojibake)
import re

def _normalize_dashes(value: str) -> str:
    if not isinstance(value, str):
        return value
    s = value
    # Fix common UTF-8 -> cp1252 mojibake for dashes
    s = s.replace("â€“", "–").replace("â€”", "—")
    # If a stray 'â' accidentally split a range like 12â14, correct to en dash
    s = re.sub(r"(?<=\d)â(?=\d)", "–", s)
    # Normalize all long dashes to an en dash
    s = s.replace("—", "–")
    # Collapse spaces around dashes used as ranges
    s = re.sub(r"\s*–\s*", "–", s)
    return s

templates.env.filters["normalize_dashes"] = _normalize_dashes

# Include only the simplified routes
from app.routes import simple
app.include_router(simple.router)
# if os.path.exists(os.path.join(app.config.get('PATHS', 'TemplatesDir'), "faculty")):
#     from app.routes import faculty
#     app.include_router(faculty.router)

# Create required directories
os.makedirs(config.get('PATHS', 'LogsDir'), exist_ok=True)
os.makedirs(os.path.dirname(config.get('DATABASE', 'CSVPath')), exist_ok=True)
os.makedirs(config.get('DATABASE', 'BackupDir'), exist_ok=True)

# Root route
@app.get("/")
async def root(request: Request):
    return RedirectResponse(url="/login")

# QR route removed in simplified app


# Error handling
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    from datetime import datetime
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "message": exc.detail,
            "status_code": exc.status_code,
            "now": datetime.now(),
            "conference": settings_service.get(),
        },
        status_code=exc.status_code
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    from datetime import datetime
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "message": "An unexpected error occurred",
            "status_code": 500,
            "error_details": str(exc) if config.getboolean('DEFAULT', 'Debug') else None,
            "now": datetime.now(),
            "conference": settings_service.get(),
        },
        status_code=500
    )

@app.on_event("startup")
async def startup_event():
    app.state.start_time = time.time()
    logger.info("Simplified app started")

@app.get("/admin_dashboard")
async def admin_dashboard_redirect(request: Request):
    # For backward compatibility; redirect to simplified admin
    return RedirectResponse(url="/admin")



