# app/routes/guest.py
from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict
import os
import logging
import uuid
from datetime import datetime
import shutil
import io
import base64
import qrcode
from PIL import Image, ImageDraw

from app.services.qr_service import QRService
from app.services.journey_sync import create_journey_service

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
    """Generate QR code as base64 string with MAGNACODE styling"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(f"MAGNACODE2025:{data}")
        qr.make(fit=True)

        img = qr.make_image(fill_color="#1e3a8a", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        return ""

# Routes
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
        messages = []
        if os.path.exists(MESSAGES_CSV):
            with open(MESSAGES_CSV, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row.get("guest_id") == guest["ID"]:
                        messages.append(row)
        
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
                "messages": messages,
                "inward_journey": inward_journey,
                "outward_journey": outward_journey,
                "user_role": "faculty" if guest["is_faculty"] else "guest",
                "active_page": "profile"
            }
        )
    except Exception as e:
        logger.error(f"Error loading profile page: {str(e)}")
        raise HTTPException(status_code=500, detail="Error loading profile")

# Add route to generate QR code on demand
@router.get("/qr-code/{guest_id}")
async def get_qr_code(guest_id: str, guest: Dict = Depends(get_current_guest)):
    """Generate QR code for guest"""
    try:
        # Verify guest can only access their own QR code
        if guest["ID"] != guest_id:
            raise HTTPException(status_code=403, detail="Access denied")

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(f"MAGNACODE2025:GUEST:{guest_id}")
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
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating QR code")

@router.get("/download-badge")
async def download_guest_badge(request: Request, guest: Dict = Depends(get_current_guest)):
    """Allow guest to download their own corporate badge"""
    try:
        badge_image = create_corporate_badge(guest)

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

    except Exception as e:
        logger.error(f"Error downloading guest badge: {str(e)}")
        raise HTTPException(status_code=500, detail="Error downloading badge")

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
    phone: str = Form(...)
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
    existing_id: str = Form(None)
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
        
        # Generate or use existing ID
        if registration_type == "existing" and existing_id:
            guest_id = existing_id
            # Verify ID exists
            guests = guests_db.read_all()
            if not any(g["ID"] == guest_id for g in guests):
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "Invalid registration ID"}
                )
        else:
            guest_id = str(uuid.uuid4())[:8].upper()
        
        # Create guest record
        guest = {
            "ID": guest_id,
            "Name": name,
            "Phone": phone,
            "Email": email or "",
            "GuestRole": guest_role,
            "RegistrationDate": datetime.now().strftime("%Y-%m-%d"),
            "DailyAttendance": "False"
        }
        
        # Add to database
        guests = guests_db.read_all()
        guests.append(guest)
        guests_db.write_all(guests)

        # Generate QR code for the new guest
        try:
            qr_service.generate_guest_badge_qr(guest_id)
        except Exception as qr_error:
            logger.warning(f"Failed to generate QR code for guest {guest_id}: {str(qr_error)}")
        
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


def create_corporate_badge(guest: dict) -> Image.Image:
    """Create corporate badge matching the admin version"""
    try:
        dpi = 300
        width_px = int(90 * dpi / 25.4)
        height_px = int(140 * dpi / 25.4)

        badge = Image.new('RGB', (width_px, height_px), '#ffffff')
        draw = ImageDraw.Draw(badge)

        primary_blue = '#1e3a8a'
        accent_orange = '#f97316'
        light_blue = '#e0f2fe'
        light_gray = '#f8fafc'
        dark_gray = '#334155'

        header_height = int(height_px * 0.25)
        for i in range(header_height):
            alpha = 1 - (i / header_height * 0.3)
            color_val = int(30 + (138-30) * alpha)
            draw.line([(0, i), (width_px, i)], fill=f'#{color_val:02x}{58:02x}{138:02x}')

        try:
            draw.text((width_px//2, 50), "MAGNACODE 2025", fill='white', anchor="mm", font_size=52)
            draw.text((width_px//2, 110), "Healthcare and Education Foundation", fill='white', anchor="mm", font_size=26)
            draw.text((width_px//2, 160), "21st & 22nd September 2025", fill='#fbbf24', anchor="mm", font_size=22)
            draw.text((width_px//2, 190), "Bangalore", fill='white', anchor="mm", font_size=20)
        except TypeError:
            draw.text((50, 50), "MAGNACODE 2025", fill='white')
            draw.text((30, 90), "Healthcare and Education Foundation", fill='white')
            draw.text((50, 130), "21st & 22nd September 2025", fill='#fbbf24')
            draw.text((80, 160), "Bangalore", fill='white')

        content_y = header_height + 40
        margin = 50

        qr_size = 220
        qr_box_padding = 25
        qr_total_size = qr_size + (qr_box_padding * 2)
        qr_x = margin
        qr_y = content_y + 80

        shadow_offset = 5
        draw.rectangle([(qr_x + shadow_offset, qr_y + shadow_offset), (qr_x + qr_total_size + shadow_offset, qr_y + qr_total_size + shadow_offset)], fill='#00000020')
        draw.rectangle([(qr_x, qr_y), (qr_x + qr_total_size, qr_y + qr_total_size)], fill='white', outline=primary_blue, width=4)

        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=1)
        qr.add_data(f"MAGNACODE2025:GUEST:{guest['ID']}")
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color=primary_blue, back_color="white")
        qr_resized = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        badge.paste(qr_resized, (qr_x + qr_box_padding, qr_y + qr_box_padding))
        draw.text((qr_x + qr_total_size//2, qr_y + qr_total_size + 20), "Quick Check-in", fill=dark_gray, anchor="mm")

        info_x = qr_x + qr_total_size + 40
        info_width = width_px - info_x - margin
        info_y = content_y + 40

        id_height = 55
        draw.rectangle([(info_x, info_y), (width_px - margin, info_y + id_height)], fill=accent_orange)
        draw.rectangle([(info_x, info_y), (width_px - margin, info_y + id_height)], fill='none', outline='#dc2626', width=2)
        draw.text((info_x + info_width//2, info_y + id_height//2), f"ID: {guest['ID']}", fill='white', anchor="mm")

        name_y = info_y + id_height + 20
        name = guest.get('Name', 'N/A')
        if name and name != 'N/A':
            role = guest.get('GuestRole', '')
            if role in ['Delegates', 'Faculty', 'OrgBatch']:
                if not any(prefix in name.upper() for prefix in ['DR.', 'PROF.', 'MR.', 'MS.', 'MRS.']):
                    name = f"Dr. {name}"

        name_height = 85
        draw.rectangle([(info_x, name_y), (width_px - margin, name_y + name_height)], fill=light_blue, outline=primary_blue, width=3)

        if len(name) > 18:
            words = name.split(' ')
            if len(words) > 1:
                mid = len(words) // 2
                line1 = ' '.join(words[:mid])
                line2 = ' '.join(words[mid:])
                draw.text((info_x + info_width//2, name_y + 25), line1, fill=primary_blue, anchor="mm")
                draw.text((info_x + info_width//2, name_y + 60), line2, fill=primary_blue, anchor="mm")
            else:
                draw.text((info_x + info_width//2, name_y + name_height//2), name, fill=primary_blue, anchor="mm")
        else:
            draw.text((info_x + info_width//2, name_y + name_height//2), name, fill=primary_blue, anchor="mm")

        role = guest.get('GuestRole', 'Guest')
        role_colors = {
            'Delegates': '#059669',
            'Faculty': '#dc2626',
            'Sponsors': '#d97706',
            'Staff': '#6b7280',
            'OrgBatch': '#7c3aed',
            'Roots': '#0891b2',
            'Event': '#ea580c'
        }
        role_color = role_colors.get(role, '#6b7280')

        role_y = name_y + name_height + 15
        role_height = 45
        draw.rectangle([(info_x, role_y), (width_px - margin, role_y + role_height)], fill=role_color)
        draw.text((info_x + info_width//2, role_y + role_height//2), role.upper(), fill='white', anchor="mm")

        contact_y = role_y + role_height + 20
        phone = guest.get('Phone', '')
        if phone:
            if len(phone) == 10:
                formatted_phone = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
            else:
                formatted_phone = phone
            draw.text((info_x + 10, contact_y), f"📞 {formatted_phone}", fill=dark_gray)
            contact_y += 35

        if guest.get('Organization'):
            org = guest['Organization']
            if len(org) > 22:
                org = org[:19] + "..."
            draw.text((info_x + 10, contact_y), f"🏢 {org}", fill=dark_gray)
            contact_y += 35

        if guest.get('Batch'):
            draw.text((info_x + 10, contact_y), f"🎓 Batch: {guest['Batch']}", fill=dark_gray)

        footer_y = height_px - 130
        draw.rectangle([(0, footer_y), (width_px, height_px)], fill=light_gray)
        draw.rectangle([(0, footer_y), (width_px, footer_y + 3)], fill=accent_orange)

        footer_texts = [
            "🏨 Venue: The Chancery Pavilion, Bangalore",
            "🔬 Healthcare Excellence • 📚 Education Innovation",
            "🌐 www.magnacode.org | 📧 info@magnacode.org"
        ]

        for i, text in enumerate(footer_texts):
            draw.text((width_px//2, footer_y + 25 + (i * 30)), text, fill=dark_gray, anchor="mm")

        corner_size = 25
        draw.polygon([(width_px - corner_size - 15, 15), (width_px - 15, 15), (width_px - 15, corner_size + 15)], fill=accent_orange)
        draw.polygon([(15, height_px - corner_size - 15), (corner_size + 15, height_px - corner_size - 15), (15, height_px - 15)], fill=accent_orange)
        draw.rectangle([(0, 0), (8, height_px)], fill=accent_orange)
        draw.rectangle([(width_px - 8, 0), (width_px, height_px)], fill=accent_orange)
        draw.rectangle([(0, 0), (width_px - 1, height_px - 1)], fill='none', outline=primary_blue, width=4)

        return badge

    except Exception as e:
        logger.error(f"Error creating guest corporate badge: {str(e)}")
        fallback = Image.new('RGB', (1063, 1654), 'white')
        draw_fb = ImageDraw.Draw(fallback)
        draw_fb.rectangle([(0, 0), (1063, 400)], fill='#1e3a8a')
        draw_fb.text((532, 200), "MAGNACODE 2025", fill='white', anchor="mm")
        draw_fb.text((100, 600), f"Guest: {guest.get('Name', 'N/A')}", fill='black')
        return fallback
    
