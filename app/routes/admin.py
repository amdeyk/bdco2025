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
from fastapi.responses import StreamingResponse
import csv
import io
from app.utils.changelog import ChangelogManager
import random

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
            
        # Registration trends over time
        registration_dates = defaultdict(int)
        for guest in guests:
            try:
                if guest.get("RegistrationDate"):
                    date = datetime.fromisoformat(guest.get("RegistrationDate")).strftime('%Y-%m-%d')
                    registration_dates[date] += 1
            except (ValueError, TypeError):
                continue
        
        dates = sorted(registration_dates.keys())
        
        # FIX: Convert registration_trend to a dictionary with lists, not methods
        registration_trend = {
            "labels": dates[-30:] if len(dates) > 30 else dates,
            "values": [registration_dates[date] for date in (dates[-30:] if len(dates) > 30 else dates)]
        }
        
        # NEW: Get journey data
        journey_data = []
        journey_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "journey.csv")
        if os.path.exists(journey_csv):
            with open(journey_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                journey_data = list(reader)
        
        # NEW: Journey statistics
        total_journeys = len(journey_data)
        pickup_needed = sum(1 for j in journey_data if j.get("pickup_required") == "True")
        drop_needed = sum(1 for j in journey_data if j.get("drop_required") == "True")
        
        # NEW: Get presentation data
        presentations = []
        presentations_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "presentations.csv")
        if os.path.exists(presentations_csv):
            with open(presentations_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                presentations = list(reader)
        
        # NEW: Presentation statistics
        total_presentations = len(presentations)
        presentation_types = defaultdict(int)
        for p in presentations:
            p_type = p.get("file_type", "unknown")
            presentation_types[p_type] += 1
        
        # FIX: Convert dict.keys() and dict.values() to lists so they're JSON serializable
        role_distr_labels = list(role_distribution.keys())
        role_distr_values = list(role_distribution.values())
        
        payment_status_labels = list(payment_status.keys())
        payment_status_values = list(payment_status.values())
        
        presentation_type_labels = list(presentation_types.keys())
        presentation_type_values = list(presentation_types.values())
        
        # NEW: Attendance over time (sample data)
        last_7_dates = dates[-7:] if dates else []
        attendance_trend = {
            "labels": last_7_dates,
            "values": [random.randint(0, total_guests) for _ in last_7_dates]
        }
        
        # NEW: Faculty-specific statistics
        faculty_count = sum(1 for g in guests if g.get("GuestRole") == "Faculty")
        faculty_data = []
        faculty_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "faculty.csv")
        if os.path.exists(faculty_csv):
            with open(faculty_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                faculty_data = list(reader)
        
        faculty_with_presentations = set(p.get("guest_id") for p in presentations)
        faculty_with_accommodations = sum(1 for f in faculty_data if "accommodation_required" in f and f["accommodation_required"] == "True")
        
        # NEW: Message statistics
        messages = []
        messages_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "messages.csv")
        if os.path.exists(messages_csv):
            with open(messages_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                messages = list(reader)
        
        unread_messages = sum(1 for m in messages if m.get("read") == "False")
        
        # NEW: Recent changelog entries
        # Use ChangelogManager if it exists, otherwise provide empty data
        recent_changes = []
        try:
            from app.utils.changelog import ChangelogManager
            changelog_manager = ChangelogManager()
            recent_changes = changelog_manager.get_entries(limit=5)
        except (ImportError, AttributeError):
            # If ChangelogManager doesn't exist yet, just return empty list
            pass
        
        return templates.TemplateResponse(
            "admin/report.html",
            {
                "request": request,
                "admin": admin,
                "total_guests": total_guests,
                "checked_in": checked_in,
                "kit_received": kit_received,
                "badges_printed": badges_printed,
                "payment_status": payment_status,
                "payment_status_labels": payment_status_labels,
                "payment_status_values": payment_status_values,
                "total_collected": total_collected,
                "role_distribution": role_distribution,
                "role_distribution_labels": role_distr_labels,
                "role_distribution_values": role_distr_values,
                # NEW data for enhanced reporting
                "total_journeys": total_journeys,
                "pickup_needed": pickup_needed,
                "drop_needed": drop_needed,
                "total_presentations": total_presentations,
                "presentation_types": presentation_types,
                "presentation_type_labels": presentation_type_labels,
                "presentation_type_values": presentation_type_values,
                "registration_dates": registration_dates,
                "registration_trend": registration_trend,
                "attendance_trend": attendance_trend,
                "faculty_stats": {
                    "total": faculty_count,
                    "with_presentations": len(faculty_with_presentations),
                    "with_accommodations": faculty_with_accommodations
                },
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