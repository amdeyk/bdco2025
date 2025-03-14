# Example of improved admin routes (admin.py)
from fastapi import APIRouter, Request, Form, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List, Dict
import logging

from app.services.csv_db import CSVDatabase
from app.services.auth import get_current_admin
from app.services.email import EmailService

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/admin", tags=["admin"])

# Initialize services
templates = Jinja2Templates(directory="templates")
guests_db = CSVDatabase("./data/guests.csv", "./data/backups")
email_service = EmailService(
    smtp_server="smtp.example.com",
    smtp_port=587,
    username="admin@example.com",
    password="password123",
    sender="Conference <admin@example.com>"
)

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin: Dict = Depends(get_current_admin)):
    """
    Admin dashboard view showing overview statistics
    
    Displays:
    - Total registrations
    - Attendance statistics
    - Payment overview
    - Recent activity
    
    Args:
        request: FastAPI request object
        admin: Current admin user information (from dependency)
        
    Returns:
        HTMLResponse: Rendered admin dashboard template
    """
    try:
        # Get statistics for dashboard
        guests = guests_db.read_all()
        stats = calculate_dashboard_stats(guests)
        
        # Get system health status
        system_status = {
            "last_backup": get_last_backup_time(),
            "storage": check_storage_status()
        }
        
        # Render dashboard template
        return templates.TemplateResponse(
            "admin/dashboard.html", 
            {
                "request": request,
                "admin": admin,
                "stats": stats,
                "system_status": system_status,
                "active_page": "dashboard"
            }
        )
    except Exception as e:
        logger.error(f"Error in admin dashboard: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading admin dashboard",
                "error_details": str(e) if debug_mode else None
            }
        )

@router.post("/send-email")
async def send_email_to_guests(
    request: Request,
    admin: Dict = Depends(get_current_admin),
    subject: str = Form(...),
    message: str = Form(...),
    recipient_role: Optional[str] = Form(None),
    recipient_ids: Optional[str] = Form(None)
):
    """
    Send emails to guests based on role or specific IDs
    
    Args:
        request: FastAPI request object
        admin: Current admin user info 
        subject: Email subject
        message: Email message body (HTML)
        recipient_role: Optional role to filter recipients
        recipient_ids: Optional comma-separated list of guest IDs
        
    Returns:
        JSONResponse: Result of email sending operation
    """
    try:
        # Get recipients based on criteria
        guests = guests_db.read_all()
        recipients = []
        
        if recipient_ids:
            # Send to specific guests
            guest_ids = [id.strip() for id in recipient_ids.split(',')]
            recipients = [
                guest["Email"] for guest in guests 
                if guest["ID"] in guest_ids and guest["Email"]
            ]
        elif recipient_role:
            # Send to all guests with specified role
            recipients = [
                guest["Email"] for guest in guests 
                if guest["GuestRole"] == recipient_role and guest["Email"]
            ]
        else:
            # Send to all guests
            recipients = [
                guest["Email"] for guest in guests 
                if guest["Email"]
            ]
            
        if not recipients:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No valid recipients found"}
            )
            
        # Send emails
        results = email_service.send_bulk_email(recipients, subject, message)
        
        # Count successes and failures
        successes = sum(1 for _, success in results if success)
        failures = len(results) - successes
        
        return JSONResponse(content={
            "success": True,
            "message": f"Sent {successes} emails successfully. {failures} failed.",
            "details": {
                "total": len(results),
                "success": successes,
                "failed": failures
            }
        })
        
    except Exception as e:
        logger.error(f"Error sending emails: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error sending emails: {str(e)}"}
        )