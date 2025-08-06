# app/routes/guest.py
from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict
import os
import logging
import uuid
from app.utils.helpers import generate_unique_id
from datetime import datetime
import shutil
import io
import base64
import qrcode
from PIL import Image, ImageDraw
from pathlib import Path

from app.services.qr_service import QRService
from app.services.journey_sync import create_journey_service
from app.services import EmailService

from app.services.csv_db import CSVDatabase
from app.services.auth import auth_service
from app.config import Config
from app.templates import templates
# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/guest", tags=["guest"])

# Initialize services
config = Config()
templates = Jinja2Templates(directory=config.get('PATHS', 'TemplatesDir'))
guests_db = CSVDatabase(
    config.get('DATABASE', 'CSVPath'),
    config.get('DATABASE', 'BackupDir')
)
# Initialize QR service
qr_service = QRService(config.get('PATHS', 'StaticDir'))
# Email service for registration notifications
email_service = EmailService()
# Use singleton auth_service from app.services.auth

# Define storage paths
UPLOADS_DIR = os.path.join(config.get('PATHS', 'StaticDir'), "uploads")
PRESENTATIONS_DIR = os.path.join(UPLOADS_DIR, "presentations")
PROFILE_PHOTOS_DIR = os.path.join(UPLOADS_DIR, "profile_photos")

# Ensure directories exist
os.makedirs(PRESENTATIONS_DIR, exist_ok=True)
os.makedirs(PROFILE_PHOTOS_DIR, exist_ok=True)

# Create CSV file paths
FACULTY_CSV = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "faculty.csv")
PRESENTATIONS_CSV = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "presentations.csv")
JOURNEY_CSV = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "journey.csv")
MESSAGES_CSV = os.path.join(os.path.dirname(config.get('DATABASE', 'CSVPath')), "messages.csv")

# Allowed file extensions
ALLOWED_PRESENTATION_EXTENSIONS = {".pdf", ".ppt", ".pptx", ".doc", ".docx", ".mp4", ".avi", ".webm"}
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}

# Dependency for guest authentication
async def get_current_guest(request: Request):
    """Verify guest is authenticated and return guest data"""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = auth_service.validate_session(session_id)
    if not session or session["role"] != "guest":
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get guest data
    guests = guests_db.read_all()
    guest = next((g for g in guests if g["ID"] == session["user_id"]), None)
    
    if not guest:
        raise HTTPException(status_code=401, detail="Guest not found")
        
    return guest

# Helper Functions
def is_faculty(guest_id: str) -> bool:
    """Check if guest has faculty access"""
    try:
        import csv
        
        if not os.path.exists(FACULTY_CSV):
            with open(FACULTY_CSV, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["guest_id", "is_active", "created_at", "last_login"])
            return False
            
        with open(FACULTY_CSV, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["guest_id"] == guest_id and row.get("is_active", "").lower() == "true":
                    return True
        return False
    except Exception as e:
        logger.error(f"Error checking faculty status: {str(e)}")
        return False

def update_faculty_login(guest_id: str):
    """Update faculty last login time"""
    try:
        import csv
        
        if not os.path.exists(FACULTY_CSV):
            return
            
        rows = []
        with open(FACULTY_CSV, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames
            
            for row in reader:
                if row["guest_id"] == guest_id:
                    row["last_login"] = datetime.now().isoformat()
                rows.append(row)
        
        with open(FACULTY_CSV, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        logger.error(f"Error updating faculty login: {str(e)}")

# Add this helper function for QR code generation
def generate_qr_base64(data: str) -> str:
    """Generate QR code as base64 string"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        return ""

# Enhanced registration confirmation email template
def create_registration_email_content(guest_data):
    """Create enhanced HTML email content for registration confirmation"""

    # Extract guest information
    guest_id = guest_data.get('ID')
    name = guest_data.get('Name')
    email = guest_data.get('Email')
    phone = guest_data.get('Phone')
    role = guest_data.get('GuestRole')
    kmc_number = guest_data.get('KMCNumber', '')
    registration_date = guest_data.get('RegistrationDate')

    # Format phone number nicely
    formatted_phone = phone
    if phone and len(phone) == 10 and phone.isdigit():
        formatted_phone = f"+91 {phone[:5]} {phone[5:]}"

    # Role-specific content
    role_specific_content = ""
    if role == "Faculty":
        role_specific_content = """
        <div style="background-color: #e3f2fd; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #1976d2; margin: 0 0 10px 0; font-size: 16px;">
                🎓 Faculty Information
            </h3>
            <p style="margin: 5px 0; color: #333;">
                As a faculty member, you'll have access to:
            </p>
            <ul style="margin: 10px 0; padding-left: 20px; color: #333;">
                <li>Faculty lounge and networking areas</li>
                <li>Presentation upload portal</li>
                <li>Speaker coordination services</li>
                <li>Priority conference materials</li>
            </ul>
        </div>
        """
    elif role == "Delegate":
        role_specific_content = """
        <div style="background-color: #e8f5e8; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #2e7d32; margin: 0 0 10px 0; font-size: 16px;">
                👥 Delegate Information
            </h3>
            <p style="margin: 5px 0; color: #333;">
                As a delegate, you'll enjoy:
            </p>
            <ul style="margin: 10px 0; padding-left: 20px; color: #333;">
                <li>Full access to all conference sessions</li>
                <li>Networking opportunities</li>
                <li>Conference materials and documentation</li>
                <li>Certificate of participation</li>
            </ul>
        </div>
        """
    elif role == "Sponsor":
        role_specific_content = """
        <div style="background-color: #fff3e0; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #f57c00; margin: 0 0 10px 0; font-size: 16px;">
                🤝 Sponsor Information
            </h3>
            <p style="margin: 5px 0; color: #333;">
                Thank you for sponsoring our event! You'll have:
            </p>
            <ul style="margin: 10px 0; padding-left: 20px; color: #333;">
                <li>Dedicated sponsor area access</li>
                <li>Brand visibility opportunities</li>
                <li>Networking with healthcare professionals</li>
                <li>Sponsor appreciation ceremony</li>
            </ul>
        </div>
        """

    # KMC number section (if provided)
    kmc_section = ""
    if kmc_number:
        kmc_section = f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; font-weight: 600; color: #555; width: 150px;">
                KMC Number:
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; color: #333;">
                {kmc_number}
            </td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Registration Confirmation - Magna Endocrine Update 2025</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: 'Segoe UI', Arial, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 30px; text-align: center;">
                <div style="background-color: white; width: 80px; height: 80px; border-radius: 50%; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold; color: #1e3a8a;">
                    MC
                </div>
                <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 300;">
                    Magna Endocrine Update 2025
                </h1>
                <p style="color: #e0f2fe; margin: 8px 0 0 0; font-size: 16px;">
                    Healthcare and Education Foundation
                </p>
                <p style="color: #fbbf24; margin: 5px 0 0 0; font-size: 14px; font-weight: 500;">
                    September 21-22, 2025 | Bangalore
                </p>
            </div>
            <div style="text-align: center; padding: 30px 30px 20px; background-color: #f8fffe;">
                <div style="background-color: #10b981; width: 60px; height: 60px; border-radius: 50%; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center;">
                    <span style="color: white; font-size: 24px;">✓</span>
                </div>
                <h2 style="color: #065f46; margin: 0 0 10px 0; font-size: 24px;">
                    Registration Confirmed!
                </h2>
                <p style="color: #047857; margin: 0; font-size: 16px;">
                    Welcome to Magna Endocrine Update 2025, {name}!
                </p>
            </div>
            <div style="padding: 30px;">
                <h3 style="color: #1f2937; margin: 0 0 20px 0; font-size: 20px; border-bottom: 2px solid #3b82f6; padding-bottom: 10px;">
                    📋 Your Registration Details
                </h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; font-weight: 600; color: #555; width: 150px; background-color: #f8fafc;">
                            Registration ID:
                        </td>
                        <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; color: #333;">
                            <span style="background-color: #3b82f6; color: white; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 16px;">
                                {guest_id}
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; font-weight: 600; color: #555; background-color: #f8fafc;">
                            Full Name:
                        </td>
                        <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; color: #333; font-weight: 500;">
                            {name}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; font-weight: 600; color: #555; background-color: #f8fafc;">
                            Role:
                        </td>
                        <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; color: #333;">
                            <span style="background-color: #10b981; color: white; padding: 3px 10px; border-radius: 15px; font-size: 14px;">
                                {role}
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; font-weight: 600; color: #555; background-color: #f8fafc;">
                            Email:
                        </td>
                        <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; color: #333;">
                            {email}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; font-weight: 600; color: #555; background-color: #f8fafc;">
                            Phone:
                        </td>
                        <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; color: #333;">
                            {formatted_phone}
                        </td>
                    </tr>
                    {kmc_section}
                    <tr>
                        <td style="padding: 12px; font-weight: 600; color: #555; background-color: #f8fafc;">
                            Registration Date:
                        </td>
                        <td style="padding: 12px; color: #333;">
                            {registration_date}
                        </td>
                    </tr>
                </table>
                {role_specific_content}
                <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 0 8px 8px 0; margin: 20px 0;">
                    <h3 style="color: #92400e; margin: 0 0 15px 0; font-size: 18px;">
                        🔔 Important Instructions
                    </h3>
                    <ul style="margin: 0; padding-left: 20px; color: #78350f;">
                        <li style="margin: 8px 0;"><strong>Save your Registration ID:</strong> {guest_id}</li>
                        <li style="margin: 8px 0;"><strong>Bring this ID</strong> for check-in at the conference</li>
                        <li style="margin: 8px 0;"><strong>Check-in opens:</strong> September 21, 2025 at 8:00 AM</li>
                        <li style="margin: 8px 0;"><strong>Venue:</strong> The Chancery Pavilion, Bangalore</li>
                    </ul>
                </div>
                <div style="background-color: #f0f9ff; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #0c4a6e; margin: 0 0 15px 0; font-size: 18px;">
                        📅 Conference Schedule
                    </h3>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
                        <div style="flex: 1; margin-right: 10px;">
                            <h4 style="color: #0369a1; margin: 0 0 8px 0; font-size: 16px;">Day 1 - September 21</h4>
                            <p style="margin: 0; color: #1e40af; font-size: 14px;">
                                📍 Registration & Opening Ceremony<br>
                                🎤 Keynote Sessions<br>
                                🍽️ Networking Lunch
                            </p>
                        </div>
                        <div style="flex: 1; margin-left: 10px;">
                            <h4 style="color: #0369a1; margin: 0 0 8px 0; font-size: 16px;">Day 2 - September 22</h4>
                            <p style="margin: 0; color: #1e40af; font-size: 14px;">
                                🔬 Technical Sessions<br>
                                🏆 Awards Ceremony<br>
                                🎉 Closing Reception
                            </p>
                        </div>
                    </div>
                </div>
                <div style="background-color: #f1f5f9; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #334155; margin: 0 0 15px 0; font-size: 18px;">
                        📞 Need Help?
                    </h3>
                    <p style="margin: 5px 0; color: #475569;">
                        <strong>Conference Helpline:</strong> <a href="tel:+918480002958" style="color: #3b82f6; text-decoration: none;">+91 84800 02958</a>
                    </p>
                    <p style="margin: 5px 0; color: #475569;">
                        <strong>Website:</strong> <a href="https://www.magnacode.org" style="color: #3b82f6; text-decoration: none;">www.magnacode.org</a>
                    </p>
                </div>
            </div>
            <div style="background-color: #1f2937; color: #d1d5db; text-align: center; padding: 30px;">
                <h3 style="color: #f59e0b; margin: 0 0 15px 0; font-size: 20px;">
                    Magna Endocrine Update 2025
                </h3>
                <p style="margin: 5px 0; font-size: 14px;">
                    Healthcare Excellence • Education Innovation
                </p>
                <p style="margin: 5px 0; font-size: 14px;">
                    Organized by Healthcare and Education Foundation
                </p>
                <p style="margin: 15px 0 5px 0; font-size: 12px; color: #9ca3af;">
                    The Chancery Pavilion, Bangalore | September 21-22, 2025
                </p>
                <div style="margin: 20px 0;">
                    <a href="https://www.magnacode.org" style="color: #60a5fa; text-decoration: none; margin: 0 10px;">Website</a>
                    <span style="color: #4b5563;">|</span>
                    <a href="mailto:info@magnacode.org" style="color: #60a5fa; text-decoration: none; margin: 0 10px;">Contact</a>
                    <span style="color: #4b5563;">|</span>
                    <a href="tel:+918480002958" style="color: #60a5fa; text-decoration: none; margin: 0 10px;">Support</a>
                </div>
                <p style="margin: 10px 0 0 0; font-size: 11px; color: #6b7280;">
                    This email was sent to {email} because you registered for Magna Endocrine Update 2025.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    return html_content

# Routes
@router.get("/fetch-id")
async def fetch_guest_id(phone: str):
    """Fetch guest ID by phone number."""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["Phone"] == phone), None)
        if guest:
            return JSONResponse({"success": True, "guest_id": guest["ID"]})
        return JSONResponse(
            {"success": False, "message": "Wrong mobile number"},
            status_code=404,
        )
    except Exception as e:
        logger.error(f"Fetch guest ID error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": "An error occurred"},
            status_code=500,
        )

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Guest login page"""
    return templates.TemplateResponse(
        "guest/login.html",
        {
            "request": request,
            "active_page": "login"
        }
    )

@router.post("/login")
async def login(
    request: Request,
    guest_id: str = Form(...),
    phone: str = Form(...)
):
    """Process guest login"""
    try:
        # Find guest in database
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if not guest:
            return templates.TemplateResponse(
                "guest/login.html",
                {
                    "request": request,
                    "error": "Invalid guest ID",
                    "active_page": "login"
                }
            )
        
        # Verify phone number
        if guest["Phone"] != phone:
            return templates.TemplateResponse(
                "guest/login.html",
                {
                    "request": request,
                    "error": "Invalid phone number",
                    "active_page": "login"
                }
            )
        
        # Check faculty status
        has_faculty = is_faculty(guest["ID"])
        
        # Create session
        session_id = auth_service.create_session(
            guest["ID"],
            "faculty" if has_faculty else "guest"
        )
        
        # Update faculty login time if applicable
        if has_faculty:
            update_faculty_login(guest["ID"])
        
        # Redirect with session cookie
        response = RedirectResponse(
            url="/guest/profile",
            status_code=303
        )
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=43200  # 12 hours
        )
        
        return response
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return templates.TemplateResponse(
            "guest/login.html",
            {
                "request": request,
                "error": "An error occurred during login",
                "active_page": "login"
            }
        )

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, guest: Dict = Depends(get_current_guest)):
    """Guest profile page"""
    try:
        # Check if guest has faculty access
        guest["is_faculty"] = is_faculty(guest["ID"])

        # Generate QR code if it doesn't exist
        qr_code_path = qr_service.generate_guest_badge_qr(guest["ID"])
        if qr_code_path:
            guest["qr_code_url"] = f"/static/{qr_code_path}"
        else:
            guest["qr_code_base64"] = generate_qr_base64(f"GUEST:{guest['ID']}")
        
        # Get presentations
        import csv
        presentations = []
        
        if os.path.exists(PRESENTATIONS_CSV):
            with open(PRESENTATIONS_CSV, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["guest_id"] == guest["ID"]:
                        row["file_url"] = f"/static/uploads/presentations/{row['file_path']}"
                        presentations.append(row)

        # Get messages
        guest_messages = []
        if os.path.exists(MESSAGES_CSV):
            with open(MESSAGES_CSV, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row.get("guest_id") == guest["ID"]:
                        guest_messages.append(row)
        
        # *** UPDATED: Get journey details using synchronized service ***
        journey_service = create_journey_service(config)
        journey_data = journey_service.get_journey_data(guest["ID"])

        # Prepare journey data for template
        inward_journey = {}
        outward_journey = {}

        if journey_data:
            inward_journey = {
                "date": journey_data.get("inward_date"),
                "origin": journey_data.get("inward_origin"),
                "destination": journey_data.get("inward_destination"),
                "remarks": journey_data.get("inward_remarks"),
            }

            outward_journey = {
                "date": journey_data.get("outward_date"),
                "origin": journey_data.get("outward_origin"),
                "destination": journey_data.get("outward_destination"),
                "remarks": journey_data.get("outward_remarks"),
            }
        
        # Check for photo
        photo_path = os.path.join(PROFILE_PHOTOS_DIR, f"{guest['ID']}.jpg")
        if os.path.exists(photo_path):
            guest["photo_url"] = f"/static/uploads/profile_photos/{guest['ID']}.jpg"
        
        return templates.TemplateResponse(
            "guest/profile.html",
            {
                "request": request,
                "guest": guest,
                "presentations": presentations,
                "guest_messages": guest_messages,
                "inward_journey": inward_journey,
                "outward_journey": outward_journey,
                "user_role": "faculty" if guest["is_faculty"] else "guest",
                "active_page": "profile"
            }
        )
    except Exception as e:
        logger.error(f"Error loading profile page: {str(e)}")
        raise HTTPException(status_code=500, detail="Error loading profile")

# Guest badge download
@router.get("/download-badge")
async def download_guest_badge(request: Request, guest: Dict = Depends(get_current_guest)):
    """Download guest's own badge"""
    if not validate_guest_data(guest):
        raise HTTPException(status_code=400, detail="Invalid guest data")

    badge_image = create_magnacode_badge_working(guest)

    img_byte_array = io.BytesIO()
    badge_image.save(img_byte_array, format='PNG', dpi=(300, 300))
    img_byte_array.seek(0)

    return StreamingResponse(
        img_byte_array,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="MAGNACODE2025_MyBadge_{guest["ID"]}.png"'
        }
    )

# Guest QR code
@router.get("/qr-code/{guest_id}")
async def get_qr_code(guest_id: str, guest: Dict = Depends(get_current_guest)):
    """Get QR code for guest"""
    if guest["ID"] != guest_id:
        raise HTTPException(status_code=403, detail="Access denied")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(f"MAGNACODE2025:{guest_id}")
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1e3a8a", back_color="white")
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)

    return StreamingResponse(
        io.BytesIO(img_buffer.getvalue()),
        media_type="image/png",
        headers={"Cache-Control": "max-age=3600"}
    )

@router.get("/presentations", response_class=HTMLResponse)
async def presentations_page(request: Request, guest: Dict = Depends(get_current_guest)):
    """Page showing guest presentations"""
    try:
        guest["is_faculty"] = is_faculty(guest["ID"])

        import csv
        presentations = []

        if os.path.exists(PRESENTATIONS_CSV):
            with open(PRESENTATIONS_CSV, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["guest_id"] == guest["ID"]:
                        row["file_url"] = f"/static/uploads/presentations/{row['file_path']}"
                        presentations.append(row)

        return templates.TemplateResponse(
            "guest/presentations.html",
            {
                "request": request,
                "guest": guest,
                "presentations": presentations,
                "user_role": "faculty" if guest["is_faculty"] else "guest",
                "active_page": "presentations",
            },
        )
    except Exception as e:
        logger.error(f"Error loading presentations page: {str(e)}")
        raise HTTPException(status_code=500, detail="Error loading presentations")

@router.post("/upload-presentation")
async def upload_presentation(
    request: Request,
    guest: Dict = Depends(get_current_guest),
    title: str = Form(...),
    description: Optional[str] = Form(""),
    file: UploadFile = File(...)
):
    """Upload a presentation file"""
    try:
        # Validate file extension
        import os
        ext = os.path.splitext(file.filename)[1].lower()
        
        if ext not in ALLOWED_PRESENTATION_EXTENSIONS:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "File type not allowed. Please upload a PDF, PowerPoint, Word document, or video file."
                }
            )
        
        # Create unique filename
        timestamp = int(datetime.now().timestamp())
        safe_title = "".join([c if c.isalnum() else "_" for c in title])
        filename = f"{guest['ID']}_{timestamp}_{safe_title}{ext}"
        file_path = os.path.join(PRESENTATIONS_DIR, filename)
        
        # Save file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Determine file type category
        file_type = "doc"
        if ext in [".pdf"]:
            file_type = "pdf"
        elif ext in [".ppt", ".pptx"]:
            file_type = "ppt"
        elif ext in [".mp4", ".avi", ".webm"]:
            file_type = "video"
        
        # Add to database
        import csv
        
        # Ensure file exists
        if not os.path.exists(PRESENTATIONS_CSV):
            with open(PRESENTATIONS_CSV, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["id", "guest_id", "title", "description", "file_path", "file_type", "upload_date"])
        
        with open(PRESENTATIONS_CSV, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=["id", "guest_id", "title", "description", "file_path", "file_type", "upload_date"])
            writer.writerow({
                "id": str(uuid.uuid4()),
                "guest_id": guest["ID"],
                "title": title,
                "description": description,
                "file_path": filename,
                "file_type": file_type,
                "upload_date": datetime.now().isoformat()
            })
        
        return JSONResponse(
            content={"success": True, "message": "Presentation uploaded successfully."}
        )
    except Exception as e:
        logger.error(f"Error uploading presentation: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error uploading presentation: {str(e)}"}
        )

@router.post("/update-journey")
async def update_journey(
    request: Request,
    guest: Dict = Depends(get_current_guest),
    inward_date: Optional[str] = Form(None),
    inward_origin: Optional[str] = Form(None),
    inward_destination: Optional[str] = Form(None),
    inward_remarks: Optional[str] = Form(None),
    outward_date: Optional[str] = Form(None),
    outward_origin: Optional[str] = Form(None),
    outward_destination: Optional[str] = Form(None),
    outward_remarks: Optional[str] = Form(None)
):
    """Update journey details - synchronized version"""
    try:
        journey_service = create_journey_service(config)

        journey_data = {
            "inward_date": inward_date or "",
            "inward_origin": inward_origin or "",
            "inward_destination": inward_destination or "",
            "inward_remarks": inward_remarks or "",
            "outward_date": outward_date or "",
            "outward_origin": outward_origin or "",
            "outward_destination": outward_destination or "",
            "outward_remarks": outward_remarks or "",
        }

        success = journey_service.update_journey_from_guest(guest["ID"], journey_data)

        if success:
            return JSONResponse(
                content={"success": True, "message": "Journey details updated successfully."}
            )
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "Failed to update journey details."}
            )
    except Exception as e:
        logger.error(f"Error updating journey: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error updating journey: {str(e)}"}
        )

@router.post("/send-message")
async def send_message(
    request: Request,
    guest: Dict = Depends(get_current_guest),
    message: str = Form(...)
):
    """Send a message to administrators"""
    try:
        import csv
        
        if not message.strip():
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Message cannot be empty."}
            )
        
        # Ensure file exists
        fieldnames = ["id", "guest_id", "message", "timestamp", "read", "response", "response_timestamp"]
        if not os.path.exists(MESSAGES_CSV):
            with open(MESSAGES_CSV, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(fieldnames)

        # Add message
        with open(MESSAGES_CSV, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writerow({
                "id": str(uuid.uuid4()),
                "guest_id": guest["ID"],
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "read": "False",
                "response": "",
                "response_timestamp": ""
            })
        
        return JSONResponse(
            content={"success": True, "message": "Message sent successfully."}
        )
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error sending message: {str(e)}"}
        )

@router.post("/update-profile")
async def update_profile(
    request: Request,
    guest: Dict = Depends(get_current_guest),
    email: str = Form(...),
    phone: str = Form(...),
    kmc_number: str = Form("")
):
    """Update guest profile information"""
    try:
        # Validate phone number
        if not phone.isdigit() or len(phone) != 10:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Phone number must be exactly 10 digits."}
            )
        
        # Validate email
        if "@" not in email or "." not in email:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Invalid email format."}
            )
        
        # Update guest
        guests = guests_db.read_all()
        updated = False

        for g in guests:
            if g["ID"] == guest["ID"]:
                g["Email"] = email
                g["Phone"] = phone
                g["KMCNumber"] = kmc_number
                updated = True
                break
        
        if updated:
            guests_db.write_all(guests)
            return JSONResponse(
                content={"success": True, "message": "Profile updated successfully."}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found."}
            )
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error updating profile: {str(e)}"}
        )

@router.post("/upload-photo")
async def upload_photo(
    request: Request,
    guest: Dict = Depends(get_current_guest),
    photo: UploadFile = File(...)
):
    """Upload profile photo"""
    try:
        # Validate file extension
        import os
        ext = os.path.splitext(photo.filename)[1].lower()
        
        if ext not in ALLOWED_PHOTO_EXTENSIONS:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "File type not allowed. Please upload a JPG, JPEG, PNG, or GIF file."
                }
            )
        
        # Save file
        file_path = os.path.join(PROFILE_PHOTOS_DIR, f"{guest['ID']}.jpg")
        
        with open(file_path, "wb") as f:
            content = await photo.read()
            f.write(content)
        
        return JSONResponse(
            content={"success": True, "message": "Profile photo updated successfully."}
        )
    except Exception as e:
        logger.error(f"Error uploading photo: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error uploading photo: {str(e)}"}
        )

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Guest registration page"""
    return templates.TemplateResponse(
        "guest_registration.html",
        {
            "request": request,
            "active_page": "register"
        }
    )

@router.post("/register", response_class=JSONResponse)
async def register_guest(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    email: str = Form(None),
    guest_role: str = Form(...),
    registration_type: str = Form(...),
    existing_id: str = Form(None),
    kmc_number: str = Form("")
):
    """Process guest registration"""
    try:
        # Validate phone number
        if not phone.isdigit() or len(phone) != 10:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Phone number must be exactly 10 digits"}
            )
        
        # Validate email if provided
        if email and ("@" not in email or "." not in email):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Invalid email format"}
            )

        guests = guests_db.read_all()

        # Check for duplicate phone number
        if any(g.get("Phone") == phone for g in guests):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "This phone number is already registered."}
            )

        # Check for duplicate KMC number if provided
        if kmc_number and any(g.get("KMCNumber") == kmc_number for g in guests):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "This KMC number is already registered."}
            )

        # Generate or use existing ID
        if registration_type == "existing" and existing_id:
            guest_id = existing_id
            # Verify ID exists
            if not any(g["ID"] == guest_id for g in guests):
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "Invalid registration ID"}
                )
        else:
            existing_ids = [g["ID"] for g in guests]
            guest_id = generate_unique_id(existing_ids, 4)
        
        # Create guest record
        guest = {
            "ID": guest_id,
            "Name": name,
            "Phone": phone,
            "Email": email or "",
            "GuestRole": guest_role,
            "KMCNumber": kmc_number,
            "RegistrationDate": datetime.now().strftime("%Y-%m-%d"),
            "DailyAttendance": "False"
        }
        
        # Add to database
        guests.append(guest)
        guests_db.write_all(guests)

        # Generate QR code for the new guest
        try:
            qr_service.generate_guest_badge_qr(guest_id)
        except Exception as qr_error:
            logger.warning(f"Failed to generate QR code for guest {guest_id}: {str(qr_error)}")

        # Send confirmation email (with enhanced template)
        email_sent = False
        if email:
            try:
                # Test email connection first
                if email_service.test_connection():
                    # Create complete guest data for email template
                    guest_data = {
                        "ID": guest_id,
                        "Name": name,
                        "Email": email,
                        "Phone": phone,
                        "GuestRole": guest_role,
                        "KMCNumber": kmc_number,
                        "RegistrationDate": datetime.now().strftime("%B %d, %Y")
                    }

                    # Create enhanced email content
                    email_content = create_registration_email_content(guest_data)

                    email_sent = email_service.send_email(
                        email,
                        "🎉 Registration Confirmed - Magna Endocrine Update 2025",
                        email_content
                    )

                    if email_sent:
                        logger.info(f"Enhanced registration confirmation email sent to {email}")
                    else:
                        logger.error(f"Failed to send registration email to {email}")
                else:
                    logger.error("Email connection test failed, skipping email send")

            except Exception as mail_error:
                logger.error(f"Email sending error: {mail_error}")

        return JSONResponse(
            content={
                "success": True,
                "message": "Registration successful",
                "guest_id": guest_id,
                "name": name,
                "role": guest_role
            }
        )
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Registration failed: {str(e)}"}
        )
    

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

    # --- ADJUST QR CODE POSITION ---
    qr_size = 300
    qr_padding = 20
    qr_x = 100
    qr_y = 600

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=1)
    qr.add_data(f"MAGNACODE2025:{guest.get('ID', 'UNKNOWN')}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=navy_blue, back_color="white")
    try:
        qr_resized = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    except AttributeError:
        qr_resized = qr_img.resize((qr_size, qr_size))
    badge.paste(qr_resized, (qr_x + qr_padding, qr_y + qr_padding))

    # --- ADJUST GUEST INFO POSITION ---
    info_x = qr_x + qr_size + 80
    info_width = width_px - info_x - 100
    info_y = qr_y + 20

    guest_name = guest.get('Name', 'Unknown Guest')
    role = guest.get('GuestRole', 'Event')
    if role in ['Delegates', 'Faculty'] and guest_name and not any(prefix in guest_name.upper() for prefix in ['DR.', 'PROF.', 'MR.', 'MS.', 'MRS.']):
        guest_name = f"Dr. {guest_name}"

    # Guest Name
    name_y = info_y
    name_height = 100
    if len(guest_name) > 20:
        words = guest_name.split(' ')
        if len(words) > 1:
            mid = len(words) // 2
            line1 = ' '.join(words[:mid])
            line2 = ' '.join(words[mid:])
            try:
                draw.text((info_x + info_width//2, name_y + 35), line1, fill=navy_blue, anchor="mm", font_size=35)
                draw.text((info_x + info_width//2, name_y + 75), line2, fill=navy_blue, anchor="mm", font_size=35)
            except TypeError:
                draw.text((info_x + info_width//2, name_y + 35), line1, fill=navy_blue, anchor="mm")
                draw.text((info_x + info_width//2, name_y + 75), line2, fill=navy_blue, anchor="mm")
        else:
            try:
                draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm", font_size=35)
            except TypeError:
                draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm")
    else:
        try:
            draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm", font_size=40)
        except TypeError:
            draw.text((info_x + info_width//2, name_y + name_height//2), guest_name, fill=navy_blue, anchor="mm")

    # Guest Role
    role_y = name_y + name_height + 20
    role_height = 60
    try:
        draw.text((info_x + info_width//2, role_y + role_height//2), role.upper(), fill='black', anchor="mm", font_size=30)
    except TypeError:
        draw.text((info_x + info_width//2, role_y + role_height//2), role.upper(), fill='black', anchor="mm")

    # Guest ID
    id_y = role_y + role_height + 20
    id_height = 60
    guest_id = guest.get('ID', 'UNKNOWN')
    try:
        draw.text((info_x + info_width//2, id_y + id_height//2), f"ID: {guest_id}", fill='black', anchor="mm", font_size=30)
    except TypeError:
        draw.text((info_x + info_width//2, id_y + id_height//2), f"ID: {guest_id}", fill='black', anchor="mm")

    return badge

def create_magnacode_badge(guest: dict) -> Image.Image:
    """Backward compatibility wrapper."""
    return create_magnacode_badge_working(guest)



def validate_guest_data(guest: dict) -> bool:
    required_fields = ['ID', 'Name', 'GuestRole']
    for field in required_fields:
        if not guest.get(field):
            return False
    valid_roles = ['Delegates', 'Faculty', 'Sponsor', 'Event']
    if guest['GuestRole'] not in valid_roles:
        return False
    return True
