import csv
import os
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class JourneyDataService:
    """Service to synchronize journey data between guests.csv and journey.csv"""

    def __init__(self, guests_csv_path: str, journey_csv_path: str, backup_dir: str):
        self.guests_csv_path = guests_csv_path
        self.journey_csv_path = journey_csv_path
        self.backup_dir = backup_dir

        os.makedirs(os.path.dirname(journey_csv_path), exist_ok=True)
        os.makedirs(backup_dir, exist_ok=True)

        self._initialize_journey_csv()
        logger.info("Journey synchronization service initialized")

    def _initialize_journey_csv(self):
        """Create journey.csv if it does not exist"""
        if not os.path.exists(self.journey_csv_path):
            fieldnames = [
                "guest_id",
                "inward_date",
                "inward_origin",
                "inward_destination",
                "inward_transport_mode",
                "inward_transport_details",
                "inward_remarks",
                "outward_date",
                "outward_origin",
                "outward_destination",
                "outward_transport_mode",
                "outward_transport_details",
                "outward_remarks",
                "pickup_required",
                "pickup_location",
                "pickup_confirmed",
                "drop_required",
                "drop_location",
                "drop_confirmed",
                "updated_at",
            ]

            with open(self.journey_csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            logger.info("Created new journey.csv at %s", self.journey_csv_path)

    def update_journey_from_guest(self, guest_id: str, journey_data: Dict) -> bool:
        """Update journey details from guest interface"""
        try:
            self._update_journey_csv(guest_id, journey_data)
            self._sync_to_guests_csv(guest_id, journey_data)
            self._mark_journey_updated(guest_id)
            logger.info("Journey updated from guest interface for %s", guest_id)
            return True
        except Exception as exc:
            logger.error("Error updating journey from guest: %s", exc)
            return False

    def update_journey_from_admin(self, guest_id: str, admin_data: Dict) -> bool:
        """Update journey details from admin interface"""
        try:
            journey_data = self._convert_admin_to_journey_format(admin_data)
            # Update guests.csv using the normalized journey fields to avoid
            # writing unexpected columns
            self._sync_to_guests_csv(guest_id, journey_data)
            self._update_journey_csv(guest_id, journey_data)
            logger.info("Journey updated from admin interface for %s", guest_id)
            return True
        except Exception as exc:
            logger.error("Error updating journey from admin: %s", exc)
            return False

    def get_journey_data(self, guest_id: str) -> Optional[Dict]:
        """Return unified journey data for a guest"""
        try:
            journey_data = self._get_from_journey_csv(guest_id)
            if journey_data and journey_data.get("updated_at"):
                return journey_data

            guests_data = self._get_from_guests_csv(guest_id)
            if guests_data and guests_data.get("LastJourneyUpdate"):
                return self._convert_guests_to_journey_format(guests_data)

            return journey_data if journey_data else None
        except Exception as exc:
            logger.error("Error getting journey data: %s", exc)
            return None

    def _update_journey_csv(self, guest_id: str, journey_data: Dict):
        """Insert or update journey.csv"""
        rows = []
        updated = False
        fieldnames = [
            "guest_id",
            "inward_date",
            "inward_origin",
            "inward_destination",
            "inward_transport_mode",
            "inward_transport_details",
            "inward_remarks",
            "outward_date",
            "outward_origin",
            "outward_destination",
            "outward_transport_mode",
            "outward_transport_details",
            "outward_remarks",
            "pickup_required",
            "pickup_location",
            "pickup_confirmed",
            "drop_required",
            "drop_location",
            "drop_confirmed",
            "updated_at",
        ]

        if os.path.exists(self.journey_csv_path):
            with open(self.journey_csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["guest_id"] == guest_id:
                        row.update(journey_data)
                        row["updated_at"] = datetime.now().isoformat()
                        updated = True
                    rows.append(row)

        if not updated:
            new_record = {field: "" for field in fieldnames}
            new_record.update(journey_data)
            new_record["guest_id"] = guest_id
            new_record["updated_at"] = datetime.now().isoformat()
            rows.append(new_record)

        with open(self.journey_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _sync_to_guests_csv(self, guest_id: str, journey_data: Dict):
        admin_fields = {
            "InwardJourneyDate": journey_data.get("inward_date", ""),
            "InwardJourneyFrom": journey_data.get("inward_origin", ""),
            "InwardJourneyTo": journey_data.get("inward_destination", ""),
            "InwardJourneyDetails": journey_data.get("inward_transport_details", ""),
            "InwardJourneyRemarks": journey_data.get("inward_remarks", ""),
            "InwardPickupRequired": str(journey_data.get("pickup_required", False)),
            "OutwardJourneyDate": journey_data.get("outward_date", ""),
            "OutwardJourneyFrom": journey_data.get("outward_origin", ""),
            "OutwardJourneyTo": journey_data.get("outward_destination", ""),
            "OutwardJourneyDetails": journey_data.get("outward_transport_details", ""),
            "OutwardJourneyRemarks": journey_data.get("outward_remarks", ""),
            "OutwardDropRequired": str(journey_data.get("drop_required", False)),
            "JourneyDetailsUpdated": "True",
            "LastJourneyUpdate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        self._update_guests_csv_journey(guest_id, admin_fields)

    def _update_guests_csv_journey(self, guest_id: str, admin_data: Dict):
        rows = []
        updated = False

        if os.path.exists(self.guests_csv_path):
            with open(self.guests_csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames)

                journey_fields = [
                    "InwardJourneyDate",
                    "InwardJourneyFrom",
                    "InwardJourneyTo",
                    "InwardJourneyDetails",
                    "InwardJourneyRemarks",
                    "InwardPickupRequired",
                    "OutwardJourneyDate",
                    "OutwardJourneyFrom",
                    "OutwardJourneyTo",
                    "OutwardJourneyDetails",
                    "OutwardJourneyRemarks",
                    "OutwardDropRequired",
                    "JourneyDetailsUpdated",
                    "LastJourneyUpdate",
                ]
                for field in journey_fields:
                    if field not in fieldnames:
                        fieldnames.append(field)

                for row in reader:
                    if row["ID"] == guest_id:
                        row.update(admin_data)
                        updated = True

                    for field in fieldnames:
                        if field not in row:
                            row[field] = ""
                    rows.append(row)

        if updated:
            with open(self.guests_csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

    def _mark_journey_updated(self, guest_id: str):
        update_data = {
            "JourneyDetailsUpdated": "True",
            "LastJourneyUpdate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._update_guests_csv_journey(guest_id, update_data)

    def _get_from_journey_csv(self, guest_id: str) -> Optional[Dict]:
        if not os.path.exists(self.journey_csv_path):
            return None
        with open(self.journey_csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["guest_id"] == guest_id:
                    return row
        return None

    def _get_from_guests_csv(self, guest_id: str) -> Optional[Dict]:
        if not os.path.exists(self.guests_csv_path):
            return None
        with open(self.guests_csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["ID"] == guest_id:
                    return row
        return None

    def _convert_admin_to_journey_format(self, admin_data: Dict) -> Dict:
        return {
            "inward_date": admin_data.get("inward_date", ""),
            "inward_origin": admin_data.get("inward_from", ""),
            "inward_destination": admin_data.get("inward_to", ""),
            "inward_transport_details": admin_data.get("inward_details", ""),
            "inward_remarks": admin_data.get("inward_remarks", ""),
            "pickup_required": admin_data.get("inward_pickup", False),
            "outward_date": admin_data.get("outward_date", ""),
            "outward_origin": admin_data.get("outward_from", ""),
            "outward_destination": admin_data.get("outward_to", ""),
            "outward_transport_details": admin_data.get("outward_details", ""),
            "outward_remarks": admin_data.get("outward_remarks", ""),
            "drop_required": admin_data.get("outward_drop", False),
        }

    def _convert_guests_to_journey_format(self, guests_data: Dict) -> Dict:
        return {
            "guest_id": guests_data.get("ID", ""),
            "inward_date": guests_data.get("InwardJourneyDate", ""),
            "inward_origin": guests_data.get("InwardJourneyFrom", ""),
            "inward_destination": guests_data.get("InwardJourneyTo", ""),
            "inward_transport_details": guests_data.get("InwardJourneyDetails", ""),
            "inward_remarks": guests_data.get("InwardJourneyRemarks", ""),
            "pickup_required": guests_data.get("InwardPickupRequired", "False") == "True",
            "outward_date": guests_data.get("OutwardJourneyDate", ""),
            "outward_origin": guests_data.get("OutwardJourneyFrom", ""),
            "outward_destination": guests_data.get("OutwardJourneyTo", ""),
            "outward_transport_details": guests_data.get("OutwardJourneyDetails", ""),
            "outward_remarks": guests_data.get("OutwardJourneyRemarks", ""),
            "drop_required": guests_data.get("OutwardDropRequired", "False") == "True",
            "updated_at": guests_data.get("LastJourneyUpdate", ""),
        }

    def sync_all_data(self) -> Dict[str, int]:
        stats = {"synced_from_guests": 0, "synced_from_journey": 0, "errors": 0}
        try:
            guests = []
            if os.path.exists(self.guests_csv_path):
                with open(self.guests_csv_path, "r", newline="", encoding="utf-8") as f:
                    guests = list(csv.DictReader(f))

            for guest in guests:
                guest_id = guest["ID"]
                try:
                    has_guests_journey = any([
                        guest.get("InwardJourneyDate"),
                        guest.get("OutwardJourneyDate"),
                    ])

                    journey_data = self._get_from_journey_csv(guest_id)
                    has_journey_data = journey_data is not None and journey_data.get("updated_at")

                    if has_guests_journey and not has_journey_data:
                        journey_format = self._convert_guests_to_journey_format(guest)
                        self._update_journey_csv(guest_id, journey_format)
                        stats["synced_from_guests"] += 1
                    elif has_journey_data and not has_guests_journey:
                        self._sync_to_guests_csv(guest_id, journey_data)
                        stats["synced_from_journey"] += 1
                except Exception as exc:
                    logger.error("Error syncing data for guest %s: %s", guest_id, exc)
                    stats["errors"] += 1

            logger.info("Journey data sync completed: %s", stats)
            return stats
        except Exception as exc:
            logger.error("Error during full sync: %s", exc)
            stats["errors"] += 1
            return stats


def create_journey_service(config):
    return JourneyDataService(
        guests_csv_path=config.get("DATABASE", "CSVPath"),
        journey_csv_path=os.path.join(os.path.dirname(config.get("DATABASE", "CSVPath")), "journey.csv"),
        backup_dir=config.get("DATABASE", "BackupDir"),
    )
