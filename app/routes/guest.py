# app/routes/guest.py
from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict
import os
import logging
import uuid
from datetime import datetime
import shutil

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
guests_db = CSVDatabase(
    config.get('DATABASE', 'CSVPath'),
    config.get('DATABASE', 'BackupDir')
)
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
        
        # Get journey details
        journey_data = None
        if os.path.exists(JOURNEY_CSV):
            with open(JOURNEY_CSV, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["guest_id"] == guest["ID"]:
                        journey_data = row
                        break
        
        # Check for photo
        photo_path = os.path.join(PROFILE_PHOTOS_DIR, f"{guest['ID']}.jpg")
        if os.path.exists(photo_path):
            guest["photo_url"] = f"/static/uploads/profile_photos/{guest['ID']}.jpg"
        
        # Prepare journey data for template
        inward_journey = {}
        outward_journey = {}
        
        if journey_data:
            inward_journey = {
                "date": journey_data.get("inward_date"),
                "origin": journey_data.get("inward_origin"),
                "destination": journey_data.get("inward_destination"),
                "remarks": journey_data.get("inward_remarks")
            }
            
            outward_journey = {
                "date": journey_data.get("outward_date"),
                "origin": journey_data.get("outward_origin"),
                "destination": journey_data.get("outward_destination"),
                "remarks": journey_data.get("outward_remarks")
            }
        
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
    """Update journey details"""
    try:
        import csv
        
        journey_data = {
            "inward_date": inward_date,
            "inward_origin": inward_origin,
            "inward_destination": inward_destination,
            "inward_remarks": inward_remarks,
            "outward_date": outward_date,
            "outward_origin": outward_origin,
            "outward_destination": outward_destination,
            "outward_remarks": outward_remarks
        }
        
        # Check if journey data exists
        journeys = []
        journey_exists = False
        fieldnames = ["guest_id", "inward_date", "inward_origin", "inward_destination", 
                     "inward_remarks", "outward_date", "outward_origin", 
                     "outward_destination", "outward_remarks", "updated_at"]
        
        if os.path.exists(JOURNEY_CSV):
            with open(JOURNEY_CSV, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["guest_id"] == guest["ID"]:
                        # Update existing journey
                        row.update(journey_data)
                        row["updated_at"] = datetime.now().isoformat()
                        journey_exists = True
                    journeys.append(row)
        
        if not journey_exists:
            # Create new journey record
            journey_data["guest_id"] = guest["ID"]
            journey_data["updated_at"] = datetime.now().isoformat()
            journeys.append(journey_data)
        
        # Ensure file directory exists
        os.makedirs(os.path.dirname(JOURNEY_CSV), exist_ok=True)
        
        # Write to file
        with open(JOURNEY_CSV, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(journeys)
        
        return JSONResponse(
            content={"success": True, "message": "Journey details updated successfully."}
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
    
