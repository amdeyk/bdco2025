# app/routes/admin.py

from fastapi import APIRouter, Request, Form, Depends, HTTPException, Response, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from typing import Optional, List, Dict
import logging
import os
import re
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
from fastapi.responses import StreamingResponse
import csv
import io
from app.utils.changelog import ChangelogManager
import random
from fastapi import Path as FastAPIPath
from pathlib import Path
from fastapi.responses import StreamingResponse
import io
from PIL import Image, ImageDraw
import qrcode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import csv
import logging
import uuid
import shutil
from app.config import Config
from app.templates import templates

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/admin", tags=["admin"])

# Initialize services
config = Config()
email_config = Config("email_config.ini")
guests_db = CSVDatabase(
    config.get('DATABASE', 'CSVPath'),
    config.get('DATABASE', 'BackupDir')
)

# Use singleton auth_service from app.services.auth
email_service = EmailService(
    smtp_server=email_config.get('EMAIL', 'SMTPServer'),
    smtp_port=email_config.getint('EMAIL', 'SMTPPort'),
    username=email_config.get('EMAIL', 'Username'),
    password=email_config.get('EMAIL', 'Password'),
    sender=f"{email_config.get('EMAIL', 'SenderName')} <{email_config.get('EMAIL', 'SenderEmail')}>"
)

# Paths for storing email history and attachments
EMAIL_LOG_CSV = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), 'emails.csv')
EMAIL_ATTACH_DIR = os.path.join(config.get('PATHS', 'StaticDir'), 'uploads/email_attachments')
os.makedirs(EMAIL_ATTACH_DIR, exist_ok=True)
EMAIL_TEMPLATE_DIR = os.path.join('email_templates')
os.makedirs(EMAIL_TEMPLATE_DIR, exist_ok=True)

# Allowed categories for outgoing emails
EMAIL_CATEGORIES = [
    'Introduction', 'pre-conference info1', 'pre-conf info 2', 'Sponsor info1',
    'Sponsor Info2', 'Speaker info 1', 'Speaker info 2', 'Schedule of conference',
    'RSVP of Conference', 'conference day 1', 'conference day 2', 'Thank you',
    'Certificate', 'Post Conference 1', 'Post Conference 2'
]

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
            recent_activity = [{
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "title": "System Started",
                "description": "Application initialized successfully",
                "type": "System"
            }]
        
        # Prepare stats for the template
        stats = {
            "total_guests": len(guests),
            "checked_in": checked_in_count,
            "faculty_count": faculty_count,
            "completion_rate": round(completion_rate, 1),
            "trend_labels": trend_labels[-7:] if len(trend_labels) > 7 else trend_labels, # Last 7 days
            "trend_values": trend_values[-7:] if len(trend_values) > 7 else trend_values, # Last 7 days
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
    recipient_ids: Optional[str] = Form(None),
    category: str = Form(...),
    attachment: UploadFile = File(None)
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
        category: Category of the email
        attachment: Optional file attachment
    Returns:
        JSONResponse: Result of email sending operation
    """
    try:
        # Get recipients based on criteria
        guests = guests_db.read_all()
        recipients = []
        recipient_ids_list = []

        if category not in EMAIL_CATEGORIES:
            return JSONResponse(status_code=400, content={"success": False, "message": "Invalid category"})
        
        if recipient_ids:
            # Send to specific guests
            guest_ids = [id.strip() for id in recipient_ids.split(',')]
            recipient_ids_list = guest_ids
            recipients = [
                guest["Email"] for guest in guests
                if guest["ID"] in guest_ids and guest.get("Email")
            ]
        elif recipient_role:
            # Send to all guests with specified role
            recipients = [
                guest["Email"] for guest in guests
                if guest.get("GuestRole") == recipient_role and guest.get("Email")
            ]
            recipient_ids_list = [g["ID"] for g in guests if g.get("GuestRole") == recipient_role]
        else:
            # Send to all guests
            recipients = [
                guest["Email"] for guest in guests if guest.get("Email")
            ]
            recipient_ids_list = [g["ID"] for g in guests if g.get("Email")]
        
        if not recipients:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No valid recipients found"}
            )
        
        # Save attachment if provided
        attachment_path = None
        if attachment is not None:
            filename = f"{uuid.uuid4()}_{attachment.filename}"
            attachment_path = os.path.join(EMAIL_ATTACH_DIR, filename)
            with open(attachment_path, "wb") as buffer:
                shutil.copyfileobj(attachment.file, buffer)

        # Send emails
        results = email_service.send_bulk_email(recipients, subject, message, attachments=[attachment_path] if attachment_path else None)
        
        # Count successes and failures
        successes = sum(1 for _, success in results if success)
        failures = len(results) - successes
        
        # Log this admin activity
        log_activity("Email", f"Admin {admin['user_id']} sent emails to {len(recipients)} recipients")

        # Record emails to CSV for history
        timestamp = datetime.now().isoformat()
        fieldnames = ["timestamp", "admin_id", "recipient_ids", "recipients", "category", "subject", "message", "attachment"]
        row = {
            "timestamp": timestamp,
            "admin_id": admin.get("user_id"),
            "recipient_ids": ",".join(recipient_ids_list),
            "recipients": ",".join(recipients),
            "category": category,
            "subject": subject,
            "message": message,
            "attachment": os.path.basename(attachment_path) if attachment_path else ""
        }
        write_header = not os.path.exists(EMAIL_LOG_CSV)
        with open(EMAIL_LOG_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        
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

@router.get("/email_template/{category}")
async def get_email_template(category: str, admin: Dict = Depends(get_current_admin)):
    """Return the email template content for the given category"""
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", category.strip().lower())
    template_path = os.path.join(EMAIL_TEMPLATE_DIR, f"{sanitized}.txt")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
        return JSONResponse(content={"template": content})
    return JSONResponse(content={"template": ""})

@router.get("/email_client", response_class=HTMLResponse)
async def email_client_page(request: Request, admin: Dict = Depends(get_current_admin)):
    """Interface for sending emails and viewing history"""
    guests = guests_db.read_all()
    roles = sorted(set(g.get("GuestRole", "") for g in guests))
    emails = []
    if os.path.exists(EMAIL_LOG_CSV):
        with open(EMAIL_LOG_CSV, newline="", encoding="utf-8") as f:
            emails = list(csv.DictReader(f))

    stats = {c: 0 for c in EMAIL_CATEGORIES}
    for e in emails:
        cat = e.get("category")
        if cat in stats:
            stats[cat] += 1
    emails = sorted(emails, key=lambda x: x.get("timestamp", ""), reverse=True)

    return templates.TemplateResponse(
        "admin/email_client.html",
        {
            "request": request,
            "guests": guests,
            "roles": roles,
            "emails": emails,
            "categories": EMAIL_CATEGORIES,
            "stats": stats,
            "active_page": "email_client",
        },
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
    """Generate comprehensive reports and analytics"""
    try:
        # Get guest data
        guests = guests_db.read_all()
        
        # Calculate basic statistics
        total_guests = len(guests)
        checked_in = sum(1 for g in guests if g.get("DailyAttendance") == "True")
        kit_received = sum(1 for g in guests if g.get("KitReceived") == "True")
        badges_printed = sum(1 for g in guests if g.get("BadgePrinted") == "True")
        
        # Payment statistics
        payment_status_dict = {}
        total_collected = 0
        
        for guest in guests:
            status = guest.get("PaymentStatus", "Unknown")
            payment_status_dict[status] = payment_status_dict.get(status, 0) + 1
            
            if status == "Paid":
                try:
                    amount = float(guest.get("PaymentAmount", "0"))
                    total_collected += amount
                except (ValueError, TypeError):
                    pass
        
        # Guest distribution by role
        role_distribution_dict = {}
        for guest in guests:
            role = guest.get("GuestRole", "Unknown")
            role_distribution_dict[role] = role_distribution_dict.get(role, 0) + 1
        
        # Registration trends over time
        reg_date_dict = {}
        for guest in guests:
            try:
                if guest.get("RegistrationDate"):
                    date = datetime.fromisoformat(guest.get("RegistrationDate")).strftime('%Y-%m-%d')
                    reg_date_dict[date] = reg_date_dict.get(date, 0) + 1
            except (ValueError, TypeError):
                continue
        
        # Sort dates
        dates = sorted(reg_date_dict.keys())
        
        # Prepare data for charts
        registration_labels = dates[-30:] if len(dates) > 30 else dates
        registration_values = [reg_date_dict.get(date, 0) for date in registration_labels]
        
        # Convert all dictionaries to lists for template
        payment_status_labels = list(payment_status_dict.keys())
        payment_status_values = list(payment_status_dict.values())
        
        role_distribution_labels = list(role_distribution_dict.keys())
        role_distribution_values = list(role_distribution_dict.values())
        
        # Get journey data
        journey_data = []
        journey_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "journey.csv")
        if os.path.exists(journey_csv):
            with open(journey_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                journey_data = list(reader)
        
        # Journey statistics
        total_journeys = len(journey_data)
        pickup_needed = sum(1 for j in journey_data if j.get("pickup_required") == "True")
        drop_needed = sum(1 for j in journey_data if j.get("drop_required") == "True")
        
        # Get presentation data
        presentations = []
        presentations_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "presentations.csv")
        if os.path.exists(presentations_csv):
            with open(presentations_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                presentations = list(reader)
        
        # Presentation statistics
        total_presentations = len(presentations)
        presentation_types_dict = {}
        for p in presentations:
            p_type = p.get("file_type", "unknown")
            presentation_types_dict[p_type] = presentation_types_dict.get(p_type, 0) + 1
        
        presentation_type_labels = list(presentation_types_dict.keys())
        presentation_type_values = list(presentation_types_dict.values())
        
        # Attendance trend (sample data)
        attendance_labels = dates[-7:] if dates else []
        attendance_values = [random.randint(0, total_guests) for _ in attendance_labels]
        
        # Faculty-specific statistics
        faculty_count = sum(1 for g in guests if g.get("GuestRole") == "Faculty")
        faculty_data = []
        faculty_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "faculty.csv")
        if os.path.exists(faculty_csv):
            with open(faculty_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                faculty_data = list(reader)
        
        faculty_with_presentations = len(set(p.get("guest_id") for p in presentations))
        faculty_with_accommodations = sum(1 for f in faculty_data if "accommodation_required" in f and f["accommodation_required"] == "True")
        
        # Message statistics
        messages = []
        messages_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "messages.csv")
        if os.path.exists(messages_csv):
            with open(messages_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                messages = list(reader)
        
        unread_messages = sum(1 for m in messages if m.get("read") == "False")
        
        # Recent changelog entries (empty for now)
        recent_changes = []
        
        return templates.TemplateResponse(
            "admin/report.html",
            {
                "request": request,
                "admin": admin,
                "total_guests": total_guests,
                "checked_in": checked_in,
                "kit_received": kit_received,
                "badges_printed": badges_printed,
                "total_collected": total_collected,
                # Lists for the charts
                "registration_labels": registration_labels,
                "registration_values": registration_values,
                "payment_status_labels": payment_status_labels,
                "payment_status_values": payment_status_values,
                "role_distribution_labels": role_distribution_labels,
                "role_distribution_values": role_distribution_values,
                "presentation_type_labels": presentation_type_labels,
                "presentation_type_values": presentation_type_values,
                "attendance_labels": attendance_labels,
                "attendance_values": attendance_values,
                # Journey statistics
                "total_journeys": total_journeys,
                "pickup_needed": pickup_needed,
                "drop_needed": drop_needed,
                "total_presentations": total_presentations,
                # Faculty statistics
                "faculty_stats": {
                    "total": faculty_count,
                    "with_presentations": faculty_with_presentations,
                    "with_accommodations": faculty_with_accommodations
                },
                # Message statistics
                "message_stats": {
                    "total": len(messages),
                    "unread": unread_messages
                },
                "recent_changes": recent_changes,
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
                max_age=43200 # 12 hours
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

@router.get("/report/export/guest_list")
async def export_guest_list(
    admin: Dict = Depends(get_current_admin),
    role: Optional[str] = None,
    attendance: Optional[str] = None,
    payment: Optional[str] = None,
    format: str = "csv"
):
    """Export guest list as CSV or Excel"""
    try:
        guests = guests_db.read_all()
        
        # Apply filters
        if role:
            guests = [g for g in guests if g.get("GuestRole") == role]
        
        if attendance:
            is_present = attendance == "present"
            guests = [g for g in guests if g.get("DailyAttendance") == str(is_present)]
            
        if payment:
            guests = [g for g in guests if g.get("PaymentStatus") == payment]
        
        if format.lower() == "csv":
            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "ID", "Name", "Email", "Phone", "Role", "Registration Date", 
                "Check-in Status", "Kit Status", "Badge Status", "Payment Status", "Amount"
            ])
            
            # Write data
            for guest in guests:
                writer.writerow([
                    guest.get("ID", ""),
                    guest.get("Name", ""),
                    guest.get("Email", ""),
                    guest.get("Phone", ""),
                    guest.get("GuestRole", ""),
                    guest.get("RegistrationDate", ""),
                    "Checked In" if guest.get("DailyAttendance") == "True" else "Not Checked In",
                    "Received" if guest.get("KitReceived") == "True" else "Not Received",
                    "Printed" if guest.get("BadgePrinted") == "True" else "Not Printed",
                    guest.get("PaymentStatus", ""),
                    guest.get("PaymentAmount", "")
                ])
            
            # Return as downloadable CSV
            output.seek(0)
            filename = f"guest_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
        elif format.lower() == "excel":
            # If pandas and openpyxl are installed, use them for Excel export
            try:
                import pandas as pd
                import io as io_excel
                
                # Convert to pandas DataFrame
                data = []
                for guest in guests:
                    data.append({
                        "ID": guest.get("ID", ""),
                        "Name": guest.get("Name", ""),
                        "Email": guest.get("Email", ""),
                        "Phone": guest.get("Phone", ""),
                        "Role": guest.get("GuestRole", ""),
                        "Registration Date": guest.get("RegistrationDate", ""),
                        "Check-in Status": "Checked In" if guest.get("DailyAttendance") == "True" else "Not Checked In",
                        "Kit Status": "Received" if guest.get("KitReceived") == "True" else "Not Received",
                        "Badge Status": "Printed" if guest.get("BadgePrinted") == "True" else "Not Printed",
                        "Payment Status": guest.get("PaymentStatus", ""),
                        "Amount": guest.get("PaymentAmount", "")
                    })
                
                df = pd.DataFrame(data)
                
                # Create Excel in memory
                output = io_excel.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name="Guests")
                
                # Return as downloadable Excel
                output.seek(0)
                filename = f"guest_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                return StreamingResponse(
                    iter([output.getvalue()]),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            except ImportError:
                # Fall back to CSV if pandas/openpyxl not available
                return await export_guest_list(admin, role, attendance, payment, format="csv")
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported export format")
    except Exception as e:
        logger.error(f"Error exporting guest list: {str(e)}")
        raise HTTPException(status_code=500, detail="Error exporting guest list")

@router.get("/report/export_attendance")
async def export_attendance(admin: Dict = Depends(get_current_admin)):
    """Export attendance data as CSV"""
    try:
        guests = guests_db.read_all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(["ID", "Name", "Role", "Attendance Status", "Check-in Time"])
        
        # Write data
        for guest in guests:
            writer.writerow([
                guest.get("ID", ""),
                guest.get("Name", ""),
                guest.get("GuestRole", ""),
                "Present" if guest.get("DailyAttendance") == "True" else "Absent",
                guest.get("CheckInTime", "")
            ])
        
        # Return as downloadable CSV
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=attendance.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting attendance: {str(e)}")
        raise HTTPException(status_code=500, detail="Error exporting attendance")

@router.get("/report/export_payments")
async def export_payments(admin: Dict = Depends(get_current_admin)):
    """Export payment data as CSV"""
    try:
        guests = guests_db.read_all()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(["ID", "Name", "Payment Status", "Payment Amount", "Payment Date", "Payment Method"])
        
        # Write data
        for guest in guests:
            writer.writerow([
                guest.get("ID", ""),
                guest.get("Name", ""),
                guest.get("PaymentStatus", ""),
                guest.get("PaymentAmount", ""),
                guest.get("PaymentDate", ""),
                guest.get("PaymentMethod", "")
            ])
        
        # Return as downloadable CSV
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=payments.csv"}
        )
    except Exception as e:
        logger.error(f"Error exporting payments: {str(e)}")
        raise HTTPException(status_code=500, detail="Error exporting payments")

@router.get("/report/guests", response_class=HTMLResponse)
async def guest_report(
    request: Request, 
    admin: Dict = Depends(get_current_admin),
    role: Optional[str] = None,
    attendance: Optional[str] = None,
    payment: Optional[str] = None,
):
    """Detailed guest report with filtering"""
    try:
        guests = guests_db.read_all()
        
        # Apply filters
        if role:
            guests = [g for g in guests if g.get("GuestRole") == role]
        
        if attendance:
            is_present = attendance == "present"
            guests = [g for g in guests if g.get("DailyAttendance") == str(is_present)]
            
        if payment:
            guests = [g for g in guests if g.get("PaymentStatus") == payment]
        
        # Get unique values for filters
        roles = sorted(set(g.get("GuestRole", "Unknown") for g in guests_db.read_all()))
        payment_statuses = sorted(set(g.get("PaymentStatus", "Unknown") for g in guests_db.read_all()))
        
        return templates.TemplateResponse(
            "admin/reports/guest_report.html",
            {
                "request": request,
                "admin": admin,
                "guests": guests,
                "roles": roles,
                "payment_statuses": payment_statuses,
                "selected_role": role,
                "selected_attendance": attendance,
                "selected_payment": payment,
                "active_page": "report"
            }
        )
    except Exception as e:
        logger.error(f"Error generating guest report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generating guest report")

@router.get("/report/faculty", response_class=HTMLResponse)
async def faculty_report(request: Request, admin: Dict = Depends(get_current_admin)):
    """Detailed faculty report"""
    try:
        guests = [g for g in guests_db.read_all() if g.get("GuestRole") == "Faculty"]
        
        # Get faculty-specific data
        faculty_data = []
        faculty_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "faculty.csv")
        if os.path.exists(faculty_csv):
            with open(faculty_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                faculty_data = list(reader)
                
        # Map faculty data to guests
        faculty_map = {f.get("guest_id"): f for f in faculty_data}
        
        for guest in guests:
            faculty_info = faculty_map.get(guest.get("ID"))
            if faculty_info:
                for key, value in faculty_info.items():
                    if key != "guest_id":
                        guest[f"faculty_{key}"] = value
        
        # Get presentation data
        presentations = []
        presentations_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "presentations.csv")
        if os.path.exists(presentations_csv):
            with open(presentations_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                presentations = list(reader)
                
        # Group presentations by faculty
        presentation_counts = defaultdict(int)
        for p in presentations:
            presentation_counts[p.get("guest_id")] += 1
            
        for guest in guests:
            guest["presentation_count"] = presentation_counts.get(guest.get("ID"), 0)
        
        return templates.TemplateResponse(
            "admin/reports/faculty_report.html",
            {
                "request": request,
                "admin": admin,
                "faculty": guests,
                "active_page": "report"
            }
        )
    except Exception as e:
        logger.error(f"Error generating faculty report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generating faculty report")

@router.get("/report/presentations", response_class=HTMLResponse)
async def presentations_report(request: Request, admin: Dict = Depends(get_current_admin)):
    """Presentations report"""
    try:
        presentations = []
        presentations_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "presentations.csv")
        if os.path.exists(presentations_csv):
            with open(presentations_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                presentations = list(reader)
        
        # Get guest data for presenters
        guests = guests_db.read_all()
        guest_map = {g.get("ID"): g for g in guests}
        
        # Enrich presentation data with presenter info
        for presentation in presentations:
            guest_id = presentation.get("guest_id")
            guest = guest_map.get(guest_id)
            if guest:
                presentation["presenter_name"] = guest.get("Name", "Unknown")
                presentation["presenter_role"] = guest.get("GuestRole", "Unknown")
        
        return templates.TemplateResponse(
            "admin/reports/presentations_report.html",
            {
                "request": request,
                "admin": admin,
                "presentations": presentations,
                "active_page": "report"
            }
        )
    except Exception as e:
        logger.error(f"Error generating presentations report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generating presentations report")

@router.get("/report/journeys", response_class=HTMLResponse)
async def journeys_report(request: Request, admin: Dict = Depends(get_current_admin)):
    """Travel/journey report"""
    try:
        journey_data = []
        journey_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "journey.csv")
        if os.path.exists(journey_csv):
            with open(journey_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                journey_data = list(reader)
        
        # Get guest data
        guests = guests_db.read_all()
        guest_map = {g.get("ID"): g for g in guests}
        
        # Enrich journey data with guest info
        for journey in journey_data:
            guest_id = journey.get("guest_id")
            guest = guest_map.get(guest_id)
            if guest:
                journey["guest_name"] = guest.get("Name", "Unknown")
                journey["guest_role"] = guest.get("GuestRole", "Unknown")
                journey["guest_phone"] = guest.get("Phone", "Unknown")
        
        return templates.TemplateResponse(
            "admin/reports/journeys_report.html",
            {
                "request": request,
                "admin": admin,
                "journeys": journey_data,
                "active_page": "report"
            }
        )
    except Exception as e:
        logger.error(f"Error generating journey report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generating journey report")

@router.get("/report/changelog", response_class=HTMLResponse)
async def changelog_report(request: Request, admin: Dict = Depends(get_current_admin)):
    """Changelog report"""
    try:
        changelog_manager = ChangelogManager()
        entries = changelog_manager.get_entries()
        
        return templates.TemplateResponse(
            "admin/reports/changelog_report.html",
            {
                "request": request,
                "admin": admin,
                "entries": entries,
                "active_page": "report"
            }
        )
    except Exception as e:
        logger.error(f"Error generating changelog report: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generating changelog report")

@router.post("/changelog/add", response_class=JSONResponse)
async def add_changelog_entry(
    request: Request,
    admin: Dict = Depends(get_current_admin),
    title: str = Form(...),
    description: str = Form(...),
    author: str = Form(...)
):
    """Add a new changelog entry"""
    try:
        changelog_manager = ChangelogManager()
        entry = changelog_manager.add_entry(title, description, author)
        
        return JSONResponse(content={
            "success": True,
            "message": "Changelog entry added successfully",
            "entry": entry
        })
    except Exception as e:
        logger.error(f"Error adding changelog entry: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error adding changelog entry: {str(e)}"}
        )

@router.get("/guest_badges", response_class=HTMLResponse)
async def guest_badges_page(request: Request, admin: Dict = Depends(get_current_admin)):
    """Badge management page"""
    try:
        guests = guests_db.read_all()
        
        # Get filter parameters from query
        status_filter = request.query_params.get("status")
        search_query = request.query_params.get("q", "").lower()
        
        # Apply filters
        if status_filter == "printed":
            guests = [g for g in guests if g.get("BadgePrinted") == "True"]
        elif status_filter == "not_printed":
            guests = [g for g in guests if g.get("BadgePrinted") != "True"]
        elif status_filter == "given":
            guests = [g for g in guests if g.get("BadgeGiven") == "True"]
        elif status_filter == "not_given":
            guests = [g for g in guests if g.get("BadgeGiven") != "True"]
        
        if search_query:
            guests = [g for g in guests if
                search_query in g.get("Name", "").lower() or
                search_query in g.get("ID", "").lower() or
                search_query in g.get("Phone", "").lower() or
                search_query in g.get("Email", "").lower()]
        
        return templates.TemplateResponse(
            "admin/guest_badges.html",
            {
                "request": request,
                "admin": admin,
                "guests": guests,
                "status_filter": status_filter,
                "search_query": search_query,
                "active_page": "guest_badges"
            }
        )
    except Exception as e:
        logger.error(f"Error loading badge management page: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading badge management page",
                "error_details": str(e) if config.getboolean('DEFAULT', 'Debug', fallback=False) else None
            }
        )

@router.get("/journey_management", response_class=HTMLResponse)
async def journey_management_page(request: Request, admin: Dict = Depends(get_current_admin)):
    """Journey management page"""
    try:
        guests = guests_db.read_all()
        
        # Get filter parameters from query
        status_filter = request.query_params.get("status")
        search_query = request.query_params.get("q", "").lower()
        
        # Apply filters
        if status_filter == "updated":
            guests = [g for g in guests if g.get("JourneyDetailsUpdated") == "True"]
        elif status_filter == "not_updated":
            guests = [g for g in guests if g.get("JourneyDetailsUpdated") != "True"]
        elif status_filter == "completed":
            guests = [g for g in guests if g.get("JourneyCompleted") == "True"]
        elif status_filter == "ongoing":
            guests = [g for g in guests if g.get("JourneyCompleted") != "True"]
        
        if search_query:
            guests = [g for g in guests if
                search_query in g.get("Name", "").lower() or
                search_query in g.get("ID", "").lower() or
                search_query in g.get("Phone", "").lower() or
                search_query in g.get("Email", "").lower()]
        
        return templates.TemplateResponse(
            "admin/journey_management.html",
            {
                "request": request,
                "admin": admin,
                "guests": guests,
                "status_filter": status_filter,
                "search_query": search_query,
                "active_page": "journey_management"
            }
        )
    except Exception as e:
        logger.error(f"Error loading journey management page: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading journey management page",
                "error_details": str(e) if config.getboolean('DEFAULT', 'Debug', fallback=False) else None
            }
        )

@router.get("/food_management", response_class=HTMLResponse)
async def food_management_page(request: Request, admin: Dict = Depends(get_current_admin)):
    """Food coupon management page"""
    try:
        guests = guests_db.read_all()
        
        # Get filter parameters from query
        day_filter = request.query_params.get("day")
        status_filter = request.query_params.get("status")
        search_query = request.query_params.get("q", "").lower()
        
        # Apply filters
        if day_filter == "1" and status_filter == "given":
            guests = [g for g in guests if g.get("FoodCouponsDay1") == "True"]
        elif day_filter == "1" and status_filter == "not_given":
            guests = [g for g in guests if g.get("FoodCouponsDay1") != "True"]
        elif day_filter == "2" and status_filter == "given":
            guests = [g for g in guests if g.get("FoodCouponsDay2") == "True"]
        elif day_filter == "2" and status_filter == "not_given":
            guests = [g for g in guests if g.get("FoodCouponsDay2") != "True"]
        
        if search_query:
            guests = [g for g in guests if
                search_query in g.get("Name", "").lower() or
                search_query in g.get("ID", "").lower() or
                search_query in g.get("Phone", "").lower() or
                search_query in g.get("Email", "").lower()]
        
        return templates.TemplateResponse(
            "admin/food_management.html",
            {
                "request": request,
                "admin": admin,
                "guests": guests,
                "day_filter": day_filter,
                "status_filter": status_filter,
                "search_query": search_query,
                "active_page": "food_management"
            }
        )
    except Exception as e:
        logger.error(f"Error loading food management page: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading food management page",
                "error_details": str(e) if config.getboolean('DEFAULT', 'Debug', fallback=False) else None
            }
        )

@router.get("/gift_management", response_class=HTMLResponse)
async def gift_management_page(request: Request, admin: Dict = Depends(get_current_admin)):
    """Gift management page"""
    try:
        guests = guests_db.read_all()
        
        # Get filter parameters from query
        status_filter = request.query_params.get("status")
        search_query = request.query_params.get("q", "").lower()
        
        # Apply filters
        if status_filter == "given":
            guests = [g for g in guests if g.get("GiftsGiven") == "True"]
        elif status_filter == "not_given":
            guests = [g for g in guests if g.get("GiftsGiven") != "True"]
        
        if search_query:
            guests = [g for g in guests if
                search_query in g.get("Name", "").lower() or
                search_query in g.get("ID", "").lower() or
                search_query in g.get("Phone", "").lower() or
                search_query in g.get("Email", "").lower()]
        
        return templates.TemplateResponse(
            "admin/gift_management.html",
            {
                "request": request,
                "admin": admin,
                "guests": guests,
                "status_filter": status_filter,
                "search_query": search_query,
                "active_page": "gift_management"
            }
        )
    except Exception as e:
        logger.error(f"Error loading gift management page: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading gift management page",
                "error_details": str(e) if config.getboolean('DEFAULT', 'Debug', fallback=False) else None
            }
        )

@router.get("/presentations_management", response_class=HTMLResponse)
async def presentations_management(request: Request, admin: Dict = Depends(get_current_admin)):
    """View and download uploaded presentations"""
    try:
        presentations_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), 'presentations.csv')
        presentations = []
        if os.path.exists(presentations_csv):
            with open(presentations_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                presentations = list(reader)

        guests = guests_db.read_all()
        guest_map = {g['ID']: g for g in guests}
        for p in presentations:
            g = guest_map.get(p.get('guest_id'))
            if g:
                p['guest_name'] = g.get('Name', 'Unknown')
                p['guest_role'] = g.get('GuestRole', '')
            p['file_url'] = f"/admin/download_presentation/{p.get('file_path')}"

        return templates.TemplateResponse(
            "admin/presentations_management.html",
            {"request": request, "admin": admin, "presentations": presentations, "active_page": "presentations_management"}
        )
    except Exception as e:
        logger.error(f"Error loading presentations management page: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "Error loading presentations", "error_details": str(e) if config.getboolean('DEFAULT', 'Debug', fallback=False) else None}
        )

@router.get("/download_presentation/{file_name}")
async def download_presentation(admin: Dict = Depends(get_current_admin), file_name: str = FastAPIPath(...)):
    """Download an uploaded presentation file"""
    try:
        file_path = os.path.join(config.get('PATHS', 'StaticDir'), 'uploads', 'presentations', file_name)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        return StreamingResponse(open(file_path, 'rb'), headers={'Content-Disposition': f'attachment; filename="{file_name}"'})
    except Exception as e:
        logger.error(f"Error downloading presentation: {e}")
        raise HTTPException(status_code=500, detail="Error downloading presentation")

# BADGE MANAGEMENT ROUTES

@router.post("/print_badge")
async def print_badge(request: Request, admin: Dict = Depends(get_current_admin), guest_id: str = Form(...)):
    """Mark badge as printed for a guest (for tracking purposes)"""
    try:
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                guest["BadgePrinted"] = "True"
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity(guest_id, f"Admin {admin['user_id']} marked badge as printed")
            
            return JSONResponse(
                content={"success": True, "message": "Badge marked as printed successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
    except Exception as e:
        logger.error(f"Error marking badge as printed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error: {str(e)}"}
        )

@router.get("/download_badge/{guest_id}")
async def download_badge(admin: Dict = Depends(get_current_admin), guest_id: str = FastAPIPath(...)):
    """Download badge for a guest (can be called multiple times)"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        # Create badge design
        badge_image = create_simple_badge(guest)
        
        # Convert to bytes
        img_byte_array = io.BytesIO()
        badge_image.save(img_byte_array, format='PNG')
        img_byte_array.seek(0)
        
        # Log this activity
        log_activity(guest_id, f"Admin {admin['user_id']} downloaded badge")
        
        return StreamingResponse(
            img_byte_array,
            media_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="Badge_{guest_id}_{guest.get("Name", "Guest").replace(" ", "_")}.png"'
            }
        )

    except Exception as e:
        logger.error(f"Error downloading badge: {str(e)}")
        raise HTTPException(status_code=500, detail="Error downloading badge")

@router.post("/print_and_download_badge")
async def print_and_download_badge(request: Request, admin: Dict = Depends(get_current_admin), guest_id: str = Form(...)):
    """Print badge (download) and mark as printed"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if not guest:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )

        # Mark as printed in database
        for g in guests:
            if g["ID"] == guest_id:
                g["BadgePrinted"] = "True"
                break
                
        guests_db.write_all(guests)
        
        # Create badge design
        badge_image = create_simple_badge(guest)
        
        # Convert to bytes
        img_byte_array = io.BytesIO()
        badge_image.save(img_byte_array, format='PNG')
        img_byte_array.seek(0)
        
        # Log this activity
        log_activity(guest_id, f"Admin {admin['user_id']} printed and downloaded badge")
        
        # Return the badge file for download
        return StreamingResponse(
            img_byte_array,
            media_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="Badge_{guest_id}_{guest.get("Name", "Guest").replace(" ", "_")}.png"'
            }
        )

    except Exception as e:
        logger.error(f"Error printing and downloading badge: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error: {str(e)}"}
        )

@router.post("/give_badge")
async def give_badge(request: Request, admin: Dict = Depends(get_current_admin), guest_id: str = Form(...)):
    """Mark badge as given to guest"""
    try:
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                # Only allow giving badge if it has been printed
                if guest.get("BadgePrinted") != "True":
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "message": "Badge must be printed first"}
                    )
                
                # Check if badge is already given
                if guest.get("BadgeGiven") == "True":
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "message": "Badge has already been given"}
                    )
                
                guest["BadgeGiven"] = "True"
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity(guest_id, f"Admin {admin['user_id']} marked badge as given")
            
            return JSONResponse(
                content={"success": True, "message": "Badge marked as given successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
    except Exception as e:
        logger.error(f"Error giving badge: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error giving badge: {str(e)}"}
        )

@router.get("/single_guest/{guest_id}", response_class=HTMLResponse)
async def single_guest_view(request: Request, admin: Dict = Depends(get_current_admin), guest_id: str = FastAPIPath(...)):
    """Show single guest details"""
    try:
        logger.info(f"Admin {admin['user_id']} accessing guest details for ID: {guest_id}")
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if not guest:
            logger.error(f"Guest not found with ID: {guest_id}")
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "message": "Guest not found",
                    "admin": admin
                },
                status_code=404
            )
            
        # Get guest presentations
        presentations_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), 'presentations.csv')
        presentations = []
        if os.path.exists(presentations_csv):
            with open(presentations_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('guest_id') == guest_id:
                        row['file_url'] = f"/admin/download_presentation/{row.get('file_path')}"
                        presentations.append(row)

        # Get guest messages
        messages_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), 'messages.csv')
        messages = []
        if os.path.exists(messages_csv):
            with open(messages_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('guest_id') == guest_id:
                        row['message'] = row.get('message') or row.get('content', '')
                        messages.append(row)

        # Get guest activities (placeholder for now)
        activities = []
        
        return templates.TemplateResponse(
            "admin/single_guest.html",
            {
                "request": request,
                "admin": admin,
                "guest": guest,
                "guest_activities": activities,
                "presentations": presentations,
                "messages": messages,
                "active_page": "all_guests"
            }
        )
    except Exception as e:
        logger.error(f"Error loading single guest page: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading guest details",
                "admin": admin,
                "error_details": str(e) if config.getboolean('DEFAULT', 'Debug', fallback=False) else None
            },
            status_code=500
        )

@router.get("/generate_badge/{guest_id}")
async def generate_badge(admin: Dict = Depends(get_current_admin), guest_id: str = FastAPIPath(...)):
    """Generate and download badge for a guest"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        # Create a simple badge design
        badge_image = create_simple_badge(guest)
        
        # Convert to bytes
        img_byte_array = io.BytesIO()
        badge_image.save(img_byte_array, format='PNG')
        img_byte_array.seek(0)
        
        # Log this activity
        log_activity(guest_id, f"Admin {admin['user_id']} generated badge")
        
        return StreamingResponse(
            img_byte_array,
            media_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="{guest_id}_badge.png"'
            }
        )

    except Exception as e:
        logger.error(f"Error generating badge: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating badge")

@router.post("/print_badges_bulk")
async def print_badges_bulk(request: Request, admin: Dict = Depends(get_current_admin)):
    """Print badges for multiple guests"""
    try:
        data = await request.json()
        guest_ids = data.get('guest_ids', [])
        
        if not guest_ids:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No guest IDs provided"}
            )
            
        guests = guests_db.read_all()
        updated_count = 0
        
        for guest in guests:
            if guest["ID"] in guest_ids:
                guest["BadgePrinted"] = "True"
                updated_count += 1
                
        if updated_count > 0:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity("Bulk", f"Admin {admin['user_id']} printed badges for {updated_count} guests")
            
            return JSONResponse(
                content={"success": True, "message": f"Printed badges for {updated_count} guests successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "No matching guests found"}
            )
    except Exception as e:
        logger.error(f"Error printing badges in bulk: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error printing badges: {str(e)}"}
        )

@router.post("/give_badges_bulk")
async def give_badges_bulk(request: Request, admin: Dict = Depends(get_current_admin)):
    """Mark badges as given for multiple guests"""
    try:
        data = await request.json()
        guest_ids = data.get('guest_ids', [])
        
        if not guest_ids:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No guest IDs provided"}
            )
            
        guests = guests_db.read_all()
        updated_count = 0
        
        for guest in guests:
            if guest["ID"] in guest_ids and guest.get("BadgePrinted") == "True":
                guest["BadgeGiven"] = "True"
                updated_count += 1
                
        if updated_count > 0:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity("Bulk", f"Admin {admin['user_id']} marked {updated_count} badges as given")
            
            return JSONResponse(
                content={"success": True, "message": f"Marked {updated_count} badges as given successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "No matching guests with printed badges found"}
            )
    except Exception as e:
        logger.error(f"Error giving badges in bulk: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error giving badges: {str(e)}"}
        )

# JOURNEY MANAGEMENT ROUTES

@router.post("/update_journey_status")
async def update_journey_status(request: Request, admin: Dict = Depends(get_current_admin), guest_id: str = Form(...)):
    """Mark journey details as updated"""
    try:
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                guest["JourneyDetailsUpdated"] = "True"
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity(guest_id, f"Admin {admin['user_id']} marked journey details as updated")
            
            return JSONResponse(
                content={"success": True, "message": "Journey details marked as updated successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
    except Exception as e:
        logger.error(f"Error updating journey status: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error updating journey status: {str(e)}"}
        )

@router.post("/complete_journey")
async def complete_journey(request: Request, admin: Dict = Depends(get_current_admin), guest_id: str = Form(...)):
    """Mark journey as completed"""
    try:
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                guest["JourneyCompleted"] = "True"
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity(guest_id, f"Admin {admin['user_id']} marked journey as completed")
            
            return JSONResponse(
                content={"success": True, "message": "Journey marked as completed successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
    except Exception as e:
        logger.error(f"Error completing journey: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error completing journey: {str(e)}"}
        )

@router.post("/update_journey_status_bulk")
async def update_journey_status_bulk(request: Request, admin: Dict = Depends(get_current_admin)):
    """Mark journey details as updated for multiple guests"""
    try:
        data = await request.json()
        guest_ids = data.get('guest_ids', [])
        
        if not guest_ids:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No guest IDs provided"}
            )
            
        guests = guests_db.read_all()
        updated_count = 0
        
        for guest in guests:
            if guest["ID"] in guest_ids:
                guest["JourneyDetailsUpdated"] = "True"
                updated_count += 1
                
        if updated_count > 0:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity("Bulk", f"Admin {admin['user_id']} updated journey details for {updated_count} guests")
            
            return JSONResponse(
                content={"success": True, "message": f"Journey details updated for {updated_count} guests successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "No matching guests found"}
            )
    except Exception as e:
        logger.error(f"Error updating journey details in bulk: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error updating journey details: {str(e)}"}
        )

@router.post("/complete_journey_bulk")
async def complete_journey_bulk(request: Request, admin: Dict = Depends(get_current_admin)):
    """Mark journeys as completed for multiple guests"""
    try:
        data = await request.json()
        guest_ids = data.get('guest_ids', [])
        
        if not guest_ids:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No guest IDs provided"}
            )
            
        guests = guests_db.read_all()
        updated_count = 0
        
        for guest in guests:
            if guest["ID"] in guest_ids:
                guest["JourneyCompleted"] = "True"
                updated_count += 1
                
        if updated_count > 0:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity("Bulk", f"Admin {admin['user_id']} completed journeys for {updated_count} guests")
            
            return JSONResponse(
                content={"success": True, "message": f"Journeys completed for {updated_count} guests successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "No matching guests found"}
            )
    except Exception as e:
        logger.error(f"Error completing journeys in bulk: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error completing journeys: {str(e)}"}
        )

@router.get("/download_itinerary/{guest_id}")
async def download_itinerary(admin: Dict = Depends(get_current_admin), guest_id: str = FastAPIPath(...)):
    """Generate and download journey itinerary for a guest"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        # Create itinerary document
        itinerary_content = create_itinerary_document(guest)
        
        # Convert to bytes
        buffer = io.BytesIO()
        buffer.write(itinerary_content.encode('utf-8'))
        buffer.seek(0)
        
        # Log this activity
        log_activity(guest_id, f"Admin {admin['user_id']} downloaded itinerary")
        
        return StreamingResponse(
            buffer,
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="Itinerary_{guest_id}_{guest.get("Name", "Guest").replace(" ", "_")}.txt"'
            }
        )

    except Exception as e:
        logger.error(f"Error downloading itinerary: {str(e)}")
        raise HTTPException(status_code=500, detail="Error downloading itinerary")

@router.post("/update_journey_details")
async def update_journey_details(request: Request, admin: Dict = Depends(get_current_admin)):
    """Update complete journey details with all fields"""
    try:
        data = await request.json()
        guest_id = data.get('guest_id')
        
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                # Update inward journey details
                guest["InwardJourneyDate"] = data.get('inward_date', '')
                guest["InwardJourneyFrom"] = data.get('inward_from', '')
                guest["InwardJourneyTo"] = data.get('inward_to', '')
                guest["InwardJourneyDetails"] = data.get('inward_details', '')
                guest["InwardPickupRequired"] = "True" if data.get('inward_pickup') else "False"
                guest["InwardJourneyRemarks"] = data.get('inward_remarks', '')
                
                # Update outward journey details
                guest["OutwardJourneyDate"] = data.get('outward_date', '')
                guest["OutwardJourneyFrom"] = data.get('outward_from', '')
                guest["OutwardJourneyTo"] = data.get('outward_to', '')
                guest["OutwardJourneyDetails"] = data.get('outward_details', '')
                guest["OutwardDropRequired"] = "True" if data.get('outward_drop') else "False"
                guest["OutwardJourneyRemarks"] = data.get('outward_remarks', '')
                
                # Mark journey details as updated
                guest["JourneyDetailsUpdated"] = "True"
                guest["LastJourneyUpdate"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity(guest_id, f"Admin {admin['user_id']} updated complete journey details")
            
            return JSONResponse(
                content={"success": True, "message": "Journey details updated successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
    except Exception as e:
        logger.error(f"Error updating journey details: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error updating journey details: {str(e)}"}
        )

@router.get("/api/journey-details/{guest_id}")
async def get_journey_details(guest_id: str, admin: Dict = Depends(get_current_admin)):
    """Get detailed journey information for a specific guest"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if not guest:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
        
        journey_details = {
            "inward_date": guest.get("InwardJourneyDate", ""),
            "inward_origin": guest.get("InwardJourneyFrom", ""),
            "inward_destination": guest.get("InwardJourneyTo", ""),
            "inward_details": guest.get("InwardJourneyDetails", ""),
            "inward_pickup": guest.get("InwardPickupRequired", "False"),
            "inward_remarks": guest.get("InwardJourneyRemarks", ""),
            "outward_date": guest.get("OutwardJourneyDate", ""),
            "outward_origin": guest.get("OutwardJourneyFrom", ""),
            "outward_destination": guest.get("OutwardJourneyTo", ""),
            "outward_details": guest.get("OutwardJourneyDetails", ""),
            "outward_drop": guest.get("OutwardDropRequired", "False"),
            "outward_remarks": guest.get("OutwardJourneyRemarks", ""),
        }
        
        return JSONResponse(
            content={"success": True, "journey": journey_details}
        )
    except Exception as e:
        logger.error(f"Error getting journey details: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error getting journey details: {str(e)}"}
        )

# ENHANCED FOOD MANAGEMENT ROUTES (Updated from paste content)

@router.post("/give_food_coupon")
async def give_food_coupon(request: Request, admin: Dict = Depends(get_current_admin), guest_id: str = Form(...), day: str = Form(...)):
    """Give food coupons to guest for a specific day"""
    try:
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                if day == "1":
                    if guest.get("FoodCouponsDay1") == "True":
                        return JSONResponse(
                            status_code=400,
                            content={"success": False, "message": "Food coupons for Day 1 already given"}
                        )
                    guest["FoodCouponsDay1"] = "True"
                    guest["FoodCouponsDay1Date"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                elif day == "2":
                    if guest.get("FoodCouponsDay2") == "True":
                        return JSONResponse(
                            status_code=400,
                            content={"success": False, "message": "Food coupons for Day 2 already given"}
                        )
                    guest["FoodCouponsDay2"] = "True"
                    guest["FoodCouponsDay2Date"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                else:
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "message": "Invalid day specified"}
                    )
                
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity(guest_id, f"Admin {admin['user_id']} gave Day {day} food coupons")
            
            return JSONResponse(
                content={"success": True, "message": f"Food coupons for Day {day} marked as given successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
    except Exception as e:
        logger.error(f"Error giving food coupons: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error giving food coupons: {str(e)}"}
        )

@router.post("/give_food_coupons_bulk")
async def give_food_coupons_bulk(request: Request, admin: Dict = Depends(get_current_admin)):
    """Give food coupons to multiple guests"""
    try:
        data = await request.json()
        guest_ids = data.get('guest_ids', [])
        day = data.get('day')
        
        if not guest_ids:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No guest IDs provided"}
            )
            
        if day not in ["1", "2"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Invalid day specified"}
            )
            
        guests = guests_db.read_all()
        updated_count = 0
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for guest in guests:
            if guest["ID"] in guest_ids:
                if day == "1":
                    guest["FoodCouponsDay1"] = "True"
                    guest["FoodCouponsDay1Date"] = current_time
                else:
                    guest["FoodCouponsDay2"] = "True"
                    guest["FoodCouponsDay2Date"] = current_time
                updated_count += 1
                
        if updated_count > 0:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity("Bulk", f"Admin {admin['user_id']} gave Day {day} food coupons to {updated_count} guests")
            
            return JSONResponse(
                content={"success": True, "message": f"Day {day} food coupons given to {updated_count} guests successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "No matching guests found"}
            )
    except Exception as e:
        logger.error(f"Error giving food coupons in bulk: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error giving food coupons: {str(e)}"}
        )

@router.get("/download_meal_plan/{guest_id}")
async def download_meal_plan(admin: Dict = Depends(get_current_admin), guest_id: str = FastAPIPath(...)):
    """Generate and download meal plan for a guest"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        # Create meal plan document
        meal_plan_content = create_meal_plan_document(guest)
        
        # Convert to bytes
        buffer = io.BytesIO()
        buffer.write(meal_plan_content.encode('utf-8'))
        buffer.seek(0)
        
        # Log this activity
        log_activity(guest_id, f"Admin {admin['user_id']} downloaded meal plan")
        
        return StreamingResponse(
            buffer,
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="MealPlan_{guest_id}_{guest.get("Name", "Guest").replace(" ", "_")}.txt"'
            }
        )

    except Exception as e:
        logger.error(f"Error downloading meal plan: {str(e)}")
        raise HTTPException(status_code=500, detail="Error downloading meal plan")

@router.post("/update_food_notes")
async def update_food_notes(request: Request, admin: Dict = Depends(get_current_admin)):
    """Update food notes for a guest"""
    try:
        data = await request.json()
        guest_id = data.get('guest_id')
        notes = data.get('notes', '')
        
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                guest["FoodNotes"] = notes
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity(guest_id, f"Admin {admin['user_id']} updated food notes")
            
            return JSONResponse(
                content={"success": True, "message": "Food notes updated successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
    except Exception as e:
        logger.error(f"Error updating food notes: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error updating food notes: {str(e)}"}
        )

@router.get("/report/export/food_list")
async def export_food_list(
    admin: Dict = Depends(get_current_admin),
    day: Optional[str] = None,
    status: Optional[str] = None,
    format: str = "csv"
):
    """Export food distribution list as CSV"""
    try:
        guests = guests_db.read_all()
        
        # Apply filters
        if day == "1" and status == "given":
            guests = [g for g in guests if g.get("FoodCouponsDay1") == "True"]
        elif day == "1" and status == "not_given":
            guests = [g for g in guests if g.get("FoodCouponsDay1") != "True"]
        elif day == "2" and status == "given":
            guests = [g for g in guests if g.get("FoodCouponsDay2") == "True"]
        elif day == "2" and status == "not_given":
            guests = [g for g in guests if g.get("FoodCouponsDay2") != "True"]
        elif status == "given":
            guests = [g for g in guests if g.get("FoodCouponsDay1") == "True" or g.get("FoodCouponsDay2") == "True"]
        elif status == "not_given":
            guests = [g for g in guests if g.get("FoodCouponsDay1") != "True" and g.get("FoodCouponsDay2") != "True"]
        
        if format.lower() == "csv":
            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "ID", "Name", "Role", "Phone", "Day 1 Status", "Day 1 Date", 
                "Day 2 Status", "Day 2 Date", "Food Notes"
            ])
            
            # Write data
            for guest in guests:
                writer.writerow([
                    guest.get("ID", ""),
                    guest.get("Name", ""),
                    guest.get("GuestRole", ""),
                    guest.get("Phone", ""),
                    "Given" if guest.get("FoodCouponsDay1") == "True" else "Not Given",
                    guest.get("FoodCouponsDay1Date", ""),
                    "Given" if guest.get("FoodCouponsDay2") == "True" else "Not Given",
                    guest.get("FoodCouponsDay2Date", ""),
                    guest.get("FoodNotes", "")
                ])
            
            # Return as downloadable CSV
            output.seek(0)
            filename = f"food_distribution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported export format")
    except Exception as e:
        logger.error(f"Error exporting food list: {str(e)}")
        raise HTTPException(status_code=500, detail="Error exporting food list")

# GIFT MANAGEMENT ROUTES

@router.post("/give_gift")
async def give_gift(request: Request, admin: Dict = Depends(get_current_admin), guest_id: str = Form(...)):
    """Mark gifts as given to guest with date tracking"""
    try:
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                if guest.get("GiftsGiven") == "True":
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "message": "Gifts have already been given to this guest"}
                    )
                
                guest["GiftsGiven"] = "True"
                guest["GiftGivenDate"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity(guest_id, f"Admin {admin['user_id']} marked gifts as given")
            
            return JSONResponse(
                content={"success": True, "message": "Gifts marked as given successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
    except Exception as e:
        logger.error(f"Error giving gifts: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error giving gifts: {str(e)}"}
        )

@router.post("/give_gifts_bulk")
async def give_gifts_bulk(request: Request, admin: Dict = Depends(get_current_admin)):
    """Give gifts to multiple guests"""
    try:
        data = await request.json()
        guest_ids = data.get('guest_ids', [])
        
        if not guest_ids:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No guest IDs provided"}
            )
            
        guests = guests_db.read_all()
        updated_count = 0
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for guest in guests:
            if guest["ID"] in guest_ids:
                guest["GiftsGiven"] = "True"
                guest["GiftGivenDate"] = current_time
                updated_count += 1
                
        if updated_count > 0:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity("Bulk", f"Admin {admin['user_id']} gave gifts to {updated_count} guests")
            
            return JSONResponse(
                content={"success": True, "message": f"Gifts given to {updated_count} guests successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "No matching guests found"}
            )
    except Exception as e:
        logger.error(f"Error giving gifts in bulk: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error giving gifts: {str(e)}"}
        )

@router.get("/download_gift_list/{guest_id}")
async def download_gift_list(admin: Dict = Depends(get_current_admin), guest_id: str = FastAPIPath(...)):
    """Generate and download gift list for a guest"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        # Create gift list document
        gift_list_content = create_gift_list_document(guest)
        
        # Convert to bytes
        buffer = io.BytesIO()
        buffer.write(gift_list_content.encode('utf-8'))
        buffer.seek(0)
        
        # Log this activity
        log_activity(guest_id, f"Admin {admin['user_id']} downloaded gift list")
        
        return StreamingResponse(
            buffer,
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="GiftList_{guest_id}_{guest.get("Name", "Guest").replace(" ", "_")}.txt"'
            }
        )

    except Exception as e:
        logger.error(f"Error downloading gift list: {str(e)}")
        raise HTTPException(status_code=500, detail="Error downloading gift list")

@router.post("/update_gift_notes")
async def update_gift_notes(request: Request, admin: Dict = Depends(get_current_admin)):
    """Update gift notes for a guest"""
    try:
        data = await request.json()
        guest_id = data.get('guest_id')
        notes = data.get('notes', '')
        
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                guest["GiftNotes"] = notes
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity(guest_id, f"Admin {admin['user_id']} updated gift notes")
            
            return JSONResponse(
                content={"success": True, "message": "Gift notes updated successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
    except Exception as e:
        logger.error(f"Error updating gift notes: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error updating gift notes: {str(e)}"}
        )

@router.get("/report/export/gift_list")
async def export_gift_list(
    admin: Dict = Depends(get_current_admin),
    status: Optional[str] = None,
    format: str = "csv"
):
    """Export gift distribution list as CSV"""
    try:
        guests = guests_db.read_all()
        
        # Apply filters
        if status == "given":
            guests = [g for g in guests if g.get("GiftsGiven") == "True"]
        elif status == "not_given":
            guests = [g for g in guests if g.get("GiftsGiven") != "True"]
        
        if format.lower() == "csv":
            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "ID", "Name", "Role", "Phone", "Gift Status", "Distribution Date", "Gift Notes"
            ])
            
            # Write data
            for guest in guests:
                writer.writerow([
                    guest.get("ID", ""),
                    guest.get("Name", ""),
                    guest.get("GuestRole", ""),
                    guest.get("Phone", ""),
                    "Given" if guest.get("GiftsGiven") == "True" else "Not Given",
                    guest.get("GiftGivenDate", ""),
                    guest.get("GiftNotes", "")
                ])
            
            # Return as downloadable CSV
            output.seek(0)
            filename = f"gift_distribution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported export format")
    except Exception as e:
        logger.error(f"Error exporting gift list: {str(e)}")
        raise HTTPException(status_code=500, detail="Error exporting gift list")

# UTILITY ROUTES

@router.get("/api/guest/{guest_id}")
async def get_guest_api(guest_id: str, admin: Dict = Depends(get_current_admin)):
    """Get guest information via API (for AJAX calls from frontend)"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if not guest:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
        
        return JSONResponse(
            content={"success": True, "guest": guest}
        )
    except Exception as e:
        logger.error(f"Error getting guest via API: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error getting guest information: {str(e)}"}
        )

@router.post("/update_guest_basic_info")
async def update_guest_basic_info(request: Request, admin: Dict = Depends(get_current_admin)):
    """Update guest basic information (for inline editing)"""
    try:
        data = await request.json()
        guest_id = data.get('guest_id')
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                guest["Name"] = name
                guest["Email"] = email
                guest["Phone"] = phone
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity(guest_id, f"Admin {admin['user_id']} updated basic information")
            
            return JSONResponse(
                content={"success": True, "message": "Basic information updated successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
    except Exception as e:
        logger.error(f"Error updating guest basic info: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error updating basic information: {str(e)}"}
        )


@router.get("/messages", response_class=HTMLResponse)
async def messages_management(request: Request, q: str = ""):
    trace_id = str(uuid.uuid4())
    logging.info(f"[{trace_id}] Admin accessed messages_management with search='{q}'")
    messages_path = config.get('DATABASE', 'MessagesCSV', fallback='./data/messages.csv')
    guests_path = config.get('DATABASE', 'CSVPath', fallback='./data/guests.csv')
    messages = []
    guests_map = {}

    # Read guest info for mapping
    try:
        with open(guests_path, newline='', encoding='utf-8') as gfile:
            for row in csv.DictReader(gfile):
                guests_map[row['ID']] = row
    except Exception as e:
        logging.error(f"[{trace_id}] Failed reading guests: {e}")

    # Read messages and join with guest info
    try:
        with open(messages_path, newline='', encoding='utf-8') as mfile:
            for msg in csv.DictReader(mfile):
                guest = guests_map.get(msg['guest_id'], {})
                # Search filter
                if q and all(
                    q.lower() not in (str(msg.get(f, "")).lower() + str(guest.get(f, "")).lower())
                    for f in ['message', 'content', 'Name', 'Phone']
                ):
                    continue
                message_text = msg.get('message') or msg.get('content', '')
                messages.append({
                    "id": msg.get('id'),
                    "guest_id": msg['guest_id'],
                    "name": guest.get('Name', 'Unknown'),
                    "phone": guest.get('Phone', ''),
                    "role": guest.get('GuestRole', ''),
                    "message": message_text,
                    "timestamp": msg.get('timestamp', ''),
                    "response": msg.get('response', ''),
                    "response_timestamp": msg.get('response_timestamp', '')
                })
    except Exception as e:
        logging.error(f"[{trace_id}] Failed reading messages: {e}")

    logging.info(f"[{trace_id}] Loaded {len(messages)} messages for admin display.")
    return templates.TemplateResponse(
        "admin/messages_management.html",
        {"request": request, "messages": messages, "search_query": q, "trace_id": trace_id}
    )

@router.post("/respond_message")
async def respond_message(request: Request, admin: Dict = Depends(get_current_admin), message_id: str = Form(...), response: str = Form(...)):
    """Store admin response to a guest message"""
    try:
        messages_path = config.get('DATABASE', 'MessagesCSV', fallback='./data/messages.csv')
        rows = []
        fieldnames = []
        if os.path.exists(messages_path):
            with open(messages_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    if row.get('id') == message_id:
                        row['response'] = response
                        row['response_timestamp'] = datetime.now().isoformat()
                        row['read'] = 'True'
                    rows.append(row)

        if rows and fieldnames:
            with open(messages_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        return RedirectResponse(url="/admin/messages", status_code=303)
    except Exception as e:
        logging.error(f"Error responding to message: {e}")
        raise HTTPException(status_code=500, detail="Error responding to message")

# HELPER FUNCTIONS

def create_simple_badge(guest: Dict) -> Image.Image:
    """Create a professional badge design for BDCON 2025"""
    try:
        # Create a badge with BDCON 2025 theme
        width, height = 1000, 700  # Increased size for better quality
        
        # Background with gradient effect
        badge = Image.new('RGB', (width, height), '#ffffff')
        draw = ImageDraw.Draw(badge)
        
        # Draw blue header section
        header_height = 150
        draw.rectangle([(0, 0), (width, header_height)], fill='#1a237e')
        
        # Conference branding
        try:
            # Main title
            draw.text((width//2, 30), "BDCON 2025", fill='white', anchor="mm", font_size=36)
            draw.text((width//2, 70), "14th Annual Conference", fill='white', anchor="mm", font_size=20)
            draw.text((width//2, 100), "Bengal Diabetes Foundation", fill='white', anchor="mm", font_size=18)
            draw.text((width//2, 125), "June 14-15, 2025", fill='#ffeb3b', anchor="mm", font_size=16)
        except:
            # Fallback without font_size parameter
            draw.text((50, 30), "BDCON 2025 - 14th Annual Conference", fill='white')
            draw.text((50, 60), "Bengal Diabetes Foundation", fill='white')
            draw.text((50, 90), "June 14-15, 2025", fill='#ffeb3b')
        
        # Guest information section
        info_start_y = header_height + 40
        
        # Guest ID with background
        id_bg_height = 50
        draw.rectangle([(50, info_start_y), (width-50, info_start_y + id_bg_height)], 
                      fill='#f5f5f5', outline='#1a237e', width=2)
        draw.text((width//2, info_start_y + 25), f"ID: {guest['ID']}", 
                 fill='#1a237e', anchor="mm")
        
        # Guest name - prominent display
        name_y = info_start_y + 80
        name = guest.get('Name', 'N/A')
        if name and name != 'N/A':
            # Add "Dr." prefix for medical professionals if not already present
            if guest.get('GuestRole') in ['Delegates', 'Faculty', 'OrgBatch'] and not name.upper().startswith('DR.'):
                name = f"Dr. {name}"
        
        # Name with background
        name_bg_height = 60
        draw.rectangle([(50, name_y), (width-50, name_y + name_bg_height)], 
                      fill='#e3f2fd', outline='#1976d2', width=2)
        draw.text((width//2, name_y + 30), name, fill='#1976d2', anchor="mm")
        
        # Role badge
        role = guest.get('GuestRole', 'Guest')
        role_colors = {
            'Delegates': '#28a745',
            'Faculty': '#007bff', 
            'Sponsors': '#ffc107',
            'Staff': '#6c757d',
            'OrgBatch': '#dc3545',
            'Roots': '#17a2b8',
            'Event': '#fd7e14'
        }
        role_color = role_colors.get(role, '#6c757d')
        
        role_y = name_y + 80
        role_width = 300
        role_height = 40
        role_x = (width - role_width) // 2
        
        draw.rectangle([(role_x, role_y), (role_x + role_width, role_y + role_height)], 
                      fill=role_color)
        draw.text((width//2, role_y + 20), role.upper(), fill='white', anchor="mm")
        
        # Additional information
        extra_info_y = role_y + 60
        info_items = []
        
        if guest.get('Batch'):
            info_items.append(f"Batch: {guest['Batch']}")
        if guest.get('CompanyName'):
            info_items.append(f"Company: {guest['CompanyName']}")
        if guest.get('PaymentAmount') and float(guest.get('PaymentAmount', 0)) > 0:
            info_items.append(f"Amount: ₹{guest['PaymentAmount']}")
        
        for i, info in enumerate(info_items):
            draw.text((70, extra_info_y + (i * 25)), info, fill='#424242')
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2
        )
        qr.add_data(f"GUEST:{guest['ID']}")
        qr.make()
        qr_img = qr.make_image(fill_color="#1a237e", back_color="white")
        
        # Resize and paste QR code
        qr_size = 180
        qr_resized = qr_img.resize((qr_size, qr_size))
        qr_x = width - qr_size - 50
        qr_y = info_start_y + 60
        badge.paste(qr_resized, (qr_x, qr_y))
        
        # QR code label
        draw.text((qr_x + qr_size//2, qr_y + qr_size + 15), "Scan for Check-in", 
                 fill='#666666', anchor="mm")
        
        # Footer information
        footer_y = height - 100
        draw.rectangle([(0, footer_y), (width, height)], fill='#f8f9fa')
        
        footer_items = [
            "Venue: ITC Fortune Park, Pushpanjali, Durgapur",
            "Under the Banner of Bengal Diabetes Foundation",
            "Bridging the Gaps in Diabetes Management"
        ]
        
        for i, item in enumerate(footer_items):
            draw.text((width//2, footer_y + 20 + (i * 20)), item, 
                     fill='#666666', anchor="mm")
        
        # Decorative elements
        # Top border
        draw.rectangle([(0, header_height), (width, header_height + 5)], fill='#ffeb3b')
        
        # Side borders
        draw.rectangle([(0, 0), (5, height)], fill='#1a237e')
        draw.rectangle([(width-5, 0), (width, height)], fill='#1a237e')
        
        return badge
        
    except Exception as e:
        logger.error(f"Error creating badge: {str(e)}")
        # Return a simple placeholder image
        placeholder = Image.new('RGB', (1000, 700), 'lightgray')
        draw = ImageDraw.Draw(placeholder)
        draw.text((100, 350), f"Badge for {guest['ID']}", fill='black')
        draw.text((100, 380), f"Name: {guest.get('Name', 'N/A')}", fill='black')
        draw.text((100, 410), f"Role: {guest.get('GuestRole', 'Guest')}", fill='black')
        return placeholder

def create_itinerary_document(guest: Dict) -> str:
    """Create itinerary document content"""
    try:
        content = f"""
===========================================
BDCON 2025 - JOURNEY ITINERARY
===========================================

Guest Information:
- ID: {guest['ID']}
- Name: {guest.get('Name', 'N/A')}
- Role: {guest.get('GuestRole', 'N/A')}
- Phone: {guest.get('Phone', 'N/A')}
- Email: {guest.get('Email', 'N/A')}

Conference Details:
- Event: 14th Annual Conference - BDCON 2025
- Dates: June 14-15, 2025
- Venue: ITC Fortune Park, Pushpanjali, Durgapur
- Organizer: Bengal Diabetes Foundation

Journey Status:
- Details Updated: {'Yes' if guest.get('JourneyDetailsUpdated') == 'True' else 'No'}
- Journey Completed: {'Yes' if guest.get('JourneyCompleted') == 'True' else 'No'}

Contact Information:
- Conference Helpline: +91 84800 02958
- Email: info@bdcon2025.org

Important Notes:
1. Please carry this itinerary and your registration confirmation
2. Report to the registration desk upon arrival
3. Conference materials will be provided at the venue
4. For any journey-related queries, contact the organizing committee

===========================================
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
===========================================
        """
        return content.strip()
        
    except Exception as e:
        logger.error(f"Error creating itinerary: {str(e)}")
        return f"Error generating itinerary for guest {guest.get('ID', 'Unknown')}"

def create_meal_plan_document(guest: Dict) -> str:
    """Create meal plan document content"""
    try:
        content = f"""
===========================================
BDCON 2025 - MEAL PLAN & FOOD COUPONS
===========================================

Guest Information:
- ID: {guest['ID']}
- Name: {guest.get('Name', 'N/A')}
- Role: {guest.get('GuestRole', 'N/A')}
- Phone: {guest.get('Phone', 'N/A')}

Food Coupon Status:
- Day 1 Coupons: {'Received' if guest.get('FoodCouponsDay1') == 'True' else 'Not Received'}
- Day 2 Coupons: {'Received' if guest.get('FoodCouponsDay2') == 'True' else 'Not Received'}

Conference Meal Schedule:

DAY 1 - June 14, 2025
======================
09:00 AM - Welcome Tea/Coffee
12:30 PM - Lunch Break
03:30 PM - Afternoon Tea/Coffee
07:00 PM - Welcome Dinner

DAY 2 - June 15, 2025
======================
09:00 AM - Morning Tea/Coffee
12:30 PM - Lunch Break
03:30 PM - Afternoon Tea/Coffee
06:30 PM - Farewell Dinner

Dietary Information:
- Vegetarian and Non-vegetarian options available
- Special dietary requirements can be accommodated
- Please inform the organizing committee for any allergies

Venue:
- Main Conference Hall - ITC Fortune Park
- All meals will be served in the designated dining areas

Food Notes:
{guest.get('FoodNotes', 'No special dietary requirements noted')}

Contact for Food-related Queries:
- Food Coordinator: +91 84800 02958
- Email: food@bdcon2025.org

Important Notes:
1. Please present your food coupons at meal times
2. Food coupons are non-transferable
3. Outside food is not permitted in conference areas
4. Meal timings are subject to minor changes

===========================================
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
===========================================
        """
        return content.strip()
        
    except Exception as e:
        logger.error(f"Error creating meal plan: {str(e)}")
        return f"Error generating meal plan for guest {guest.get('ID', 'Unknown')}"

def create_gift_list_document(guest: Dict) -> str:
    """Create gift list document content"""
    try:
        # Determine gifts based on guest role
        role = guest.get('GuestRole', 'Guest')
        
        role_specific_gifts = {
            'Delegates': [
                'Conference Kit with Stationery',
                'BDCON 2025 T-Shirt',
                'Conference Proceedings Book',
                'Certificate of Participation',
                'Conference Bag',
                'Pen & Notepad Set'
            ],
            'Faculty': [
                'Faculty Kit with Premium Items',
                'BDCON 2025 T-Shirt',
                'Conference Proceedings Book',
                'Certificate of Appreciation',
                'Premium Conference Bag',
                'Faculty Recognition Award'
            ],
            'Sponsors': [
                'Sponsor Recognition Kit',
                'BDCON 2025 T-Shirt',
                'Conference Proceedings Book',
                'Sponsor Certificate',
                'Premium Gift Set',
                'Conference Memento'
            ],
            'OrgBatch': [
                'Organizing Committee Special Kit',
                'BDCON 2025 T-Shirt',
                'Conference Proceedings Book',
                'Organizing Committee Certificate',
                'Special Recognition Award',
                'Committee Memento'
            ],
            'Staff': [
                'Staff Appreciation Kit',
                'BDCON 2025 T-Shirt',
                'Certificate of Service',
                'Staff Badge',
                'Conference Bag'
            ]
        }
        
        gifts = role_specific_gifts.get(role, [
            'Conference Kit',
            'BDCON 2025 T-Shirt',
            'Certificate of Participation'
        ])
        
        content = f"""
===========================================
BDCON 2025 - CONFERENCE GIFT LIST
===========================================

Guest Information:
- ID: {guest['ID']}
- Name: {guest.get('Name', 'N/A')}
- Role: {role}

Gift Status: {'Received' if guest.get('GiftsGiven') == 'True' else 'Not Received'}

Conference Gift Items:
"""
        
        for i, gift in enumerate(gifts, 1):
            content += f"{i:2d}. {gift}\n"
        
        content += f"""

Special Notes:
- All items are complimentary for conference participants
- Gift collection is available at the registration desk
- Please present your conference badge for verification
- Gifts are non-transferable and subject to availability

Collection Details:
- Venue: Registration Desk, ITC Fortune Park
- Timing: During conference registration hours
- Contact: Registration Team (+91 84800 02958)

Conference Details:
- Event: 14th Annual Conference - BDCON 2025
- Dates: June 14-15, 2025
- Theme: Bridging the Gaps in Diabetes Management
- Organizer: Bengal Diabetes Foundation

===========================================
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
===========================================
        """
        return content.strip()
        
    except Exception as e:
        logger.error(f"Error creating gift list: {str(e)}")
        return f"Error generating gift list for guest {guest.get('ID', 'Unknown')}"

# FIELD INITIALIZATION FUNCTIONS

def ensure_badge_fields():
    """Ensure badge-related fields exist in CSV"""
    try:
        guests = guests_db.read_all()
        if not guests:
            return
            
        # Check if badge fields exist
        first_guest = guests[0]
        fields_to_add = []
        
        if "BadgePrinted" not in first_guest:
            fields_to_add.append("BadgePrinted")
        if "BadgeGiven" not in first_guest:
            fields_to_add.append("BadgeGiven")
            
        if fields_to_add:
            # Add missing fields to all guests
            for guest in guests:
                for field in fields_to_add:
                    guest[field] = "False"
            
            # Write back to CSV
            guests_db.write_all(guests)
            logger.info(f"Added badge fields to CSV: {fields_to_add}")
            
    except Exception as e:
        logger.error(f"Error ensuring badge fields: {str(e)}")

def ensure_journey_detail_fields():
    """Ensure all detailed journey fields exist in CSV"""
    try:
        guests = guests_db.read_all()
        if not guests:
            return
            
        # Check if journey detail fields exist
        first_guest = guests[0]
        fields_to_add = []
        
        # All journey fields including detailed ones
        journey_fields = [
            "JourneyDetailsUpdated", "JourneyCompleted", "LastJourneyUpdate",
            "InwardJourneyDate", "InwardJourneyFrom", "InwardJourneyTo", 
            "InwardJourneyDetails", "InwardPickupRequired", "InwardJourneyRemarks",
            "OutwardJourneyDate", "OutwardJourneyFrom", "OutwardJourneyTo",
            "OutwardJourneyDetails", "OutwardDropRequired", "OutwardJourneyRemarks"
        ]
        
        for field in journey_fields:
            if field not in first_guest:
                fields_to_add.append(field)
            
        if fields_to_add:
            # Add missing fields to all guests
            for guest in guests:
                for field in fields_to_add:
                    if field.endswith("Required") or field in ["JourneyDetailsUpdated", "JourneyCompleted"]:
                        guest[field] = "False"
                    else:
                        guest[field] = ""
            
            # Write back to CSV
            guests_db.write_all(guests)
            logger.info(f"Added detailed journey fields to CSV: {fields_to_add}")
            
    except Exception as e:
        logger.error(f"Error ensuring journey detail fields: {str(e)}")

def ensure_enhanced_food_fields():
    """Ensure all food-related fields exist in CSV including dates and notes"""
    try:
        guests = guests_db.read_all()
        if not guests:
            return
            
        # Check if food fields exist
        first_guest = guests[0]
        fields_to_add = []
        
        food_fields = [
            "FoodCouponsDay1", "FoodCouponsDay2", 
            "FoodCouponsDay1Date", "FoodCouponsDay2Date", 
            "FoodNotes"
        ]
        
        for field in food_fields:
            if field not in first_guest:
                fields_to_add.append(field)
            
        if fields_to_add:
            # Add missing fields to all guests
            for guest in guests:
                for field in fields_to_add:
                    if field.startswith("FoodCouponsDay") and not field.endswith("Date"):
                        guest[field] = "False"
                    else:
                        guest[field] = ""
            
            # Write back to CSV
            guests_db.write_all(guests)
            logger.info(f"Added enhanced food fields to CSV: {fields_to_add}")
            
    except Exception as e:
        logger.error(f"Error ensuring enhanced food fields: {str(e)}")

def ensure_enhanced_gift_fields():
    """Ensure all gift-related fields exist in CSV including notes and dates"""
    try:
        guests = guests_db.read_all()
        if not guests:
            return
            
        # Check if gift fields exist
        first_guest = guests[0]
        fields_to_add = []
        
        gift_fields = [
            "GiftsGiven", "GiftGivenDate", "GiftNotes"
        ]
        
        for field in gift_fields:
            if field not in first_guest:
                fields_to_add.append(field)
            
        if fields_to_add:
            # Add missing fields to all guests
            for guest in guests:
                for field in fields_to_add:
                    if field == "GiftsGiven":
                        guest[field] = "False"
                    else:
                        guest[field] = ""
            
            # Write back to CSV
            guests_db.write_all(guests)
            logger.info(f"Added enhanced gift fields to CSV: {fields_to_add}")
            
    except Exception as e:
        logger.error(f"Error ensuring enhanced gift fields: {str(e)}")

# Initialize all fields when the module is loaded
ensure_badge_fields()
ensure_journey_detail_fields()
ensure_enhanced_food_fields()
ensure_enhanced_gift_fields()