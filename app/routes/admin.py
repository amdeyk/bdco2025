# app/routes/admin.py
from fastapi import APIRouter, Request, Form, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from typing import Optional, List, Dict
import logging
import os
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import psutil

from app.services.csv_db import CSVDatabase
from app.services.auth import auth_service, get_current_admin
from app.services.email import EmailService
from app.config import Config
from app.templates import templates
from app.utils.logging_utils import log_activity

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/admin", tags=["admin"])

# Initialize services
config = Config()
guests_db = CSVDatabase(
    config.get('DATABASE', 'CSVPath'),
    config.get('DATABASE', 'BackupDir')
)
# Use singleton auth_service from app.services.auth
email_service = EmailService(
    smtp_server=config.get('EMAIL', 'SMTPServer'),
    smtp_port=config.getint('EMAIL', 'SMTPPort'),
    username=config.get('EMAIL', 'Username'),
    password=config.get('EMAIL', 'Password'),
    sender=f"{config.get('EMAIL', 'SenderName')} <{config.get('EMAIL', 'SenderEmail')}>"
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
        # Get actual guest data
        guests = guests_db.read_all()
        
        # Calculate real statistics from guest data
        checked_in_count = sum(1 for g in guests if g.get("DailyAttendance") == "True")
        faculty_count = sum(1 for g in guests if g.get("GuestRole") == "Faculty")
        
        # Calculate completion rate (percentage of fully registered guests)
        completed_guests = sum(1 for g in guests if g.get("Email") and g.get("Phone"))
        completion_rate = (completed_guests / len(guests) * 100) if guests else 0
        
        # Group registrations by date
        registration_dates = defaultdict(int)
        for guest in guests:
            try:
                if guest.get("RegistrationDate"):
                    date = datetime.fromisoformat(guest.get("RegistrationDate")).strftime('%Y-%m-%d')
                    registration_dates[date] += 1
            except (ValueError, TypeError):
                continue
        
        # Sort dates and prepare data for chart
        sorted_dates = sorted(registration_dates.keys())
        trend_labels = sorted_dates
        trend_values = [registration_dates[date] for date in sorted_dates]
        
        # Get guest distribution by role
        role_counts = defaultdict(int)
        for guest in guests:
            role = guest.get("GuestRole", "Unknown")
            role_counts[role] += 1
        
        role_labels = list(role_counts.keys())
        role_values = [role_counts[role] for role in role_labels]
        
        # Check disk space
        disk = psutil.disk_usage('/')
        
        # Get last backup info
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
                ).strftime('%Y-%m-%d %H:%M')
        
        system_status = {
            "last_backup": last_backup or "No backups found",
            "storage": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent
            }
        }
        
        # Get recent activity
        recent_activity = []
        
        # Try to read from activity log file
        activity_log_path = os.path.join(config.get('PATHS', 'LogsDir'), 'activity.log')
        if os.path.exists(activity_log_path):
            try:
                with open(activity_log_path, 'r') as f:
                    # Read last 10 lines as activities
                    lines = list(f)[-10:]
                    for line in lines:
                        parts = line.strip().split(' - ', 3)
                        if len(parts) >= 3:
                            timestamp, activity_type, description = parts[0], parts[1], parts[2]
                            recent_activity.append({
                                "timestamp": timestamp,
                                "title": activity_type,
                                "description": description,
                                "type": activity_type
                            })
            except Exception as log_error:
                logger.error(f"Error reading activity log: {str(log_error)}")
        
        # Create sample activity if none exists
        if not recent_activity:
            recent_activity = [
                {
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "title": "System Started",
                    "description": "Application initialized successfully",
                    "type": "System"
                }
            ]
        
        # Prepare stats for the template
        stats = {
            "total_guests": len(guests),
            "checked_in": checked_in_count,
            "faculty_count": faculty_count,
            "completion_rate": round(completion_rate, 1),
            "trend_labels": trend_labels[-7:] if len(trend_labels) > 7 else trend_labels,  # Last 7 days
            "trend_values": trend_values[-7:] if len(trend_values) > 7 else trend_values,  # Last 7 days
            "role_labels": role_labels,
            "role_values": role_values
        }
        
        # Log this admin activity
        log_activity("Admin", f"Admin {admin['user_id']} viewed dashboard")
        
        return templates.TemplateResponse(
            "admin/dashboard.html", 
            {
                "request": request,
                "admin": admin,
                "stats": stats,
                "system_status": system_status,
                "recent_activity": recent_activity,
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
                "error_details": str(e) if config.getboolean('DEFAULT', 'Debug', fallback=False) else None
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
        
        # Log this admin activity
        log_activity("Email", f"Admin {admin['user_id']} sent emails to {len(recipients)} recipients")
        
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

@router.get("/admin_dashboard", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request, admin: Dict = Depends(get_current_admin)):
    """
    Alias for admin dashboard - redirects to /admin/dashboard for compatibility
    """
    return RedirectResponse(url="/admin/dashboard")

@router.get("/all_guests", response_class=HTMLResponse)
async def all_guests_page(request: Request, admin: Dict = Depends(get_current_admin)):
    """View all registered guests with filtering options"""
    try:
        guests = guests_db.read_all()
        
        # Get filter parameters from query
        role_filter = request.query_params.get("role")
        attendance_filter = request.query_params.get("attendance")
        search_query = request.query_params.get("q", "").lower()
        
        # Apply filters
        if role_filter:
            guests = [g for g in guests if g.get("GuestRole") == role_filter]
            
        if attendance_filter:
            is_present = attendance_filter == "present"
            guests = [g for g in guests if g.get("DailyAttendance") == str(is_present)]
            
        if search_query:
            guests = [g for g in guests if 
                      search_query in g.get("Name", "").lower() or
                      search_query in g.get("ID", "").lower() or
                      search_query in g.get("Phone", "").lower() or
                      search_query in g.get("Email", "").lower()]
        
        # Get unique roles for filter dropdown
        roles = sorted(set(g.get("GuestRole", "Unknown") for g in guests_db.read_all()))
        
        return templates.TemplateResponse(
            "admin/all_guests.html",
            {
                "request": request,
                "guests": guests,
                "roles": roles,
                "role_filter": role_filter,
                "attendance_filter": attendance_filter,
                "search_query": search_query,
                "active_page": "all_guests"
            }
        )
    except Exception as e:
        logger.error(f"Error listing all guests: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading guest list",
                "error_details": str(e) if config.getboolean('DEFAULT', 'Debug', fallback=False) else None
            }
        )

@router.get("/guest_registration", response_class=HTMLResponse)
async def guest_registration_page(request: Request):
    """Guest registration page for admin (redirects to common route)"""
    return RedirectResponse(url="/guest_registration")

@router.get("/backup", response_class=HTMLResponse)
async def backup_page(request: Request, admin: Dict = Depends(get_current_admin)):
    """Manage database backups"""
    try:
        # Get list of backups
        backup_dir = Path(config.get('DATABASE', 'BackupDir'))
        backups = []
        
        if backup_dir.exists():
            backup_files = sorted(
                [f for f in backup_dir.glob("*.csv") if f.is_file()],
                key=lambda x: os.path.getmtime(x),
                reverse=True
            )
            
            for backup_file in backup_files:
                file_stats = os.stat(backup_file)
                backups.append({
                    "name": backup_file.name,
                    "size": f"{file_stats.st_size / 1024:.1f} KB",
                    "date": datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
        
        return templates.TemplateResponse(
            "admin/backup.html",
            {
                "request": request,
                "backups": backups,
                "active_page": "backup"
            }
        )
    except Exception as e:
        logger.error(f"Error loading backup page: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading backup page",
                "error_details": str(e) if config.getboolean('DEFAULT', 'Debug', fallback=False) else None
            }
        )

@router.post("/create_backup")
async def create_backup(request: Request, admin: Dict = Depends(get_current_admin)):
    """Create a new backup of the database"""
    try:
        backup_path = guests_db.create_backup(f"manual_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv")
        
        if backup_path:
            log_activity("Backup", f"Admin {admin['user_id']} created manual backup")
            return JSONResponse(content={
                "success": True,
                "message": "Backup created successfully",
                "backup_path": backup_path
            })
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "Failed to create backup"}
            )
    except Exception as e:
        logger.error(f"Error creating backup: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error creating backup: {str(e)}"}
        )

@router.post("/restore_backup")
async def restore_backup(
    request: Request,
    admin: Dict = Depends(get_current_admin),
    backup_file: str = Form(...)
):
    """Restore the database from a backup file"""
    try:
        backup_path = os.path.join(config.get('DATABASE', 'BackupDir'), backup_file)
        
        if not os.path.exists(backup_path):
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Backup file not found"}
            )
        
        # Create a backup of the current data before restoring
        guests_db.create_backup("pre_restore_backup.csv")
        
        # Copy the backup file to the database location
        import shutil
        shutil.copy2(backup_path, config.get('DATABASE', 'CSVPath'))
        
        log_activity("Restore", f"Admin {admin['user_id']} restored from backup: {backup_file}")
        
        return JSONResponse(content={
            "success": True,
            "message": "Database restored successfully from backup"
        })
    except Exception as e:
        logger.error(f"Error restoring backup: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error restoring backup: {str(e)}"}
        )

@router.get("/report", response_class=HTMLResponse)
async def report_page(request: Request, admin: Dict = Depends(get_current_admin)):
    """Generate reports and analytics"""
    try:
        # Get guest data
        guests = guests_db.read_all()
        
        # Calculate basic statistics
        total_guests = len(guests)
        checked_in = sum(1 for g in guests if g.get("DailyAttendance") == "True")
        kit_received = sum(1 for g in guests if g.get("KitReceived") == "True")
        badges_printed = sum(1 for g in guests if g.get("BadgePrinted") == "True")
        
        # Payment statistics
        payment_status = defaultdict(int)
        total_collected = 0
        
        for guest in guests:
            status = guest.get("PaymentStatus", "Unknown")
            payment_status[status] += 1
            
            if status == "Paid":
                try:
                    amount = float(guest.get("PaymentAmount", "0"))
                    total_collected += amount
                except (ValueError, TypeError):
                    pass
        
        # Guest distribution by role
        role_distribution = defaultdict(int)
        for guest in guests:
            role = guest.get("GuestRole", "Unknown")
            role_distribution[role] += 1
        
        return templates.TemplateResponse(
            "admin/report.html",
            {
                "request": request,
                "admin": admin,
                "total_guests": total_guests,
                "checked_in": checked_in,
                "kit_received": kit_received,
                "badges_printed": badges_printed,
                "payment_status": dict(payment_status),
                "total_collected": total_collected,
                "role_distribution": dict(role_distribution),
                "active_page": "report"
            }
        )
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error generating report",
                "error_details": str(e) if config.getboolean('DEFAULT', 'Debug', fallback=False) else None
            }
        )
    
    
@router.post("/login")
async def process_admin_login(
    request: Request,
    password: str = Form(...),
):
    """Process admin login"""
    try:
        # Verify password against the configured admin password
        if password == config.get('DEFAULT', 'AdminPassword'):
            # Create admin session
            session_id = auth_service.create_session("admin", "admin")
            
            # Redirect to admin dashboard with session cookie
            response = RedirectResponse(url="/admin/dashboard", status_code=303)
            response.set_cookie(
                key="session_id",
                value=session_id,
                httponly=True,
                max_age=43200  # 12 hours
            )
            
            # Log successful login
            log_activity("Admin", "Admin login successful")
            
            return response
        else:
            # Log failed login attempt
            log_activity("Admin", "Admin login failed - incorrect password")
            
            # Show error message
            return templates.TemplateResponse(
                "admin/login.html",
                {
                    "request": request,
                    "error": "Incorrect password",
                    "active_page": "admin_login"
                }
            )
            
    except Exception as e:
        logger.error(f"Admin login error: {str(e)}")
        return templates.TemplateResponse(
            "admin/login.html",
            {
                "request": request,
                "error": "An error occurred during login",
                "active_page": "admin_login"
            }
        )