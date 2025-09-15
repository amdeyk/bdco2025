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
from app.services.journey_sync import create_journey_service
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
import pandas as pd
from app.models.guest import Guest

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
guests_db = CSVDatabase(
    config.get('DATABASE', 'CSVPath'),
    config.get('DATABASE', 'BackupDir')
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
        # Count delegates separately for dashboard stats
        delegate_count = sum(1 for g in guests if g.get("GuestRole") == "Delegate")

        # Attendance counts Faculty or Delegate guests who checked in or received a meal coupon
        attendance_count = sum(
            1
            for g in guests
            if g.get("GuestRole") in ["Faculty", "Delegate"]
            and (
                g.get("DailyAttendance") == "True"
                or g.get("FoodCouponsDay1") == "True"
                or g.get("FoodCouponsDay2") == "True"
            )
        )
        
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
            "delegate_count": delegate_count,
            "faculty_count": faculty_count,
            "attendance_count": attendance_count,
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

@router.get("/reset_database", response_class=HTMLResponse)
async def reset_database_page(request: Request, admin: Dict = Depends(get_current_admin)):
    """Reset database confirmation page"""
    try:
        return templates.TemplateResponse(
            "admin/reset_database.html",
            {
                "request": request,
                "admin": admin,
                "active_page": "reset_database"
            }
        )
    except Exception as e:
        logger.error(f"Error loading reset database page: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading reset database page",
                "error_details": str(e) if config.getboolean('DEFAULT', 'Debug', fallback=False) else None
            }
        )


@router.post("/reset_database")
async def reset_database(
    request: Request,
    admin: Dict = Depends(get_current_admin),
    confirmation_phrase: str = Form(...),
    admin_password: str = Form(...)
):
    """Reset the entire database with password protection"""
    try:
        if admin_password != config.get('DEFAULT', 'AdminPassword'):
            return templates.TemplateResponse(
                "admin/reset_database.html",
                {
                    "request": request,
                    "admin": admin,
                    "error": "Incorrect admin password",
                    "active_page": "reset_database"
                }
            )

        if confirmation_phrase != "I_DO_UNDERSTAND@@RESET":
            return templates.TemplateResponse(
                "admin/reset_database.html",
                {
                    "request": request,
                    "admin": admin,
                    "error": "Incorrect confirmation phrase",
                    "active_page": "reset_database"
                }
            )

        reset_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"pre_reset_backup_{reset_timestamp}.csv"
        backup_path = guests_db.create_backup(backup_filename)

        if not backup_path:
            return templates.TemplateResponse(
                "admin/reset_database.html",
                {
                    "request": request,
                    "admin": admin,
                    "error": "Failed to create backup. Reset aborted for safety.",
                    "active_page": "reset_database"
                }
            )

        reset_main_database()
        reset_related_databases()

        log_activity("System", f"Admin {admin['user_id']} performed complete database reset. Backup: {backup_filename}")

        return templates.TemplateResponse(
            "admin/reset_database.html",
            {
                "request": request,
                "admin": admin,
                "success": f"Database successfully reset. Backup created: {backup_filename}",
                "backup_file": backup_filename,
                "active_page": "reset_database"
            }
        )

    except Exception as e:
        logger.error(f"Error resetting database: {str(e)}")
        return templates.TemplateResponse(
            "admin/reset_database.html",
            {
                "request": request,
                "admin": admin,
                "error": f"Error during database reset: {str(e)}",
                "active_page": "reset_database"
            }
        )


def reset_main_database():
    """Reset the main guests database to initial state"""
    try:
        initial_headers = [
            "ID", "Name", "Email", "Phone", "GuestRole", "RegistrationDate",
            "DailyAttendance", "CheckInTime", "BadgePrinted", "BadgeGiven",
            "BadgePrintedDate", "BadgeGivenDate", "KitReceived", "KitReceivedDate",
            "GiftsGiven", "GiftGivenDate", "GiftNotes", "FoodCouponsDay1",
            "FoodCouponsDay2", "FoodCouponsDay1Date", "FoodCouponsDay2Date",
            "FoodNotes", "PaymentStatus", "PaymentAmount", "PaymentDate",
            "PaymentMethod", "JourneyDetailsUpdated", "JourneyCompleted",
            "LastJourneyUpdate", "Availability", "InwardJourneyDate", "InwardJourneyFrom",
            "InwardJourneyTo", "InwardJourneyDetails", "InwardPickupRequired",
            "InwardJourneyRemarks", "OutwardJourneyDate", "OutwardJourneyFrom",
            "OutwardJourneyTo", "OutwardJourneyDetails", "OutwardDropRequired",
            "OutwardJourneyRemarks", "Organization", "KMCNumber", "Batch", "CompanyName"
        ]

        csv_path = config.get('DATABASE', 'CSVPath')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(initial_headers)

        logger.info("Main database reset successfully")

    except Exception as e:
        logger.error(f"Error resetting main database: {str(e)}")
        raise


def reset_related_databases():
    """Reset all related CSV databases"""
    try:
        data_dir = os.path.dirname(config.get('DATABASE', 'CSVPath'))

        journey_csv = os.path.join(data_dir, "journey.csv")
        journey_headers = [
            "guest_id", "inward_date", "inward_origin", "inward_destination",
            "inward_transport_details", "pickup_required", "inward_remarks",
            "outward_date", "outward_origin", "outward_destination",
            "outward_transport_details", "drop_required", "outward_remarks",
            "updated_at", "created_at"
        ]
        create_empty_csv(journey_csv, journey_headers)

        presentations_csv = os.path.join(data_dir, "presentations.csv")
        presentation_headers = [
            "id",
            "guest_id",
            "title",
            "description",
            "file_path",
            "file_type",
            "upload_date",
            "selected_status",
            "marks_allotted",
            "remarks_by",
            "approval_date",
        ]
        create_empty_csv(presentations_csv, presentation_headers)

        faculty_csv = os.path.join(data_dir, "faculty.csv")
        faculty_headers = [
            "guest_id", "designation", "specialization", "experience_years",
            "accommodation_required", "dietary_requirements", "special_requests",
            "presentation_title", "presentation_duration", "av_requirements"
        ]
        create_empty_csv(faculty_csv, faculty_headers)

        messages_csv = os.path.join(data_dir, "messages.csv")
        message_headers = [
            "id", "guest_id", "message", "timestamp", "read",
            "response", "response_timestamp"
        ]
        create_empty_csv(messages_csv, message_headers)

        changelog_csv = os.path.join(data_dir, "changelog.csv")
        changelog_headers = [
            "id", "title", "description", "author", "timestamp", "changes"
        ]
        create_empty_csv(changelog_csv, changelog_headers)

        logger.info("All related databases reset successfully")

    except Exception as e:
        logger.error(f"Error resetting related databases: {str(e)}")
        raise


def create_empty_csv(file_path: str, headers: list):
    """Create an empty CSV file with specified headers"""
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
    except Exception as e:
        logger.error(f"Error creating empty CSV {file_path}: {str(e)}")
        raise


def resolve_presentation_filename(row: Dict) -> str:
    """Find the correct filename for a presentation record."""
    presentations_dir = os.path.join(
        config.get('PATHS', 'StaticDir'), 'uploads', 'presentations'
    )
    candidates = [
        row.get('file_path'),
        row.get('file_name'),
        row.get('file_type'),
        row.get('title'),
    ]
    for cand in candidates:
        if not cand:
            continue
        name = os.path.basename(cand).strip()
        if name and os.path.exists(os.path.join(presentations_dir, name)):
            return name
    return ''


@router.get("/api/database-stats")
async def get_database_stats(admin: Dict = Depends(get_current_admin)):
    """Get current database statistics for reset confirmation"""
    try:
        guests = guests_db.read_all()

        data_dir = os.path.dirname(config.get('DATABASE', 'CSVPath'))

        journey_count = 0
        journey_csv = os.path.join(data_dir, "journey.csv")
        if os.path.exists(journey_csv):
            with open(journey_csv, 'r', newline='', encoding='utf-8') as f:
                journey_count = len(list(csv.DictReader(f)))

        presentations_count = 0
        presentations_csv = os.path.join(data_dir, "presentations.csv")
        if os.path.exists(presentations_csv):
            with open(presentations_csv, 'r', newline='', encoding='utf-8') as f:
                presentations_count = len(list(csv.DictReader(f)))

        messages_count = 0
        messages_csv = os.path.join(data_dir, "messages.csv")
        if os.path.exists(messages_csv):
            with open(messages_csv, 'r', newline='', encoding='utf-8') as f:
                messages_count = len(list(csv.DictReader(f)))

        return JSONResponse(content={
            "success": True,
            "stats": {
                "total_guests": len(guests),
                "checked_in": sum(1 for g in guests if g.get("DailyAttendance") == "True"),
                "badges_printed": sum(1 for g in guests if g.get("BadgePrinted") == "True"),
                "journeys": journey_count,
                "presentations": presentations_count,
                "messages": messages_count
            }
        })

    except Exception as e:
        logger.error(f"Error getting database stats: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error getting stats: {str(e)}"}
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

@router.get("/logout")
async def admin_logout(request: Request):
    """Admin logout route"""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_id")
    log_activity("Admin", "Admin logged out")
    return response

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
                "ID", "Name", "Email", "Phone", "KMC Number", "Role", "Registration Date", "Availability",
                "Check-in Status", "Kit Status", "Badge Status", "Payment Status", "Amount"
            ])
            
            # Write data
            for guest in guests:
                writer.writerow([
                    guest.get("ID", ""),
                    guest.get("Name", ""),
                    guest.get("Email", ""),
                    guest.get("Phone", ""),
                    guest.get("KMCNumber", ""),
                    guest.get("GuestRole", ""),
                    guest.get("RegistrationDate", ""),
                    guest.get("Availability", "Not Specified"),
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
                        "KMC Number": guest.get("KMCNumber", ""),
                        "Role": guest.get("GuestRole", ""),
                        "Registration Date": guest.get("RegistrationDate", ""),
                        "Availability": guest.get("Availability", "Not Specified"),
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

@router.get("/report/export/faculty")
async def export_faculty_list(
    admin: Dict = Depends(get_current_admin),
    format: str = "csv"
):
    """Export faculty list as CSV or Excel"""
    try:
        guests = guests_db.read_all()

        # Filter only faculty members
        faculty = [g for g in guests if g.get("GuestRole") == "Faculty"]

        if format.lower() == "csv":
            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow([
                "ID", "Name", "Email", "Phone", "Designation", "Institution",
                "Registration Date", "Check-in Status", "Badge Status",
                "Kit Status", "Presentations Count", "Journey Status"
            ])

            # Write data
            for member in faculty:
                writer.writerow([
                    member.get("ID", ""),
                    member.get("Name", ""),
                    member.get("Email", ""),
                    member.get("Phone", ""),
                    member.get("faculty_designation", "N/A"),
                    member.get("faculty_institution", "N/A"),
                    member.get("RegistrationDate", ""),
                    "Checked In" if member.get("DailyAttendance") == "True" else "Not Checked In",
                    "Printed" if member.get("BadgePrinted") == "True" else "Not Printed",
                    "Received" if member.get("KitReceived") == "True" else "Not Received",
                    member.get("presentation_count", "0"),
                    "Updated" if member.get("JourneyDetailsUpdated") == "True" else "Pending"
                ])

            # Return as downloadable CSV
            output.seek(0)
            filename = f"faculty_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
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
                for member in faculty:
                    data.append({
                        "ID": member.get("ID", ""),
                        "Name": member.get("Name", ""),
                        "Email": member.get("Email", ""),
                        "Phone": member.get("Phone", ""),
                        "Designation": member.get("faculty_designation", "N/A"),
                        "Institution": member.get("faculty_institution", "N/A"),
                        "Registration Date": member.get("RegistrationDate", ""),
                        "Check-in Status": "Checked In" if member.get("DailyAttendance") == "True" else "Not Checked In",
                        "Badge Status": "Printed" if member.get("BadgePrinted") == "True" else "Not Printed",
                        "Kit Status": "Received" if member.get("KitReceived") == "True" else "Not Received",
                        "Presentations Count": member.get("presentation_count", "0"),
                        "Journey Status": "Updated" if member.get("JourneyDetailsUpdated") == "True" else "Pending"
                    })

                df = pd.DataFrame(data)

                # Create Excel in memory
                output = io_excel.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name="Faculty")

                # Return as downloadable Excel
                output.seek(0)
                filename = f"faculty_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                return StreamingResponse(
                    iter([output.getvalue()]),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            except ImportError:
                # Fall back to CSV if pandas/openpyxl not available
                return await export_faculty_list(admin, format="csv")

        else:
            raise HTTPException(status_code=400, detail="Unsupported export format")
    except Exception as e:
        logger.error(f"Error exporting faculty list: {str(e)}")
        raise HTTPException(status_code=500, detail="Error exporting faculty list")

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

def get_faculty_details(faculty_list):
    """Enhance faculty list with detailed information from faculty.csv"""
    try:
        faculty_data = []
        faculty_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "faculty.csv")
        if os.path.exists(faculty_csv):
            with open(faculty_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                faculty_data = list(reader)

        # Map faculty data to guests
        faculty_map = {f.get("guest_id"): f for f in faculty_data}

        for guest in faculty_list:
            faculty_info = faculty_map.get(guest.get("ID"))
            if faculty_info:
                guest["faculty_designation"] = faculty_info.get("designation", "N/A")
                guest["faculty_institution"] = faculty_info.get("institution", "N/A")
                guest["faculty_specialization"] = faculty_info.get("specialization", "N/A")
                guest["faculty_experience_years"] = faculty_info.get("experience_years", "N/A")
                guest["faculty_accommodation_required"] = faculty_info.get("accommodation_required", "False")
            else:
                guest["faculty_designation"] = "N/A"
                guest["faculty_institution"] = "N/A"
                guest["faculty_specialization"] = "N/A"
                guest["faculty_experience_years"] = "N/A"
                guest["faculty_accommodation_required"] = "False"

        return faculty_list
    except Exception as e:
        logger.error(f"Error enhancing faculty details: {str(e)}")
        return faculty_list


@router.get("/report/faculty", response_class=HTMLResponse)
async def faculty_report(request: Request, admin: Dict = Depends(get_current_admin)):
    """Detailed faculty report"""
    try:
        guests = [g for g in guests_db.read_all() if g.get("GuestRole") == "Faculty"]
        guests = get_faculty_details(guests)
        
        
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

        # Add presentation count to each faculty member
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
                p['guest_phone'] = g.get('Phone', '')

            # Backwards compatible filename resolution
            file_name = resolve_presentation_filename(p)
            if file_name:
                p['file_url'] = f"/admin/download_presentation/{file_name}"
            else:
                p['file_url'] = ''

            # Normalize title field for old records
            if 'title' not in p and p.get('file_name'):
                p['title'] = p.get('file_name')

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

@router.get("/report/export/presentations")
async def export_presentations_report(admin: Dict = Depends(get_current_admin)):
    """Export presentations report as CSV"""
    try:
        presentations_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), 'presentations.csv')
        presentations = []
        if os.path.exists(presentations_csv):
            with open(presentations_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                presentations = list(reader)

        guests = guests_db.read_all()
        guest_map = {g['ID']: g for g in guests}

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header with user-friendly names
        writer.writerow([
            "Presentation ID", "Title", "Presenter Name", "Presenter Role", "Contact",
            "Submission Date", "Approval Status", "Marks (out of 10)", "Reviewed By", "Approval Date"
        ])

        # Write data
        for p in presentations:
            guest = guest_map.get(p.get('guest_id'))
            writer.writerow([
                p.get('id'),
                p.get('title'),
                guest.get('Name', 'Unknown') if guest else 'Unknown',
                guest.get('GuestRole', '') if guest else '',
                guest.get('Phone', '') if guest else '',
                p.get('upload_date'),
                p.get('selected_status', 'Pending'),
                p.get('marks_allotted', 'N/A'),
                p.get('remarks_by', 'N/A'),
                p.get('approval_date', '')
            ])

        output.seek(0)
        filename = f"presentations_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting presentations report: {e}")
        raise HTTPException(status_code=500, detail="Error exporting report")

@router.get("/download_presentation/{file_name}")
async def download_presentation(admin: Dict = Depends(get_current_admin), file_name: str = FastAPIPath(...)):
    """Download an uploaded presentation file"""
    try:
        safe_name = os.path.basename(file_name).strip()
        file_path = os.path.join(config.get('PATHS', 'StaticDir'), 'uploads', 'presentations', safe_name)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        return StreamingResponse(open(file_path, 'rb'), headers={'Content-Disposition': f'attachment; filename="{safe_name}"'})
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
                if guest.get("BadgePrinted") == "True":
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "message": "Badge already printed"}
                    )
                guest["BadgePrinted"] = "True"
                guest["BadgePrintedDate"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
    """Download badge for admin - improved error handling"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)

        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        if not validate_guest_data_safe(guest):
            guest = {
                'ID': guest_id,
                'Name': guest.get('Name', 'Unknown Guest'),
                'GuestRole': guest.get('GuestRole', 'Event'),
                'Phone': guest.get('Phone', ''),
                'Organization': guest.get('Organization', '')
            }

        badge_image = create_magnacode_badge_working(guest)

        img_byte_array = io.BytesIO()
        badge_image.save(img_byte_array, format='PNG', dpi=(300, 300))
        img_byte_array.seek(0)

        log_activity(guest_id, f"Admin {admin['user_id']} downloaded badge")

        return StreamingResponse(
            img_byte_array,
            media_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="MAGNACODE2025_Badge_{guest_id}.png"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading badge for {guest_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Badge generation failed: {str(e)}")

@router.post("/print_and_download_badge")
async def print_and_download_badge(request: Request, admin: Dict = Depends(get_current_admin), guest_id: str = Form(...)):
    """Print and download badge - improved error handling"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)

        if not guest:
            return JSONResponse(status_code=404, content={"success": False, "message": "Guest not found"})

        for g in guests:
            if g["ID"] == guest_id:
                g["BadgePrinted"] = "True"
                break
        guests_db.write_all(guests)

        if not validate_guest_data_safe(guest):
            guest = {
                'ID': guest_id,
                'Name': guest.get('Name', 'Unknown Guest'),
                'GuestRole': guest.get('GuestRole', 'Event'),
                'Phone': guest.get('Phone', ''),
                'Organization': guest.get('Organization', '')
            }

        badge_image = create_magnacode_badge_working(guest)

        img_byte_array = io.BytesIO()
        badge_image.save(img_byte_array, format='PNG', dpi=(300, 300))
        img_byte_array.seek(0)

        log_activity(guest_id, f"Admin {admin['user_id']} printed badge")

        return StreamingResponse(
            img_byte_array,
            media_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="MAGNACODE2025_Badge_{guest_id}.png"'
            }
        )

    except Exception as e:
        logger.error(f"Error printing badge for {guest_id}: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": f"Badge generation failed: {str(e)}"})
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
                guest["BadgeGivenDate"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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

        # *** UPDATED: Use synchronized journey service ***
        journey_service = create_journey_service(config)
        journey_data = journey_service.get_journey_data(guest_id)

        if journey_data:
            guest.update({
                "InwardJourneyDate": journey_data.get("inward_date", ""),
                "InwardJourneyFrom": journey_data.get("inward_origin", ""),
                "InwardJourneyTo": journey_data.get("inward_destination", ""),
                "InwardJourneyDetails": journey_data.get("inward_transport_details", ""),
                "InwardJourneyRemarks": journey_data.get("inward_remarks", ""),
                "InwardPickupRequired": "True" if journey_data.get("pickup_required") else "False",
                "OutwardJourneyDate": journey_data.get("outward_date", ""),
                "OutwardJourneyFrom": journey_data.get("outward_origin", ""),
                "OutwardJourneyTo": journey_data.get("outward_destination", ""),
                "OutwardJourneyDetails": journey_data.get("outward_transport_details", ""),
                "OutwardJourneyRemarks": journey_data.get("outward_remarks", ""),
                "OutwardDropRequired": "True" if journey_data.get("drop_required") else "False",
                "Day1PickupLocation": journey_data.get("day1_pickup_location", ""),
                "Day1PickupTime": journey_data.get("day1_pickup_time", ""),
                "Day1DropLocation": journey_data.get("day1_drop_location", ""),
                "Day1DropTime": journey_data.get("day1_drop_time", ""),
                "Day2PickupLocation": journey_data.get("day2_pickup_location", ""),
                "Day2PickupTime": journey_data.get("day2_pickup_time", ""),
                "Day2DropLocation": journey_data.get("day2_drop_location", ""),
                "Day2DropTime": journey_data.get("day2_drop_time", ""),
                "LastJourneyUpdate": journey_data.get("updated_at", ""),
                "JourneyDetailsUpdated": "True" if journey_data.get("updated_at") else "False",
            })
            
        # Get guest presentations
        presentations_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), 'presentations.csv')
        presentations = []
        if os.path.exists(presentations_csv):
            with open(presentations_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('guest_id') == guest_id:
                        file_name = resolve_presentation_filename(row)
                        if file_name:
                            row['file_url'] = f"/admin/download_presentation/{file_name}"
                        else:
                            row['file_url'] = ''
                        if 'title' not in row and row.get('file_name'):
                            row['title'] = row.get('file_name')
                        presentations.append(row)

        # Get guest messages
        messages_csv = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), 'messages.csv')
        guest_messages = []
        if os.path.exists(messages_csv):
            with open(messages_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('guest_id') == guest_id:
                        row['message'] = row.get('message') or row.get('content', '')
                        guest_messages.append(row)

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
                "guest_messages": guest_messages,
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
    """Generate badge for admin - improved error handling"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)

        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        if not validate_guest_data_safe(guest):
            guest = {
                'ID': guest_id,
                'Name': guest.get('Name', 'Unknown Guest'),
                'GuestRole': guest.get('GuestRole', 'Event'),
                'Phone': guest.get('Phone', ''),
                'Organization': guest.get('Organization', '')
            }

        badge_image = create_magnacode_badge_working(guest)

        img_byte_array = io.BytesIO()
        badge_image.save(img_byte_array, format='PNG', dpi=(300, 300))
        img_byte_array.seek(0)

        log_activity(guest_id, f"Admin {admin['user_id']} generated badge")

        return StreamingResponse(
            img_byte_array,
            media_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="MAGNACODE2025_{guest_id}_badge.png"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating badge for {guest_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Badge generation failed: {str(e)}")
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
                if guest.get("BadgePrinted") != "True":
                    guest["BadgePrinted"] = "True"
                    guest["BadgePrintedDate"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
                if guest.get("BadgeGiven") != "True":
                    guest["BadgeGiven"] = "True"
                    guest["BadgeGivenDate"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
    """Update complete journey details with all fields - synchronized version"""
    try:
        data = await request.json()
        guest_id = data.get('guest_id')

        if not guest_id:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Guest ID is required"}
            )

        journey_service = create_journey_service(config)
        success = journey_service.update_journey_from_admin(guest_id, data)

        if success:
            log_activity(guest_id, f"Admin {admin['user_id']} updated complete journey details")
            return JSONResponse(
                content={"success": True, "message": "Journey details updated successfully"}
            )
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "Failed to update journey details"}
            )
    except Exception as e:
        logger.error(f"Error updating journey details: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error updating journey details: {str(e)}"}
        )

@router.get("/api/journey-details/{guest_id}")
async def get_journey_details(guest_id: str, admin: Dict = Depends(get_current_admin)):
    """Get detailed journey information for a specific guest - synchronized version"""
    try:
        journey_service = create_journey_service(config)
        journey_data = journey_service.get_journey_data(guest_id)

        if not journey_data:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "No journey data found"}
            )

        journey_details = {
            "inward_date": journey_data.get("inward_date", ""),
            "inward_origin": journey_data.get("inward_origin", ""),
            "inward_destination": journey_data.get("inward_destination", ""),
            "inward_details": journey_data.get("inward_transport_details", ""),
            "inward_pickup": journey_data.get("pickup_required", False),
            "inward_remarks": journey_data.get("inward_remarks", ""),
            "outward_date": journey_data.get("outward_date", ""),
            "outward_origin": journey_data.get("outward_origin", ""),
            "outward_destination": journey_data.get("outward_destination", ""),
            "outward_details": journey_data.get("outward_transport_details", ""),
            "outward_drop": journey_data.get("drop_required", False),
            "outward_remarks": journey_data.get("outward_remarks", ""),
            "updated_at": journey_data.get("updated_at", ""),
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

@router.post("/sync_journey_data")
async def sync_journey_data(request: Request, admin: Dict = Depends(get_current_admin)):
    """Manually trigger journey data synchronization between all systems"""
    try:
        journey_service = create_journey_service(config)
        stats = journey_service.sync_all_data()

        log_activity("System", f"Admin {admin['user_id']} triggered journey data sync")

        return JSONResponse(
            content={
                "success": True,
                "message": "Journey data synchronization completed",
                "stats": stats,
            }
        )
    except Exception as e:
        logger.error(f"Error during journey sync: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Sync failed: {str(e)}"}
        )

# ENHANCED FOOD MANAGEMENT ROUTES (Updated from paste content)

@router.post("/give_food_coupon")
async def give_food_coupon(request: Request, admin: Dict = Depends(get_current_admin), guest_id: str = Form(...), day: str = Form(...)):
    """Give food coupons to guest for a specific day with proper validation"""
    try:
        ensure_all_guest_fields()

        if day not in ["1", "2"]:
            return JSONResponse(status_code=400, content={"success": False, "message": "Invalid day specified"})

        guests = guests_db.read_all()
        updated = False

        for guest in guests:
            if guest["ID"] == guest_id:
                field_name = f"FoodCouponsDay{day}"
                date_field = f"FoodCouponsDay{day}Date"

                if guest.get(field_name, "False") == "True":
                    return JSONResponse(status_code=400, content={"success": False, "message": f"Food coupons for Day {day} already given"})

                guest[field_name] = "True"
                guest[date_field] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                updated = True
                break

        if updated:
            guests_db.write_all(guests)
            log_activity(guest_id, f"Admin {admin['user_id']} gave Day {day} food coupons")
            return JSONResponse(content={"success": True, "message": f"Food coupons for Day {day} marked as given successfully"})
        else:
            return JSONResponse(status_code=404, content={"success": False, "message": "Guest not found"})

    except Exception as e:
        logger.error(f"Error giving food coupons: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": f"Error giving food coupons: {str(e)}"})

@router.post("/give_food_coupons_bulk")
async def give_food_coupons_bulk(request: Request, admin: Dict = Depends(get_current_admin)):
    """Give food coupons to multiple guests with proper validation"""
    try:
        ensure_all_guest_fields()

        data = await request.json()
        guest_ids = data.get('guest_ids', [])
        day = data.get('day')

        if not guest_ids:
            return JSONResponse(status_code=400, content={"success": False, "message": "No guest IDs provided"})

        if day not in ["1", "2"]:
            return JSONResponse(status_code=400, content={"success": False, "message": "Invalid day specified"})

        guests = guests_db.read_all()
        updated_count = 0
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        field_name = f"FoodCouponsDay{day}"
        date_field = f"FoodCouponsDay{day}Date"

        for guest in guests:
            if guest["ID"] in guest_ids and guest.get(field_name, "False") != "True":
                guest[field_name] = "True"
                guest[date_field] = current_time
                updated_count += 1

        if updated_count > 0:
            guests_db.write_all(guests)
            log_activity("Bulk", f"Admin {admin['user_id']} gave Day {day} food coupons to {updated_count} guests")
            return JSONResponse(content={"success": True, "message": f"Day {day} food coupons given to {updated_count} guests successfully"})
        else:
            return JSONResponse(status_code=400, content={"success": False, "message": "No eligible guests found or coupons already given"})

    except Exception as e:
        logger.error(f"Error giving food coupons in bulk: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": f"Error giving food coupons: {str(e)}"})


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
    """Mark gifts as given to guest with proper validation"""
    try:
        ensure_all_guest_fields()

        guests = guests_db.read_all()
        updated = False

        for guest in guests:
            if guest["ID"] == guest_id:
                if guest.get("GiftsGiven", "False") == "True":
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
            log_activity(guest_id, f"Admin {admin['user_id']} marked gifts as given")
            return JSONResponse(content={"success": True, "message": "Gifts marked as given successfully"})
        else:
            return JSONResponse(status_code=404, content={"success": False, "message": "Guest not found"})

    except Exception as e:
        logger.error(f"Error giving gifts: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": f"Error giving gifts: {str(e)}"})

@router.post("/give_gifts_bulk")
async def give_gifts_bulk(request: Request, admin: Dict = Depends(get_current_admin)):
    """Give gifts to multiple guests with proper validation"""
    try:
        ensure_all_guest_fields()

        data = await request.json()
        guest_ids = data.get('guest_ids', [])

        if not guest_ids:
            return JSONResponse(status_code=400, content={"success": False, "message": "No guest IDs provided"})

        guests = guests_db.read_all()
        updated_count = 0
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for guest in guests:
            if guest["ID"] in guest_ids and guest.get("GiftsGiven", "False") != "True":
                guest["GiftsGiven"] = "True"
                guest["GiftGivenDate"] = current_time
                updated_count += 1

        if updated_count > 0:
            guests_db.write_all(guests)
            log_activity("Bulk", f"Admin {admin['user_id']} gave gifts to {updated_count} guests")
            return JSONResponse(content={"success": True, "message": f"Gifts given to {updated_count} guests successfully"})
        else:
            return JSONResponse(status_code=400, content={"success": False, "message": "No eligible guests found or gifts already given"})

    except Exception as e:
        logger.error(f"Error giving gifts in bulk: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": f"Error giving gifts: {str(e)}"})


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

@router.post("/update_kit_status")
async def update_kit_status(request: Request, admin: Dict = Depends(get_current_admin), guest_id: str = Form(...)):
    """Toggle kit received status"""
    try:
        guests = guests_db.read_all()
        updated = False

        for guest in guests:
            if guest["ID"] == guest_id:
                current_status = guest.get("KitReceived", "False")
                new_status = "False" if current_status == "True" else "True"
                guest["KitReceived"] = new_status
                if new_status == "True":
                    guest["KitReceivedDate"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                else:
                    guest["KitReceivedDate"] = ""
                updated = True
                break

        if updated:
            guests_db.write_all(guests)
            log_activity(guest_id, f"Admin {admin['user_id']} updated kit status")
            return JSONResponse(content={"success": True, "message": "Kit status updated successfully"})
        else:
            return JSONResponse(status_code=404, content={"success": False, "message": "Guest not found"})
    except Exception as e:
        logger.error(f"Error updating kit status: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": f"Error: {str(e)}"})


@router.post("/toggle_attendance")
async def toggle_attendance(request: Request, admin: Dict = Depends(get_current_admin), guest_id: str = Form(...)):
    """Toggle attendance status"""
    try:
        guests = guests_db.read_all()
        updated = False

        for guest in guests:
            if guest["ID"] == guest_id:
                current_status = guest.get("DailyAttendance", "False")
                new_status = "False" if current_status == "True" else "True"
                guest["DailyAttendance"] = new_status
                if new_status == "True":
                    guest["CheckInTime"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                else:
                    guest["CheckInTime"] = ""
                updated = True
                break

        if updated:
            guests_db.write_all(guests)
            log_activity(guest_id, f"Admin {admin['user_id']} toggled attendance")
            return JSONResponse(content={"success": True, "message": "Attendance updated successfully"})
        else:
            return JSONResponse(status_code=404, content={"success": False, "message": "Guest not found"})
    except Exception as e:
        logger.error(f"Error toggling attendance: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": f"Error: {str(e)}"})


@router.get("/api/guest-status/{guest_id}")
async def get_real_time_status(guest_id: str, admin: Dict = Depends(get_current_admin)):
    """Get real-time status for a guest"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)

        if not guest:
            return JSONResponse(status_code=404, content={"success": False, "message": "Guest not found"})

        status = {
            "attendance": guest.get("DailyAttendance", "False") == "True",
            "badge_printed": guest.get("BadgePrinted", "False") == "True",
            "badge_given": guest.get("BadgeGiven", "False") == "True",
            "kit_received": guest.get("KitReceived", "False") == "True",
            "gifts_given": guest.get("GiftsGiven", "False") == "True",
            "food_day1": guest.get("FoodCouponsDay1", "False") == "True",
            "food_day2": guest.get("FoodCouponsDay2", "False") == "True",
            "payment_status": guest.get("PaymentStatus", "Pending"),
            "payment_amount": guest.get("PaymentAmount", "0"),
            "journey_updated": guest.get("JourneyDetailsUpdated", "False") == "True",
            "journey_completed": guest.get("JourneyCompleted", "False") == "True",

            # Timestamps
            "checkin_time": guest.get("CheckInTime", ""),
            "badge_printed_date": guest.get("BadgePrintedDate", ""),
            "badge_given_date": guest.get("BadgeGivenDate", ""),
            "kit_received_date": guest.get("KitReceivedDate", ""),
            "gift_given_date": guest.get("GiftGivenDate", ""),
            "food_day1_date": guest.get("FoodCouponsDay1Date", ""),
            "food_day2_date": guest.get("FoodCouponsDay2Date", "")
        }

        return JSONResponse(content={"success": True, "status": status})
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": f"Error: {str(e)}"})

@router.post("/update_guest_basic_info")
async def update_guest_basic_info(request: Request, admin: Dict = Depends(get_current_admin)):
    """Update guest basic information (for inline editing)"""
    try:
        data = await request.json()
        guest_id = data.get('guest_id')
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        kmc_number = data.get('kmc_number')
        availability = data.get('availability')
        
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                guest["Name"] = name
                guest["Email"] = email
                guest["Phone"] = phone
                guest["KMCNumber"] = kmc_number
                guest["Availability"] = availability
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
    guest_messages = []
    guests_map = {}
    guests_list = []

    # Read guest info for mapping
    try:
        with open(guests_path, newline='', encoding='utf-8') as gfile:
            for row in csv.DictReader(gfile):
                guests_map[row['ID']] = row
        guests_list = sorted(guests_map.values(), key=lambda g: g.get('Name', ''))
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
                guest_messages.append({
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

    logging.info(f"[{trace_id}] Loaded {len(guest_messages)} messages for admin display.")
    return templates.TemplateResponse(
        "admin/messages_management.html",
        {
            "request": request,
            "guest_messages": guest_messages,
            "search_query": q,
            "trace_id": trace_id,
            "guests": guests_list,
        }
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


@router.post("/send_message")
async def admin_send_message(
    request: Request,
    admin: Dict = Depends(get_current_admin),
    guest_id: str = Form(...),
    message: str = Form(...),
):
    """Send a new message to a guest"""
    try:
        messages_path = config.get('DATABASE', 'MessagesCSV', fallback='./data/messages.csv')
        fieldnames = [
            "id",
            "guest_id",
            "message",
            "timestamp",
            "read",
            "response",
            "response_timestamp",
        ]

        file_exists = os.path.exists(messages_path)
        with open(messages_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            now = datetime.now().isoformat()
            writer.writerow(
                {
                    "id": str(uuid.uuid4()),
                    "guest_id": guest_id,
                    "message": "",
                    "timestamp": now,
                    "read": "True",
                    "response": message,
                    "response_timestamp": now,
                }
            )
        return RedirectResponse(url="/admin/messages", status_code=303)
    except Exception as e:
        logging.error(f"Error sending message to guest: {e}")
        raise HTTPException(status_code=500, detail="Error sending message")

# START: New CSV Upload Routes

@router.get("/upload_guests", response_class=HTMLResponse)
async def upload_guests_page(request: Request, admin: Dict = Depends(get_current_admin)):
    """Render the page for uploading a guest CSV file."""
    return templates.TemplateResponse("admin/upload_guests.html", {"request": request, "admin": admin})

@router.post("/upload_guests")
async def handle_guest_upload(
    request: Request,
    admin: Dict = Depends(get_current_admin),
    file: UploadFile = File(...)
):
    """Handle the upload and processing of a guest CSV file with robust validation."""
    if not file.filename.endswith('.csv'):
        return JSONResponse(
            status_code=400,
            content={"success": False, "errors": [{"row": "N/A", "field": "File", "value": file.filename, "error": "Invalid file type. Only CSV is supported."}]}
        )

    temp_path = f"temp_{datetime.now().timestamp()}.csv"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        new_guests, errors = await process_guest_csv(temp_path)

        if errors:
            return JSONResponse(status_code=422, content={"success": False, "errors": errors})

        # --- START FIX ---
        existing_guests = guests_db.read_all()
        all_guests = existing_guests + new_guests

        # Define a complete and canonical list of ALL possible headers to prevent errors.
        # This list includes all fields from the Guest model AND the journey sync service.
        master_fieldnames = [
            "ID", "Name", "Phone", "Email", "GuestRole", "RegistrationDate",
            "DailyAttendance", "IsActive", "KitReceived", "BadgePrinted", "BadgeGiven",
            "BadgePrintedDate", "BadgeGivenDate", "KitReceivedDate", "CheckInTime",
            "PaymentStatus", "PaymentAmount", "PaymentDate", "PaymentMethod",
            "Organization", "KMCNumber", "Notes", "JourneyDetailsUpdated", "JourneyCompleted",
            "FoodCouponsDay1", "FoodCouponsDay2", "FoodCouponsDay1Date", "FoodCouponsDay2Date",
            "GiftsGiven", "GiftGivenDate", "GiftNotes", "FoodNotes", "Availability",
            "LastJourneyUpdate", "InwardJourneyDate", "InwardJourneyFrom", "InwardJourneyTo",
            "InwardJourneyDetails", "InwardPickupRequired", "InwardJourneyRemarks",
            "OutwardJourneyDate", "OutwardJourneyFrom", "OutwardJourneyTo",
            "OutwardJourneyDetails", "OutwardDropRequired", "OutwardJourneyRemarks",
            "Batch", "CompanyName"
        ]

        # Ensure every guest dictionary has all keys from the master list.
        # This prevents the "dict contains fields not in fieldnames" error.
        default_guest_dict = {field: "" for field in master_fieldnames}

        processed_guests = []
        for guest_dict in all_guests:
            full_guest_record = default_guest_dict.copy()
            full_guest_record.update(guest_dict)
            processed_guests.append(full_guest_record)

        guests_db.write_all(processed_guests, fieldnames=master_fieldnames)
        # --- END FIX ---

        log_activity("Admin", f"Admin {admin['user_id']} uploaded {len(new_guests)} new guests from CSV.")

        return JSONResponse(
            status_code=200,
            content={"success": True, "message": f"Successfully uploaded and added {len(new_guests)} new guests."}
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

async def process_guest_csv(file_path: str):
    """
    Read, validate, and normalize data from an uploaded guest CSV with enhanced, intuitive error reporting.
    """
    from app.utils.helpers import generate_unique_id
    import logging

    logger = logging.getLogger(__name__)

    new_guests = []
    errors = []

    existing_guests = guests_db.read_all()
    existing_phones = {g['Phone'] for g in existing_guests if g.get('Phone')}
    existing_ids = {g['ID'] for g in existing_guests}
    phones_in_current_file = set()

    try:
        with open(file_path, mode='r', newline='', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)

            # --- START: Header Validation ---
            csv_headers = reader.fieldnames
            model_headers = list(Guest().to_dict().keys())

            # Check for missing required headers in the CSV
            required_headers = ["Name", "Phone", "GuestRole"]
            missing_headers = [h for h in required_headers if h not in csv_headers]
            if missing_headers:
                error_detail = f"The CSV file is missing the following required columns: {', '.join(missing_headers)}."
                logger.error(error_detail)
                errors.append({"row": 1, "field": "File Headers", "value": "N/A", "error": error_detail})
                return [], errors
            # --- END: Header Validation ---

            for index, row in enumerate(reader, start=2):
                guest_model = Guest()
                row_errors = []

                name = row.get("Name", "").strip()
                phone = re.sub(r'\D', '', row.get("Phone", "").strip())
                role = row.get("GuestRole", "").strip()

                if not name:
                    row_errors.append({"field": "Name", "value": name, "error": "Name cannot be empty."})
                if not phone:
                    row_errors.append({"field": "Phone", "value": row.get("Phone"), "error": "Phone number is required."})
                if len(phone) != 10:
                    row_errors.append({"field": "Phone", "value": phone, "error": "Phone number must be exactly 10 digits."})
                if phone in existing_phones:
                    row_errors.append({"field": "Phone", "value": phone, "error": "This phone number is already in the database."})
                if phone in phones_in_current_file:
                    row_errors.append({"field": "Phone", "value": phone, "error": "This phone number is a duplicate of another row in this file."})

                if not role:
                    row_errors.append({"field": "GuestRole", "value": role, "error": "GuestRole is required."})
                elif role not in ["Delegate", "Faculty", "Sponsor", "Staff", "Guest"]:
                    row_errors.append({"field": "GuestRole", "value": role, "error": "Invalid role specified."})

                if row_errors:
                    for err in row_errors:
                        err['row'] = index
                        logger.warning(f"CSV Upload Validation Error - Row {index}: Field='{err['field']}', Value='{err['value']}', Error='{err['error']}'")
                    errors.extend(row_errors)
                    continue

                # Populate guest object from the row, using all possible fields from the model
                for field in model_headers:
                    if field in row:
                        setattr(guest_model, field.lower(), row[field].strip())

                # Set core validated fields
                guest_model.name = name
                guest_model.phone = phone
                guest_model.guest_role = role
                guest_model.id = generate_unique_id(list(existing_ids), 4)

                new_guests.append(guest_model.to_dict())
                phones_in_current_file.add(guest_model.phone)
                existing_ids.add(guest_model.id)

    except Exception as e:
        error_message = f"An unexpected error occurred while processing the CSV file: {str(e)}"
        logger.error(error_message, exc_info=True)
        errors.append({"row": "N/A", "field": "File Processing", "value": "N/A", "error": "The file could not be read. Please ensure it is a valid, UTF-8 encoded CSV."})

    return new_guests, errors

# END: New CSV Upload Routes

# HELPER FUNCTIONS


def create_magnacode_badge(guest: dict) -> Image.Image:
    """Create MAGNACODE 2025 corporate badge - NO FALLBACKS"""
    dpi = 300
    width_px = int(90 * dpi / 25.4)
    height_px = int(140 * dpi / 25.4)
    badge = Image.new('RGB', (width_px, height_px), '#ffffff')
    draw = ImageDraw.Draw(badge)

    navy_blue = '#1e3a8a'
    bright_orange = '#f97316'
    sky_blue = '#e0f2fe'
    pearl_gray = '#f8fafc'
    charcoal = '#334155'
    gold = '#fbbf24'

    header_height = 413
    for y in range(header_height):
        intensity = 1 - (y / header_height * 0.25)
        blue_val = int(30 + (108 * intensity))
        draw.line([(0, y), (width_px, y)], fill=f'#{blue_val:02x}3a8a')

    draw.text((width_px//2, 60), "Magna Endocrine Update 2025", fill='white', anchor="mm", font_size=48)
    draw.text((width_px//2, 120), "Healthcare and Education Foundation", fill='white', anchor="mm", font_size=28)
    draw.text((width_px//2, 170), "21st & 22nd September 2025", fill=gold, anchor="mm", font_size=24)
    draw.text((width_px//2, 210), "Bangalore", fill='white', anchor="mm", font_size=22)

    content_start_y = 460
    margin = 55

    qr_size = 240
    qr_padding = 30
    qr_container_size = qr_size + (qr_padding * 2)
    qr_x = margin
    qr_y = content_start_y + 100

    shadow_offset = 6
    draw.rectangle([(qr_x + shadow_offset, qr_y + shadow_offset), (qr_x + qr_container_size + shadow_offset, qr_y + qr_container_size + shadow_offset)], fill='#00000025')
    draw.rectangle([(qr_x, qr_y), (qr_x + qr_container_size, qr_y + qr_container_size)], fill='white', outline=navy_blue, width=5)
    draw.rectangle([(qr_x + 10, qr_y + 10), (qr_x + qr_container_size - 10, qr_y + qr_container_size - 10)], fill=None, outline=bright_orange, width=2)

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=1)
    qr.add_data(f"MAGNACODE2025:{guest['ID']}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=navy_blue, back_color="white")
    qr_resized = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    badge.paste(qr_resized, (qr_x + qr_padding, qr_y + qr_padding))

    draw.text((qr_x + qr_container_size//2, qr_y + qr_container_size + 25), "Scan for Check-in", fill=charcoal, anchor="mm", font_size=18)

    info_x = qr_x + qr_container_size + 50
    info_width = width_px - info_x - margin
    info_y = content_start_y + 50

    id_height = 60
    draw.rectangle([(info_x, info_y), (width_px - margin, info_y + id_height)], fill=bright_orange)
    draw.rectangle([(info_x + 3, info_y + 3), (width_px - margin - 3, info_y + id_height - 3)], fill=None, outline='#ffffff40', width=1)
    draw.text((info_x + info_width//2, info_y + id_height//2), f"ID: {guest['ID']}", fill='white', anchor="mm", font_size=24)

    name_y = info_y + id_height + 25
    guest_name = guest.get('Name', '')
    if guest_name:
        role = guest.get('GuestRole', '')
        if role in ['Delegates', 'Faculty']:
            if not any(prefix in guest_name.upper() for prefix in ['DR.', 'PROF.', 'MR.', 'MS.', 'MRS.']):
                guest_name = f"Dr. {guest_name}"

    name_height = 95
    draw.rectangle([(info_x, name_y), (width_px - margin, name_y + name_height)], fill=sky_blue, outline=navy_blue, width=4)

    if len(guest_name) > 20:
        words = guest_name.split(' ')
        if len(words) > 1:
            mid = len(words) // 2
            line1 = ' '.join(words[:mid])
            line2 = ' '.join(words[mid:])
            draw.text((info_x + info_width//2, name_y + 30), line1, fill=navy_blue, anchor="mm", font_size=22)
            draw.text((info_x + info_width//2, name_y + 65), line2, fill=navy_blue, anchor="mm", font_size=22)
        else:
            draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm", font_size=20)
    else:
        draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm", font_size=24)

    role = guest.get('GuestRole', 'Event')
    role_colors = {
        'Delegates': '#059669',
        'Faculty': '#dc2626',
        'Sponsor': '#d97706',
        'Event': '#7c3aed'
    }
    if role not in role_colors:
        role = 'Event'
    role_color = role_colors[role]
    role_y = name_y + name_height + 20
    role_height = 50
    draw.rectangle([(info_x, role_y), (width_px - margin, role_y + role_height)], fill=role_color)
    draw.rectangle([(info_x, role_y), (width_px - margin, role_y + 15)], fill='#ffffff30')
    draw.text((info_x + info_width//2, role_y + role_height//2), role.upper(), fill='white', anchor="mm", font_size=22)

    contact_y = role_y + role_height + 30
    kmc = guest.get('KMCNumber', '')
    if kmc:
        draw.text((info_x + 15, contact_y), f"KMC: {kmc}", fill=charcoal, font_size=16)
        contact_y += 40
    phone = guest.get('Phone', '')
    if phone:
        if len(phone) == 10 and phone.isdigit():
            formatted_phone = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
        else:
            formatted_phone = phone
        draw.text((info_x + 15, contact_y), f"📱 {formatted_phone}", fill=charcoal, font_size=16)
        contact_y += 40
    org = guest.get('Organization', '')
    if org:
        if len(org) > 25:
            org = org[:22] + "..."
        draw.text((info_x + 15, contact_y), f"🏢 {org}", fill=charcoal, font_size=16)

    footer_y = height_px - 140
    draw.rectangle([(0, footer_y), (width_px, height_px)], fill=pearl_gray)
    draw.rectangle([(0, footer_y), (width_px, footer_y + 4)], fill=bright_orange)

    footer_lines = [
        "🏨 Venue: The Chancery Pavilion, Bangalore",
        "⚕️ Healthcare Excellence • 📚 Education Innovation",
        "🌐 www.magnacode.org • 📧 info@magnacode.org"
    ]
    for i, line in enumerate(footer_lines):
        draw.text((width_px//2, footer_y + 25 + (i * 35)), line, fill=charcoal, anchor="mm", font_size=16)

    corner_size = 30
    draw.polygon([(width_px - corner_size - 15, 15), (width_px - 15, 15), (width_px - 15, corner_size + 15)], fill=bright_orange)
    draw.polygon([(15, height_px - corner_size - 15), (corner_size + 15, height_px - corner_size - 15), (15, height_px - 15)], fill=bright_orange)
    draw.rectangle([(0, 0), (10, height_px)], fill=bright_orange)
    draw.rectangle([(width_px - 10, 0), (width_px, height_px)], fill=bright_orange)
    draw.rectangle([(0, 0), (width_px - 1, height_px - 1)], fill=None, outline=navy_blue, width=5)
    draw.rectangle([(5, 5), (width_px - 6, height_px - 6)], fill=None, outline=bright_orange, width=1)

    logo_diameter = 70
    logo_x = width_px - 90
    logo_y = 90
    logo_radius = logo_diameter // 2
    draw.ellipse([(logo_x - logo_radius, logo_y - logo_radius), (logo_x + logo_radius, logo_y + logo_radius)], fill='white', outline=bright_orange, width=3)
    draw.text((logo_x, logo_y), "MC", fill=navy_blue, anchor="mm", font_size=20)
    return badge


def validate_guest_data(guest: dict) -> bool:
    """Validate guest data - NO FALLBACKS"""
    required_fields = ['ID', 'Name', 'GuestRole']
    for field in required_fields:
        if not guest.get(field):
            return False
    valid_roles = ['Delegates', 'Faculty', 'Sponsor', 'Event']
    if guest['GuestRole'] not in valid_roles:
        return False
    return True


def validate_guest_data_safe(guest: dict) -> bool:
    """More permissive validation used for badge generation"""
    if not guest or not guest.get('ID'):
        return False
    return True


def create_magnacode_badge_working(guest: dict) -> Image.Image:
    """Badge generator with role-based backgrounds."""

    # 1. Define image paths and role mapping
    base_path = Path("static/raw_id_card")
    role_image_map = {
        'Delegates': base_path / "DELEGATE.jpg",
        'Faculty': base_path / "FACULTY.jpg",
        'Sponsor': base_path / "SPONSOR.jpg",
    }
    default_image = base_path / "ORGANIZER.jpg"

    guest_role = guest.get('GuestRole', 'Event')
    image_path = role_image_map.get(guest_role, default_image)

    # 2. Load the background image
    try:
        badge = Image.open(image_path)
    except FileNotFoundError:
        badge = Image.new('RGB', (1081, 1441), '#ffffff')

    draw = ImageDraw.Draw(badge)
    width_px, height_px = badge.size

    navy_blue = '#1e3a8a'

    # --- CENTER ALIGNED GUEST INFO ---
    center_x = width_px // 2
    current_y = 550  # Starting Y position for the text block

    guest_name = guest.get('Name', 'Unknown Guest')
    role = guest.get('GuestRole', 'Event')
    guest_id = guest.get('ID', 'UNKNOWN')

    if role in ['Delegates', 'Faculty'] and guest_name and not any(prefix in guest_name.upper() for prefix in ['DR.', 'PROF.', 'MR.', 'MS.', 'MRS.']):
        guest_name = f"Dr. {guest_name}"

    # Guest Name (Larger Font)
    font_size_name = 65
    try:
        draw.text((center_x, current_y), guest_name, fill=navy_blue, anchor="mm", font_size=font_size_name)
    except TypeError:
        draw.text((center_x, current_y), guest_name, fill=navy_blue, anchor="mm")
    current_y += 100  # Increase space after the name

    # Guest Role (Smaller Font)
    font_size_details = 35
    try:
        draw.text((center_x, current_y), role.upper(), fill='black', anchor="mm", font_size=font_size_details)
    except TypeError:
        draw.text((center_x, current_y), role.upper(), fill='black', anchor="mm")
    current_y += 60  # Increase space after the role

    # Guest ID (Smaller Font)
    try:
        draw.text((center_x, current_y), f"ID: {guest_id}", fill='black', anchor="mm", font_size=font_size_details)
    except TypeError:
        draw.text((center_x, current_y), f"ID: {guest_id}", fill='black', anchor="mm")
    current_y += 80  # Increase space before the QR code

    # QR Code (Centered Below Text)
    qr_size = 300
    qr_x = center_x - (qr_size // 2)
    qr_y = current_y

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=1)
    qr.add_data(f"MAGNACODE2025:{guest_id}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=navy_blue, back_color="white")
    try:
        qr_resized = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    except AttributeError:
        qr_resized = qr_img.resize((qr_size, qr_size))
    badge.paste(qr_resized, (qr_x, qr_y))

    return badge

def test_badge_generation() -> bool:
    """Simple test to verify badge generation works"""
    test_guest = {
        'ID': 'TEST001',
        'Name': 'Test User',
        'GuestRole': 'Delegates',
        'Phone': '9876543210',
        'Organization': 'Test Org'
    }
    try:
        create_magnacode_badge_working(test_guest)
        print("\u2705 Badge generation successful")
        return True
    except Exception as e:
        print(f"\u274c Badge generation failed: {str(e)}")
        return False
def create_simple_badge(guest: Dict) -> Image.Image:
    """Create a professional badge design for MAGNACODE 2025"""
    try:
        # Create a badge with MAGNACODE 2025 theme
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
            draw.text((width//2, 30), "MAGNACODE 2025", fill='white', anchor="mm", font_size=36)
            draw.text((width//2, 70), "14th Annual Conference", fill='white', anchor="mm", font_size=20)
            draw.text((width//2, 100), "Bengal Diabetes Foundation", fill='white', anchor="mm", font_size=18)
            draw.text((width//2, 125), "June 14-15, 2025", fill='#ffeb3b', anchor="mm", font_size=16)
        except:
            # Fallback without font_size parameter
            draw.text((50, 30), "MAGNACODE 2025 - 14th Annual Conference", fill='white')
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
MAGNACODE 2025 - JOURNEY ITINERARY
===========================================

Guest Information:
- ID: {guest['ID']}
- Name: {guest.get('Name', 'N/A')}
- Role: {guest.get('GuestRole', 'N/A')}
- Phone: {guest.get('Phone', 'N/A')}
- Email: {guest.get('Email', 'N/A')}

Conference Details:
- Event: 14th Annual Conference - MAGNACODE 2025
- Dates: June 14-15, 2025
- Venue: ITC Fortune Park, Pushpanjali, Durgapur
- Organizer: Bengal Diabetes Foundation

Journey Status:
- Details Updated: {'Yes' if guest.get('JourneyDetailsUpdated') == 'True' else 'No'}
- Journey Completed: {'Yes' if guest.get('JourneyCompleted') == 'True' else 'No'}

Contact Information:
- Conference Helpline: +91 84800 02958
- Email: info@MAGNACODE2025.org

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

def ensure_all_guest_fields():
    """Ensure all required guest fields exist in the CSV"""
    try:
        guests = guests_db.read_all()
        if not guests:
            return

        required_fields = {
            # Existing boolean status fields
            "GiftsGiven": "False",
            "FoodCouponsDay1": "False",
            "FoodCouponsDay2": "False",
            "BadgePrinted": "False",
            "BadgeGiven": "False",
            "KitReceived": "False",
            "DailyAttendance": "False",

            # Date tracking fields
            "GiftGivenDate": "",
            "FoodCouponsDay1Date": "",
            "FoodCouponsDay2Date": "",
            "BadgePrintedDate": "",
            "BadgeGivenDate": "",
            "KitReceivedDate": "",
            "CheckInTime": "",

            # New KMC column
            "KMCNumber": "",

            # Payment related fields
            "PaymentStatus": "Pending",
            "PaymentAmount": "0",
            "PaymentDate": "",
            "PaymentMethod": "",

            # Notes fields
            "GiftNotes": "",
            "FoodNotes": "",
            "Availability": "Not Specified",
        }

        first_guest = guests[0]
        missing_fields = [f for f in required_fields if f not in first_guest]

        if missing_fields:
            for guest in guests:
                for field in missing_fields:
                    guest[field] = required_fields[field]

            guests_db.write_all(guests)
            logger.info(f"Added missing fields to CSV: {missing_fields}")

    except Exception as e:
        logger.error(f"Error ensuring guest fields: {str(e)}")

# Initialize all fields when the module is loaded
ensure_badge_fields()
ensure_journey_detail_fields()
ensure_enhanced_food_fields()
ensure_enhanced_gift_fields()
ensure_all_guest_fields()
