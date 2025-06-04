import os
import json
import csv
from typing import List, Dict

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'conference_settings.json')


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {
            "name": "Sample Conference",
            "address": "Conference Venue",
            "date": "2025-01-01",
            "header_image": "/static/images/header.jpeg",
            "agenda_csv": ""
        }
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_settings(settings: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)


def parse_agenda_csv(agenda_path: str) -> List[Dict[str, str]]:
    """Parse agenda CSV into structured data.

    The CSV file is expected to contain the columns ``Date``, ``Time``,
    ``Event`` and ``Location`` (case insensitive).  If the file or path is
    missing, an empty list is returned.
    """
    if not agenda_path:
        return []

    # Support relative paths stored in settings
    if not os.path.isabs(agenda_path):
        agenda_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), agenda_path)

    if not os.path.exists(agenda_path):
        return []

    agenda = []
    try:
        with open(agenda_path, newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                agenda.append({
                    "date": row.get("Date") or row.get("date", ""),
                    "time": row.get("Time") or row.get("time", ""),
                    "event": row.get("Event") or row.get("event", ""),
                    "location": row.get("Location") or row.get("location", ""),
                })
    except Exception:
        return []

    return agenda
