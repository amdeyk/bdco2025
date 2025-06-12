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
    """Generate and download corporate badge for a guest - global access"""
    try:
        guests = guests_db.read_all()
        guest = next((g for g in guests if g["ID"] == guest_id), None)
        
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")

        # Create corporate badge design
        badge_image = create_magnacode_corporate_badge(guest)

        # Convert to bytes with high quality
        img_byte_array = io.BytesIO()
        badge_image.save(img_byte_array, format='PNG', dpi=(300, 300))
        img_byte_array.seek(0)
        
        # Log this activity
        log_activity(guest_id, "Corporate badge generated")
        
        return StreamingResponse(
            img_byte_array,
            media_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="MAGNACODE2025_{guest_id}_badge.png"'
            }
        )

    except Exception as e:
        logger.error(f"Error generating badge: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating badge")



def create_magnacode_corporate_badge(guest: dict) -> Image.Image:
    """Create MAGNACODE 2025 corporate badge - 140mm × 90mm"""
    try:
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

        header_h = int(height_px * 0.25)
        for line in range(header_h):
            intensity = 1 - (line / header_h * 0.3)
            blue_val = int(30 + (138-30) * intensity)
            draw.line([(0, line), (width_px, line)], fill=f'#{blue_val:02x}{58:02x}{138:02x}')

        try:
            draw.text((width_px//2, 55), "MAGNACODE 2025", fill='white', anchor="mm", font_size=54)
            draw.text((width_px//2, 115), "Healthcare and Education Foundation", fill='white', anchor="mm", font_size=28)
            draw.text((width_px//2, 165), "21st & 22nd September 2025", fill=gold, anchor="mm", font_size=24)
            draw.text((width_px//2, 195), "Bangalore", fill='white', anchor="mm", font_size=22)
        except TypeError:
            draw.text((60, 55), "MAGNACODE 2025", fill='white')
            draw.text((40, 95), "Healthcare and Education Foundation", fill='white')
            draw.text((60, 135), "21st & 22nd September 2025", fill=gold)
            draw.text((90, 165), "Bangalore", fill='white')

        content_top = header_h + 45
        side_margin = 55

        qr_dimension = 230
        qr_padding = 30
        qr_container_size = qr_dimension + (qr_padding * 2)
        qr_left = side_margin
        qr_top = content_top + 85

        shadow_dist = 6
        draw.rectangle([(qr_left + shadow_dist, qr_top + shadow_dist), (qr_left + qr_container_size + shadow_dist, qr_top + qr_container_size + shadow_dist)], fill='#00000025')

        draw.rectangle([(qr_left, qr_top), (qr_left + qr_container_size, qr_top + qr_container_size)], fill='white', outline=navy_blue, width=5)
        draw.rectangle([(qr_left + 8, qr_top + 8), (qr_left + qr_container_size - 8, qr_top + qr_container_size - 8)], fill='none', outline=bright_orange, width=2)

        qr_generator = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=1)
        qr_generator.add_data(f"MAGNACODE2025:DELEGATE:{guest['ID']}")
        qr_generator.make(fit=True)
        qr_image = qr_generator.make_image(fill_color=navy_blue, back_color="white")
        qr_final = qr_image.resize((qr_dimension, qr_dimension), Image.Resampling.LANCZOS)
        badge.paste(qr_final, (qr_left + qr_padding, qr_top + qr_padding))

        draw.text((qr_left + qr_container_size//2, qr_top + qr_container_size + 25), "🔄 Instant Check-in", fill=charcoal, anchor="mm")

        info_left = qr_left + qr_container_size + 45
        info_width = width_px - info_left - side_margin
        info_top = content_top + 45

        id_badge_h = 58
        draw.rectangle([(info_left, info_top), (width_px - side_margin, info_top + id_badge_h)], fill=bright_orange)
        draw.rectangle([(info_left + 3, info_top + 3), (width_px - side_margin - 3, info_top + id_badge_h - 3)], fill='none', outline='#ffffff40', width=1)
        draw.text((info_left + info_width//2, info_top + id_badge_h//2), f"DELEGATE ID: {guest['ID']}", fill='white', anchor="mm")

        name_top = info_top + id_badge_h + 25
        delegate_name = guest.get('Name', 'N/A')
        if delegate_name and delegate_name != 'N/A':
            role_type = guest.get('GuestRole', '')
            if role_type in ['Delegates', 'Faculty', 'OrgBatch']:
                title_prefixes = ['DR.', 'PROF.', 'MR.', 'MS.', 'MRS.', 'MISS']
                if not any(prefix in delegate_name.upper() for prefix in title_prefixes):
                    delegate_name = f"Dr. {delegate_name}"

        name_area_h = 90
        draw.rectangle([(info_left, name_top), (width_px - side_margin, name_top + name_area_h)], fill=sky_blue, outline=navy_blue, width=4)

        max_name_chars = 20
        if len(delegate_name) > max_name_chars:
            name_words = delegate_name.split(' ')
            if len(name_words) > 1:
                halfway = len(name_words) // 2
                first_line = ' '.join(name_words[:halfway])
                second_line = ' '.join(name_words[halfway:])
                draw.text((info_left + info_width//2, name_top + 25), first_line, fill=navy_blue, anchor="mm")
                draw.text((info_left + info_width//2, name_top + 65), second_line, fill=navy_blue, anchor="mm")
            else:
                draw.text((info_left + info_width//2, name_top + name_area_h//2), delegate_name, fill=navy_blue, anchor="mm")
        else:
            draw.text((info_left + info_width//2, name_top + name_area_h//2), delegate_name, fill=navy_blue, anchor="mm")

        category = guest.get('GuestRole', 'Guest')
        category_colors = {
            'Delegates': '#059669',
            'Faculty': '#dc2626',
            'Sponsors': '#d97706',
            'Staff': '#6b7280',
            'OrgBatch': '#7c3aed',
            'Roots': '#0891b2',
            'Event': '#ea580c'
        }
        category_color = category_colors.get(category, '#6b7280')

        category_top = name_top + name_area_h + 20
        category_h = 48
        draw.rectangle([(info_left, category_top), (width_px - side_margin, category_top + category_h)], fill=category_color)
        draw.rectangle([(info_left, category_top), (width_px - side_margin, category_top + 15)], fill='#ffffff30')
        draw.text((info_left + info_width//2, category_top + category_h//2), category.upper(), fill='white', anchor="mm")

        details_top = category_top + category_h + 25
        line_spacing = 38

        phone_num = guest.get('Phone', '')
        if phone_num:
            if len(phone_num) == 10 and phone_num.isdigit():
                formatted_phone = f"{phone_num[:3]}-{phone_num[3:6]}-{phone_num[6:]}"
            else:
                formatted_phone = phone_num
            draw.text((info_left + 15, details_top), f"📱 {formatted_phone}", fill=charcoal)
            details_top += line_spacing

        if guest.get('Organization'):
            org_name = guest['Organization']
            if len(org_name) > 24:
                org_name = org_name[:21] + "..."
            draw.text((info_left + 15, details_top), f"🏛️ {org_name}", fill=charcoal)
            details_top += line_spacing

        if guest.get('Batch'):
            draw.text((info_left + 15, details_top), f"🎓 Batch: {guest['Batch']}", fill=charcoal)
            details_top += line_spacing

        footer_top = height_px - 140
        footer_h = 130
        draw.rectangle([(0, footer_top), (width_px, height_px)], fill=pearl_gray)
        draw.rectangle([(0, footer_top), (width_px, footer_top + 4)], fill=bright_orange)

        footer_content = [
            "🏢 Venue: The Chancery Pavilion, Bangalore",
            "⚕️ Healthcare Excellence • 📖 Education Innovation",
            "🌐 www.magnacode.org • 📧 info@magnacode.org"
        ]

        for idx, content_line in enumerate(footer_content):
            draw.text((width_px//2, footer_top + 30 + (idx * 32)), content_line, fill=charcoal, anchor="mm")

        corner_accent_size = 28
        points_tr = [
            (width_px - corner_accent_size - 20, 20),
            (width_px - 20, 20),
            (width_px - 20, corner_accent_size + 20)
        ]
        draw.polygon(points_tr, fill=bright_orange)

        points_bl = [
            (20, height_px - corner_accent_size - 20),
            (corner_accent_size + 20, height_px - corner_accent_size - 20),
            (20, height_px - 20)
        ]
        draw.polygon(points_bl, fill=bright_orange)

        draw.rectangle([(0, 0), (10, height_px)], fill=bright_orange)
        draw.rectangle([(width_px - 10, 0), (width_px, height_px)], fill=bright_orange)

        draw.rectangle([(0, 0), (width_px - 1, height_px - 1)], fill='none', outline=navy_blue, width=5)
        draw.rectangle([(5, 5), (width_px - 6, height_px - 6)], fill='none', outline=bright_orange, width=1)

        logo_diameter = 65
        logo_center_x = width_px - 80
        logo_center_y = 80
        logo_radius = logo_diameter // 2
        draw.ellipse([(logo_center_x - logo_radius, logo_center_y - logo_radius), (logo_center_x + logo_radius, logo_center_y + logo_radius)], fill='white', outline=bright_orange, width=3)
        draw.text((logo_center_x, logo_center_y), "MC", fill=navy_blue, anchor="mm")

        return badge

    except Exception as e:
        logger.error(f"Error creating MAGNACODE corporate badge: {str(e)}")
        fallback_badge = Image.new('RGB', (1063, 1654), 'white')
        fallback_draw = ImageDraw.Draw(fallback_badge)
        fallback_draw.rectangle([(0, 0), (1063, 400)], fill='#1e3a8a')
        fallback_draw.text((532, 100), "MAGNACODE 2025", fill='white', anchor="mm")
        fallback_draw.text((532, 150), "Healthcare & Education Conference", fill='white', anchor="mm")
        fallback_draw.text((532, 200), "21st & 22nd September 2025, Bangalore", fill=gold, anchor="mm")
        fallback_draw.text((100, 500), f"Delegate ID: {guest.get('ID', 'Unknown')}", fill='black')
        fallback_draw.text((100, 600), f"Name: {guest.get('Name', 'N/A')}", fill='black')
        fallback_draw.text((100, 700), f"Category: {guest.get('GuestRole', 'Guest')}", fill='black')
        fallback_draw.rectangle([(100, 800), (300, 1000)], fill='#f0f0f0', outline='#1e3a8a', width=2)
        fallback_draw.text((200, 900), "QR CODE", fill='#1e3a8a', anchor="mm")
        fallback_draw.rectangle([(0, 1500), (1063, 1654)], fill='#f8fafc')
        fallback_draw.text((532, 1550), "The Chancery Pavilion, Bangalore", fill='#334155', anchor="mm")
        fallback_draw.text((532, 1580), "www.magnacode.org", fill='#334155', anchor="mm")
        return fallback_badge


def create_simple_badge_common(guest: dict) -> Image.Image:
    """Create a simplified version of the corporate badge for quick generation"""
    try:
        width, height = 800, 1200
        badge = Image.new('RGB', (width, height), '#ffffff')
        draw = ImageDraw.Draw(badge)

        primary_blue = '#1e3a8a'
        accent_orange = '#f97316'
        light_gray = '#f8fafc'
        dark_gray = '#334155'

        header_height = 250
        draw.rectangle([(0, 0), (width, header_height)], fill=primary_blue)
        try:
            draw.text((width//2, 50), "MAGNACODE 2025", fill='white', anchor="mm", font_size=36)
            draw.text((width//2, 100), "Healthcare and Education Foundation", fill='white', anchor="mm", font_size=20)
            draw.text((width//2, 150), "21st & 22nd September 2025", fill='#fbbf24', anchor="mm", font_size=18)
            draw.text((width//2, 180), "Bangalore", fill='white', anchor="mm", font_size=16)
        except TypeError:
            draw.text((50, 50), "MAGNACODE 2025", fill='white')
            draw.text((30, 90), "Healthcare and Education Foundation", fill='white')
            draw.text((50, 130), "21st & 22nd September 2025", fill='#fbbf24')
            draw.text((80, 160), "Bangalore", fill='white')

        content_start = header_height + 30
        id_height = 50
        draw.rectangle([(50, content_start), (width-50, content_start + id_height)], fill=accent_orange)
        draw.text((width//2, content_start + 25), f"ID: {guest['ID']}", fill='white', anchor="mm")

        name_y = content_start + id_height + 30
        name = guest.get('Name', 'N/A')
        if name and name != 'N/A':
            role = guest.get('GuestRole', '')
            if role in ['Delegates', 'Faculty', 'OrgBatch'] and not name.upper().startswith(('DR.', 'PROF.')):
                name = f"Dr. {name}"

        name_height = 80
        draw.rectangle([(50, name_y), (width-50, name_y + name_height)], fill='#e0f2fe', outline=primary_blue, width=2)
        draw.text((width//2, name_y + 40), name, fill=primary_blue, anchor="mm")

        role = guest.get('GuestRole', 'Guest')
        role_colors = {
            'Delegates': '#059669', 'Faculty': '#dc2626', 'Sponsors': '#d97706',
            'Staff': '#6b7280', 'OrgBatch': '#7c3aed', 'Roots': '#0891b2', 'Event': '#ea580c'
        }
        role_color = role_colors.get(role, '#6b7280')

        role_y = name_y + name_height + 20
        role_height = 40
        draw.rectangle([(50, role_y), (width-50, role_y + role_height)], fill=role_color)
        draw.text((width//2, role_y + 20), role.upper(), fill='white', anchor="mm")

        qr_y = role_y + role_height + 30
        qr_size = 200
        qr_x = (width - qr_size) // 2

        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=8, border=2)
        qr.add_data(f"MAGNACODE2025:GUEST:{guest['ID']}")
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color=primary_blue, back_color="white")
        qr_resized = qr_img.resize((qr_size, qr_size))
        badge.paste(qr_resized, (qr_x, qr_y))

        draw.text((width//2, qr_y + qr_size + 15), "Scan for Check-in", fill=dark_gray, anchor="mm")

        contact_y = qr_y + qr_size + 50
        phone = guest.get('Phone', '')
        if phone:
            draw.text((70, contact_y), f"Phone: {phone}", fill=dark_gray)
            contact_y += 30

        if guest.get('Organization'):
            org = guest['Organization']
            if len(org) > 30:
                org = org[:27] + "..."
            draw.text((70, contact_y), f"Org: {org}", fill=dark_gray)

        footer_y = height - 100
        draw.rectangle([(0, footer_y), (width, height)], fill=light_gray)
        draw.text((width//2, footer_y + 20), "The Chancery Pavilion, Bangalore", fill=dark_gray, anchor="mm")
        draw.text((width//2, footer_y + 45), "Healthcare Excellence • Education Innovation", fill=dark_gray, anchor="mm")
        draw.text((width//2, footer_y + 70), "www.magnacode.org", fill=dark_gray, anchor="mm")

        draw.rectangle([(0, header_height), (width, header_height + 5)], fill=accent_orange)
        draw.rectangle([(0, 0), (5, height)], fill=accent_orange)
        draw.rectangle([(width-5, 0), (width, height)], fill=accent_orange)
        draw.rectangle([(0, 0), (width-1, height-1)], fill='none', outline=primary_blue, width=3)

        return badge

    except Exception as e:
        logger.error(f"Error creating simple badge: {str(e)}")
        placeholder = Image.new('RGB', (800, 1200), 'lightgray')
        draw_placeholder = ImageDraw.Draw(placeholder)
        draw_placeholder.text((400, 200), "MAGNACODE 2025", fill='black', anchor="mm")
        draw_placeholder.text((100, 400), f"ID: {guest.get('ID', 'Unknown')}", fill='black')
        draw_placeholder.text((100, 450), f"Name: {guest.get('Name', 'N/A')}", fill='black')
        draw_placeholder.text((100, 500), f"Role: {guest.get('GuestRole', 'Guest')}", fill='black')
        return placeholder