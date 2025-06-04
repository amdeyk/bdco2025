# app/routes/faculty.py - Corrected implementation
from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from typing import Dict, List, Optional
import logging
import os
import shutil
from datetime import datetime, timedelta
import jwt
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext

from app.models.faculty import Faculty, FacultyProfile, Presentation, JourneyDetails
from app.services.enhanced_csv_db import EnhancedCSVDatabase
from app.config import Config
from app.templates import templates

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/faculty", tags=["faculty"])

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="faculty/token")
config = Config()

# Initialize database
db = EnhancedCSVDatabase(
    config.get('DATABASE', 'CSVPath'),
    config.get('DATABASE', 'BackupDir')
)

# JWT settings
SECRET_KEY = config.get('SECURITY', 'SecretKey')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict):
    """Create JWT token for faculty authentication"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_faculty(token: str = Depends(oauth2_scheme)) -> FacultyProfile:
    """Get current faculty from JWT token"""
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        faculty_id: str = payload.get("sub")
        if faculty_id is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception
        
    # Get faculty from database
    faculty_data = db.read_all()
    faculty = next((f for f in faculty_data if f["id"] == faculty_id), None)
    if faculty is None:
        raise credentials_exception
    return FacultyProfile(**faculty)

@router.get("/dashboard", response_class=HTMLResponse)
async def faculty_dashboard(request: Request):
    """Faculty dashboard for managing presentations and schedules"""
    try:
        # Get faculty data
        faculty_db = EnhancedCSVDatabase(config.get('DATABASE', 'CSVPath'), config.get('DATABASE', 'BackupDir'))
        faculty_members = faculty_db.read_all()
        
        return templates.TemplateResponse(
            "faculty/dashboard.html",
            {
                "request": request,
                "faculty_members": faculty_members,
                "active_page": "faculty_dashboard"
            }
        )
    except Exception as e:
        logger.error(f"Error loading faculty dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Error loading faculty dashboard")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render faculty login page"""
    return templates.TemplateResponse(
        "faculty/login.html",
        {"request": request}
    )

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate faculty and return JWT token"""
    faculty_data = db.read_all()
    faculty = next(
        (f for f in faculty_data 
         if f["email"] == form_data.username and 
         pwd_context.verify(form_data.password, f["password"])),
        None
    )
    
    if not faculty:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": faculty["id"]}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_faculty: FacultyProfile = Depends(get_current_faculty)
):
    """Render faculty profile page"""
    return templates.TemplateResponse(
        "faculty/profile.html",
        {
            "request": request,
            "faculty": current_faculty
        }
    )

@router.get("/presentations", response_class=HTMLResponse)
async def presentations_page(
    request: Request,
    current_faculty: FacultyProfile = Depends(get_current_faculty)
):
    """View faculty presentations"""
    return templates.TemplateResponse(
        "faculty/presentations.html",
        {
            "request": request,
            "faculty": current_faculty,
            "active_page": "faculty_presentations",
        },
    )

@router.get("/journey", response_class=HTMLResponse)
async def journey_page(
    request: Request,
    current_faculty: FacultyProfile = Depends(get_current_faculty)
):
    """View faculty journey details"""
    return templates.TemplateResponse(
        "faculty/journey.html",
        {
            "request": request,
            "faculty": current_faculty,
            "active_page": "faculty_journey",
        },
    )

@router.get("/messages", response_class=HTMLResponse)
async def messages_page(
    request: Request,
    current_faculty: FacultyProfile = Depends(get_current_faculty)
):
    """Placeholder page for faculty messages"""
    return templates.TemplateResponse(
        "faculty/messages.html",
        {
            "request": request,
            "faculty": current_faculty,
            "active_page": "faculty_messages",
        },
    )

@router.post("/profile/update")
async def update_profile(
    request: Request,
    email: str = Form(...),
    phone: str = Form(...),
    photo: Optional[UploadFile] = File(None),
    current_faculty: FacultyProfile = Depends(get_current_faculty)
):
    """Update faculty profile information"""
    # Update basic info
    faculty_data = db.read_all()
    faculty_idx = next(
        (i for i, f in enumerate(faculty_data) 
         if f["id"] == current_faculty.id),
        None
    )
    
    if faculty_idx is None:
        raise HTTPException(status_code=404, detail="Faculty not found")
    
    # Update profile photo if provided
    if photo:
        photo_dir = os.path.join(
            config.get('PATHS', 'StaticDir'),
            "uploads/profile_photos"
        )
        os.makedirs(photo_dir, exist_ok=True)
        
        file_ext = os.path.splitext(photo.filename)[1]
        photo_path = os.path.join(
            photo_dir,
            f"{current_faculty.id}{file_ext}"
        )
        
        with open(photo_path, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)
            
        faculty_data[faculty_idx]["photo_path"] = f"uploads/profile_photos/{current_faculty.id}{file_ext}"
    
    # Update other fields
    faculty_data[faculty_idx].update({
        "email": email,
        "phone": phone,
        "updated_at": datetime.now().isoformat()
    })
    
    db.write_all(faculty_data)
    return {"message": "Profile updated successfully"}

@router.post("/presentation/upload")
async def upload_presentation(
    title: str = Form(...),
    description: str = Form(...),
    session_type: str = Form(...),
    file: UploadFile = File(...),
    current_faculty: FacultyProfile = Depends(get_current_faculty)
):
    """Upload faculty presentation"""
    # Validate file type
    allowed_types = {
        ".pdf": "application/pdf",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".mp4": "video/mp4"
    }
    
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="File type not allowed"
        )
    
    # Save file
    pres_dir = os.path.join(
        config.get('PATHS', 'StaticDir'),
        "uploads/presentations"
    )
    os.makedirs(pres_dir, exist_ok=True)
    
    file_path = os.path.join(
        pres_dir,
        f"{current_faculty.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}{file_ext}"
    )
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Update faculty record
    faculty_data = db.read_all()
    faculty_idx = next(
        (i for i, f in enumerate(faculty_data) 
         if f["id"] == current_faculty.id),
        None
    )
    
    if faculty_idx is None:
        raise HTTPException(status_code=404, detail="Faculty not found")
    
    # Add presentation to faculty record
    presentations = faculty_data[faculty_idx].get("presentations", [])
    presentations.append({
        "title": title,
        "description": description,
        "file_path": f"uploads/presentations/{os.path.basename(file_path)}",
        "file_type": file_ext[1:],
        "upload_date": datetime.now().isoformat(),
        "session_type": session_type
    })
    
    faculty_data[faculty_idx]["presentations"] = presentations
    faculty_data[faculty_idx]["updated_at"] = datetime.now().isoformat()
    
    db.write_all(faculty_data)
    return {"message": "Presentation uploaded successfully"}

@router.post("/journey/update")
async def update_journey_details(
    arrival_date: datetime = Form(...),
    departure_date: datetime = Form(...),
    origin_city: str = Form(...),
    destination_city: str = Form(...),
    remarks: Optional[str] = Form(None),
    current_faculty: FacultyProfile = Depends(get_current_faculty)
):
    """Update faculty journey details"""
    faculty_data = db.read_all()
    faculty_idx = next(
        (i for i, f in enumerate(faculty_data) 
         if f["id"] == current_faculty.id),
        None
    )
    
    if faculty_idx is None:
        raise HTTPException(status_code=404, detail="Faculty not found")
    
    journey_details = {
        "arrival_date": arrival_date.isoformat(),
        "departure_date": departure_date.isoformat(),
        "origin_city": origin_city,
        "destination_city": destination_city,
        "remarks": remarks
    }
    
    faculty_data[faculty_idx]["journey_details"] = journey_details
    faculty_data[faculty_idx]["updated_at"] = datetime.now().isoformat()
    
    db.write_all(faculty_data)
    return {"message": "Journey details updated successfully"}