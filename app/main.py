# app/main.py
import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import time

from app.config import Config
from app.routes import admin, guest, common
from app.services.csv_db import CSVDatabase
# Replace the current templates initialization in main.py
from app.templates import templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

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
    os.path.join(config.get('PATHS', 'StaticDir'), "qr_codes")
]

for directory in required_directories:
    os.makedirs(directory, exist_ok=True)

# Update templates directory
from app.templates import update_template_directory
update_template_directory(config.get('PATHS', 'TemplatesDir'))

# Create FastAPI application
app = FastAPI(
    title="Conference Guest Management System",
    description="A comprehensive system for managing conference guests",
    version=config.get('DEFAULT', 'SoftwareVersion')
)

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

# Include routers
# Include routers
app.include_router(common.router)
app.include_router(guest.router)
app.include_router(admin.router)
# if os.path.exists(os.path.join(app.config.get('PATHS', 'TemplatesDir'), "faculty")):
#     from app.routes import faculty
#     app.include_router(faculty.router)

# Create required directories
os.makedirs(config.get('PATHS', 'LogsDir'), exist_ok=True)
os.makedirs(os.path.dirname(config.get('DATABASE', 'CSVPath')), exist_ok=True)
os.makedirs(config.get('DATABASE', 'BackupDir'), exist_ok=True)

# Root route
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Landing page for the application"""
    try:
        from datetime import datetime
        logger.info("Accessing landing page")
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "now": datetime.now()}
        )
    except Exception as e:
        logger.error(f"Error rendering landing page: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading page"
            }
        )

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
            "now": datetime.now()
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
            "now": datetime.now()
        },
        status_code=500
    )

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize application state on startup"""
    app.state.start_time = time.time()
    logger.info("Application started")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    # Create shutdown backup
    db = CSVDatabase(
        config.get('DATABASE', 'CSVPath'),
        config.get('DATABASE', 'BackupDir')
    )
    db.create_backup("shutdown_backup.csv")
    logger.info("Application shutdown complete")
    
@app.get("/admin_dashboard")
async def admin_dashboard_redirect(request: Request):
    """Redirect /admin_dashboard to /admin/dashboard or login page if not authenticated"""
    session_id = request.cookies.get("session_id")
    
    if session_id:
        # Check if the session is valid and has admin role
        from app.services.auth import auth_service
        session = auth_service.validate_session(session_id)
        if session and session["role"] == "admin":
            return RedirectResponse(url="/admin/dashboard")
    
    # Redirect to login page if not authenticated
    return RedirectResponse(url="/admin/login")