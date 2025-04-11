# app/routes/common.py
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import logging
import os

from app.services.csv_db import CSVDatabase
from app.services.auth import auth_service
from app.config import Config
from app.templates import templates
# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["common"])

# Initialize services
config = Config()
templates = Jinja2Templates(directory=config.get('PATHS', 'TemplatesDir'))
guests_db = CSVDatabase(
    config.get('DATABASE', 'CSVPath'),
    config.get('DATABASE', 'BackupDir')
)
# Using singleton auth_service from app.services.auth

@router.get("/check_in", response_class=HTMLResponse)
async def check_in_page(request: Request):
    """Check-in page for quick guest attendance marking"""
    try:
        # Get recent check-ins for display
        recent_checkins = []
        
        # Try to get recent check-ins from a log or database
        checkin_log_path = os.path.join(config.get('PATHS', 'LogsDir'), 'checkin.log')
        if os.path.exists(checkin_log_path):
            try:
                with open(checkin_log_path, 'r') as f:
                    # Read last 10 check-ins
                    lines = f.readlines()[-10:]
                    for line in lines:
                        parts = line.strip().split(',')
                        if len(parts) >= 4:
                            checkin = {
                                "guest_id": parts[0],
                                "name": parts[1],
                                "role": parts[2],
                                "timestamp": parts[3]
                            }
                            recent_checkins.append(checkin)
            except Exception as e:
                logger.error(f"Error reading check-in log: {str(e)}")
        
        return templates.TemplateResponse(
            "check_in.html",
            {
                "request": request,
                "recent_checkins": recent_checkins,
                "active_page": "check_in"
            }
        )
    except Exception as e:
        logger.error(f"Error rendering check-in page: {str(e)}")
        raise HTTPException(status_code=500, detail="Error loading check-in page")

@router.get("/thank_you", response_class=HTMLResponse)
async def thank_you(request: Request, name: str, phone: str):
    """Thank you page after successful registration"""
    try:
        return templates.TemplateResponse(
            "thank_you.html",
            {
                "request": request,
                "name": name,
                "phone": phone,
                "active_page": "thank_you"
            }
        )
    except Exception as e:
        logger.error(f"Error rendering thank you page: {str(e)}")
        return RedirectResponse(url="/")

@router.get("/logout")
async def logout(request: Request):
    """Log out and clear session"""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="session_id")
    return response

@router.get("/api/system-status")
async def system_status():
    """Get system health status for monitoring"""
    try:
        # Check storage status
        import psutil
        disk = psutil.disk_usage('/')
        
        # Check last backup
        from pathlib import Path
        import os
        backup_dir = Path(config.get('DATABASE', 'BackupDir'))
        last_backup = None
        
        if backup_dir.exists():
            backup_files = sorted(
                [f for f in backup_dir.glob("*.csv") if f.is_file()],
                key=lambda x: os.path.getmtime(x),
                reverse=True
            )
            if backup_files:
                last_backup = datetime.fromtimestamp(
                    os.path.getmtime(backup_files[0])
                ).isoformat()
        
        return {
            "status": "healthy" if disk.percent < 90 else "warning",
            "storage": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent
            },
            "last_backup": last_backup,
            "uptime": datetime.now().timestamp() - datetime.fromtimestamp(
                os.path.getctime(__file__)
            ).timestamp()
        }
    except Exception as e:
        logger.error(f"Error checking system status: {str(e)}")
        raise HTTPException(status_code=500, detail="Error checking system status")

@router.post("/api/search")
async def search(request: Request, q: str):
    """Search for guests by name, ID, or phone number"""
    try:
        if not q or len(q) < 3:
            return {"results": []}
            
        q = q.lower()
        guests = guests_db.read_all()
        
        results = []
        for guest in guests:
            if (q in guest.get("ID", "").lower() or 
                q in guest.get("Name", "").lower() or 
                q in guest.get("Phone", "").lower() or 
                q in guest.get("Email", "").lower()):
                
                results.append({
                    "id": guest.get("ID"),
                    "name": guest.get("Name"),
                    "phone": guest.get("Phone"),
                    "email": guest.get("Email"),
                    "role": guest.get("GuestRole")
                })
                
                # Direct match on ID - redirect directly
                if q == guest.get("ID", "").lower():
                    return {"redirect": f"/single_guest/{guest.get('ID')}"}
        
        return {"results": results[:10]}  # Limit to 10 results
    except Exception as e:
        logger.error(f"Error in search: {str(e)}")
        raise HTTPException(status_code=500, detail="Search error")

@router.get("/guest_registration", response_class=HTMLResponse)
async def guest_registration_page(request: Request):
    """Guest registration page"""
    return RedirectResponse(url="/guest/register", status_code=303)

# @router.get("/admin_dashboard", response_class=RedirectResponse)
# async def admin_dashboard_redirect():
#     """Redirect to admin dashboard"""
#     return RedirectResponse(url="/admin/dashboard")

@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page"""
    try:
        return templates.TemplateResponse(
            "admin/login.html",
            {
                "request": request,
                "active_page": "admin_login"
            }
        )
    except Exception as e:
        logger.error(f"Error rendering admin login page: {str(e)}")
        raise HTTPException(status_code=500, detail="Error loading login page")

@router.get("/program", response_class=HTMLResponse)
async def program_redirect():
    """Redirect /program to /guest/program"""
    return RedirectResponse(url="/guest/program", status_code=303)

@router.get("/speakers", response_class=HTMLResponse)
async def speakers_redirect():
    """Redirect /speakers to /guest/speakers"""
    return RedirectResponse(url="/guest/speakers", status_code=303)

@router.get("/registration", response_class=HTMLResponse)
async def registration_redirect():
    """Redirect /registration to /guest/register"""
    return RedirectResponse(url="/guest/register", status_code=303)