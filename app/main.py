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
from app.services.qr_service import QRService
from app.services.journey_sync import create_journey_service
from fastapi import Path
from fastapi import APIRouter, Request, Form, HTTPException, Path
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import logging
from datetime import datetime
import io
from PIL import Image, ImageDraw, ImageFont
import qrcode

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

# Initialize QR service and generate QR codes for existing guests
qr_service = QRService(config.get('PATHS', 'StaticDir'))

# Generate QR codes for existing guests if they don't have them
@app.on_event("startup")
async def generate_missing_qr_codes():
    """Generate QR codes for existing guests that don't have them"""
    try:
        from app.services.csv_db import CSVDatabase

        guests_db = CSVDatabase(
            config.get('DATABASE', 'CSVPath'),
            config.get('DATABASE', 'BackupDir')
        )

        guests = guests_db.read_all()
        generated_count = 0

        for guest in guests:
            guest_id = guest.get('ID')
            if guest_id and not qr_service.qr_exists(guest_id):
                try:
                    qr_service.generate_guest_badge_qr(guest_id)
                    generated_count += 1
                except Exception as e:
                    logger.error(f"Failed to generate QR code for guest {guest_id}: {str(e)}")

        if generated_count > 0:
            logger.info(f"Generated QR codes for {generated_count} guests")
    except Exception as e:
        logger.error(f"Error generating missing QR codes: {str(e)}")

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

# Add route to serve QR codes directly
@app.get("/qr-code/{guest_id}")
async def serve_qr_code(guest_id: str):
    """Serve QR code image for a guest"""
    try:
        qr_path = qr_service.generate_guest_badge_qr(guest_id)

        if not qr_path:
            raise HTTPException(status_code=404, detail="QR code not found")

        full_path = os.path.join(config.get('PATHS', 'StaticDir'), qr_path)

        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="QR code file not found")

        from fastapi.responses import FileResponse
        return FileResponse(
            full_path,
            media_type="image/png",
            headers={"Cache-Control": "max-age=3600"}
        )
    except Exception as e:
        logger.error(f"Error serving QR code: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating QR code")


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

# Add this to app/main.py after the startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application state on startup"""
    app.state.start_time = time.time()
    logger.info("Application started")
    
    # Create initial changelog entry for the enhanced reporting system
    try:
        from app.utils.changelog import ChangelogManager
        changelog_manager = ChangelogManager()
        
        # Check if there are existing entries
        entries = changelog_manager.get_entries()
        if not entries:
            changelog_manager.add_entry(
                "Enhanced Reporting System",
                "Implemented comprehensive reporting system with detailed reports for guests, faculty, presentations, travel arrangements, and system changelog.",
                "System Administrator",
                [
                    "Added guest report with filtering",
                    "Added faculty-specific report",
                    "Added presentations report",
                    "Added travel/journey report",
                    "Implemented system changelog",
                    "Enhanced data visualization with charts",
                    "Improved export functionality"
                ]
            )
    except Exception as e:
        logger.error(f"Error creating initial changelog entry: {str(e)}")

@app.on_event("startup")
async def initialize_journey_sync():
    """Initialize journey synchronization service and sync existing data"""
    try:
        journey_service = create_journey_service(config)
        stats = journey_service.sync_all_data()
        logger.info(f"Journey sync initialized: {stats}")
    except Exception as e:
        logger.error(f"Error initializing journey sync: {str(e)}")

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



