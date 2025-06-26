# app/routes/common.py
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import logging
import os

from app.services.csv_db import CSVDatabase
from app.services.auth import auth_service
from app.config import Config
from app.templates import templates
from app.utils.logging_utils import log_activity, log_checkin

from fastapi import Path as FastAPIPath  # Rename FastAPI Path
from pathlib import Path  # Keep pathlib Path for file operations
from fastapi.responses import StreamingResponse
import io
from PIL import Image, ImageDraw
import qrcode


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

@router.post("/check_in_guest", response_class=HTMLResponse)
async def check_in_guest(request: Request, guest_id: str = Form(...)):
    """Look up a guest by ID or phone and mark attendance"""
    try:
        guest_id = guest_id.strip()
        guests = guests_db.read_all()
        guest = next((g for g in guests if g.get("ID") == guest_id or g.get("Phone") == guest_id), None)

        # Prepare recent check-in list
        recent_checkins = []
        checkin_log_path = os.path.join(config.get('PATHS', 'LogsDir'), 'checkin.log')
        if os.path.exists(checkin_log_path):
            try:
                with open(checkin_log_path, 'r') as f:
                    lines = f.readlines()[-10:]
                    for line in lines:
                        parts = line.strip().split(',')
                        if len(parts) >= 4:
                            recent_checkins.append({
                                "guest_id": parts[0],
                                "name": parts[1],
                                "role": parts[2],
                                "timestamp": parts[3]
                            })
            except Exception as e:
                logger.error(f"Error reading check-in log: {str(e)}")

        if not guest:
            return templates.TemplateResponse(
                "check_in.html",
                {
                    "request": request,
                    "error": "Guest not found",
                    "recent_checkins": recent_checkins,
                    "active_page": "check_in"
                }
            )

        # Add photo URL if exists
        photo_path = os.path.join(config.get('PATHS', 'StaticDir'), 'uploads', 'profile_photos', f"{guest['ID']}.jpg")
        if os.path.exists(photo_path):
            guest["photo_url"] = f"/static/uploads/profile_photos/{guest['ID']}.jpg"

        # Mark attendance
        guest["DailyAttendance"] = "True"
        guest["CheckInTime"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        guests_db.write_all(guests)

        # Log the check-in
        log_checkin(guest["ID"], guest.get("Name", ""), guest.get("GuestRole", ""))

        return templates.TemplateResponse(
            "check_in.html",
            {
                "request": request,
                "guest": guest,
                "recent_checkins": recent_checkins,
                "active_page": "check_in"
            }
        )
    except Exception as e:
        logger.error(f"Error checking in guest: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing check-in")

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

# Add these routes to app/routes/common.py

@router.post("/give_badge")
async def give_badge(request: Request, guest_id: str = Form(...)):
    """Mark badge as given to guest"""
    try:
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                # Only allow giving badge if it has been printed
                if guest["BadgePrinted"] != "True":
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "message": "Badge must be printed first"}
                    )
                
                guest["BadgeGiven"] = "True"
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity("Badge", f"Badge given to guest {guest_id}")
            
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

@router.post("/update_journey_status")
async def update_journey_status(request: Request, guest_id: str = Form(...)):
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
            log_activity("Journey", f"Journey details updated for guest {guest_id}")
            
            return JSONResponse(
                content={"success": True, "message": "Journey details marked as updated"}
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
async def complete_journey(request: Request, guest_id: str = Form(...)):
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
            log_activity("Journey", f"Journey completed for guest {guest_id}")
            
            return JSONResponse(
                content={"success": True, "message": "Journey marked as completed"}
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

@router.post("/give_food_coupon")
async def give_food_coupon(request: Request, guest_id: str = Form(...), day: str = Form(...)):
    """Give food coupons to guest for a specific day"""
    try:
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                if day == "1":
                    guest["FoodCouponsDay1"] = "True"
                elif day == "2":
                    guest["FoodCouponsDay2"] = "True"
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
            log_activity("Food", f"Food coupons for day {day} given to guest {guest_id}")
            
            return JSONResponse(
                content={"success": True, "message": f"Food coupons for day {day} marked as given"}
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

@router.post("/give_gift")
async def give_gift(request: Request, guest_id: str = Form(...)):
    """Mark gifts as given to guest"""
    try:
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                guest["GiftsGiven"] = "True"
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity("Gift", f"Conference gifts given to guest {guest_id}")
            
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

# Add to app/routes/common.py

@router.post("/print_badges_bulk")
async def print_badges_bulk(request: Request):
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
            log_activity("Badge", f"Printed badges for {updated_count} guests")
            
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
async def give_badges_bulk(request: Request):
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
            log_activity("Badge", f"Marked {updated_count} badges as given")
            
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

@router.post("/update_journey_status_bulk")
async def update_journey_status_bulk(request: Request):
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
            log_activity("Journey", f"Updated journey details for {updated_count} guests")
            
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
async def complete_journey_bulk(request: Request):
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
            log_activity("Journey", f"Completed journeys for {updated_count} guests")
            
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

@router.post("/give_food_coupons_bulk")
async def give_food_coupons_bulk(request: Request):
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
        
        for guest in guests:
            if guest["ID"] in guest_ids:
                if day == "1":
                    guest["FoodCouponsDay1"] = "True"
                else:
                    guest["FoodCouponsDay2"] = "True"
                updated_count += 1
                
        if updated_count > 0:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity("Food", f"Given day {day} food coupons to {updated_count} guests")
            
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

@router.post("/give_gifts_bulk")
async def give_gifts_bulk(request: Request):
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
        
        for guest in guests:
            if guest["ID"] in guest_ids:
                guest["GiftsGiven"] = "True"
                updated_count += 1
                
        if updated_count > 0:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity("Gift", f"Given gifts to {updated_count} guests")
            
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

@router.get("/api/guest/{guest_id}")
async def get_guest_info(guest_id: str):
    """Get guest information by ID"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if guest:
            return {"success": True, "guest": guest}
        else:
            return {"success": False, "message": "Guest not found"}
    except Exception as e:
        logger.error(f"Error getting guest info: {str(e)}")
        return {"success": False, "message": f"Error getting guest info: {str(e)}"}
    
# Add these routes to app/routes/common.py (before the end of the file)

@router.post("/print_badge")
async def print_badge_common(request: Request, guest_id: str = Form(...)):
    """Mark badge as printed for a guest - global access"""
    try:
        guests = guests_db.read_all()
        updated = False
        
        for guest in guests:
            if guest["ID"] == guest_id:
                # Check if badge is already printed
                if guest.get("BadgePrinted") == "True":
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "message": "Badge has already been printed"}
                    )
                
                guest["BadgePrinted"] = "True"
                updated = True
                break
                
        if updated:
            guests_db.write_all(guests)
            
            # Log this activity
            log_activity(guest_id, "Badge marked as printed")
            
            return JSONResponse(
                content={"success": True, "message": "Badge marked as printed successfully"}
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Guest not found"}
            )
    except Exception as e:
        logger.error(f"Error printing badge: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error printing badge: {str(e)}"}
        )

@router.post("/give_badge")
async def give_badge_common(request: Request, guest_id: str = Form(...)):
    """Mark badge as given to guest - global access"""
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
            log_activity(guest_id, "Badge marked as given")
            
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
async def single_guest_view_common(request: Request, guest_id: str = FastAPIPath(...)):
    """Show single guest details - global access"""
    try:
        logger.info(f"Accessing guest details for ID: {guest_id}")
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if not guest:
            logger.error(f"Guest not found with ID: {guest_id}")
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "message": "Guest not found"
                },
                status_code=404
            )
            
        # Get guest activities (placeholder for now)
        activities = []
        
        return templates.TemplateResponse(
            "single_guest.html",
            {
                "request": request,
                "guest": guest,
                "guest_activities": activities,
                "active_page": "guest_details"
            }
        )
    except Exception as e:
        logger.error(f"Error loading single guest page: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading guest details",
                "error_details": str(e) if config.getboolean('DEFAULT', 'Debug', fallback=False) else None
            },
            status_code=500
        )

@router.get("/generate_badge/{guest_id}")
async def generate_badge_common(guest_id: str = FastAPIPath(...)):
    """Generate badge via common route"""
    guests = guests_db.read_all()
    guest = next((g for g in guests if g["ID"] == guest_id), None)

    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    if not validate_guest_data(guest):
        raise HTTPException(status_code=400, detail="Invalid guest data")

    badge_image = create_magnacode_badge(guest)

    img_byte_array = io.BytesIO()
    badge_image.save(img_byte_array, format='PNG', dpi=(300, 300))
    img_byte_array.seek(0)

    log_activity(guest_id, "Badge generated via common route")

    return StreamingResponse(
        img_byte_array,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="MAGNACODE2025_{guest_id}_badge.png"'
        }
    )



def create_simple_badge_common(guest: dict) -> Image.Image:
    """Create a simple badge design"""
    try:
        # Create a badge with MAGNACODE 2025 theme
        width, height = 800, 600
        badge = Image.new('RGB', (width, height), '#1a237e')  # Dark blue background
        draw = ImageDraw.Draw(badge)
        
        # Draw white content area
        content_margin = 20
        draw.rectangle([(content_margin, content_margin), (width-content_margin, height-content_margin)], 
                      fill='white', outline='#1a237e', width=3)
        
        # Header section
        header_height = 120
        draw.rectangle([(content_margin, content_margin), (width-content_margin, content_margin + header_height)], 
                      fill='#1a237e')
        
        # Conference title (simplified without external fonts)
        try:
            # Try to use a default font
            title_y = content_margin + 30
            draw.text((width//2, title_y), "MAGNACODE 2025", fill='white', anchor="mm")
            draw.text((width//2, title_y + 30), "BENGAL DIABETES CONFERENCE", fill='white', anchor="mm")
            draw.text((width//2, title_y + 55), "June 14-15, 2025", fill='white', anchor="mm")
        except:
            # Fallback if font issues
            draw.text((50, content_margin + 40), "MAGNACODE 2025 - BENGAL DIABETES CONFERENCE", fill='white')
        
        # Guest information section
        info_start_y = content_margin + header_height + 40
        
        # Guest ID (prominent)
        draw.text((50, info_start_y), f"ID: {guest['ID']}", fill='#1a237e')
        
        # Guest name
        name = guest.get('Name', 'N/A')
        if name and name != 'N/A':
            # Add "Dr." prefix for medical professionals if not already present
            if guest.get('GuestRole') in ['Delegates', 'Faculty'] and not name.upper().startswith('DR.'):
                name = f"Dr. {name}"
        draw.text((50, info_start_y + 40), f"Name: {name}", fill='black')
        
        # Role with colored background
        role = guest.get('GuestRole', 'Guest')
        role_colors = {
            'Delegates': '#28a745',
            'Faculty': '#007bff', 
            'Sponsors': '#ffc107',
            'Staff': '#6c757d',
            'OrgBatch': '#dc3545'
        }
        role_color = role_colors.get(role, '#6c757d')
        
        # Draw role badge
        role_y = info_start_y + 80
        role_width = len(role) * 12 + 20
        draw.rectangle([(50, role_y), (50 + role_width, role_y + 30)], fill=role_color)
        draw.text((60, role_y + 8), role.upper(), fill='white')
        
        # Additional info based on role
        extra_info_y = info_start_y + 130
        if guest.get('Batch'):
            draw.text((50, extra_info_y), f"Batch: {guest['Batch']}", fill='black')
            extra_info_y += 30
        
        if guest.get('CompanyName'):
            draw.text((50, extra_info_y), f"Company: {guest['CompanyName']}", fill='black')
            extra_info_y += 30
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=8,
            border=2
        )
        qr.add_data(f"GUEST:{guest['ID']}")
        qr.make()
        qr_img = qr.make_image(fill_color="#1a237e", back_color="white")
        
        # Resize and paste QR code
        qr_size = 200
        qr_resized = qr_img.resize((qr_size, qr_size))
        qr_x = width - qr_size - 50
        qr_y = info_start_y
        badge.paste(qr_resized, (qr_x, qr_y))
        
        # QR code label
        draw.text((qr_x + qr_size//2, qr_y + qr_size + 10), "Scan for Check-in", fill='black', anchor="mm")
        
        # Footer with venue info
        footer_y = height - 80
        draw.text((50, footer_y), "Venue: ITC Fortune Park, Pushpanjali, Durgapur", fill='#666666')
        draw.text((50, footer_y + 20), "Under the Banner of Bengal Diabetes Foundation", fill='#666666')
        
        # Conference logo placeholder (simple circle)
        logo_size = 60
        logo_x = width - logo_size - 30
        logo_y = 30
        draw.ellipse([(logo_x, logo_y), (logo_x + logo_size, logo_y + logo_size)], 
                    outline='white', width=3)
        draw.text((logo_x + logo_size//2, logo_y + logo_size//2), "BDF", fill='white', anchor="mm")
        
        return badge
        
    except Exception as e:
        logger.error(f"Error creating badge: {str(e)}")
        # Return a simple placeholder image
        placeholder = Image.new('RGB', (800, 600), 'lightgray')
        draw = ImageDraw.Draw(placeholder)
        draw.text((50, 300), f"Badge for {guest['ID']}", fill='black')
        draw.text((50, 330), f"Name: {guest.get('Name', 'N/A')}", fill='black')
        draw.text((50, 360), f"Role: {guest.get('GuestRole', 'Guest')}", fill='black')
        return placeholder
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

    draw.text((width_px//2, 60), "MAGNACODE 2025", fill='white', anchor="mm", font_size=54)
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
    draw.rectangle([(qr_x + 10, qr_y + 10), (qr_x + qr_container_size - 10, qr_y + qr_container_size - 10)], fill='none', outline=bright_orange, width=2)

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
    draw.rectangle([(info_x + 3, info_y + 3), (width_px - margin - 3, info_y + id_height - 3)], fill='none', outline='#ffffff40', width=1)
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
    draw.rectangle([(0, 0), (width_px - 1, height_px - 1)], fill='none', outline=navy_blue, width=5)
    draw.rectangle([(5, 5), (width_px - 6, height_px - 6)], fill='none', outline=bright_orange, width=1)

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
