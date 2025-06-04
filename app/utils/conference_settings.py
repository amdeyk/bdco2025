import os
import json

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'conference_settings.json')


def load_settings():
    defaults = {
        "name": "Sample Conference",
        "address": "Conference Venue",
        "date": "2025-01-01",
        "header_image": "/static/images/header.jpeg",
        "agenda_csv": ""
    }

    if not os.path.exists(SETTINGS_FILE):
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(defaults, f, indent=4)
        return defaults

    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_settings(settings: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)
