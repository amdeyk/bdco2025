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
from app.utils.logging_utils import log_activity
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