import json
import os
import threading
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SettingsService:
    """Simple JSON-backed conference settings with caching."""

    DEFAULTS = {
        "name": "Conference",
        "dates": "",
        "contact_name": "",
        "contact_email": "",
        "location": "",
        "tagline": "",
        # New contact roles
        "chairperson_name": "",
        "chairperson_phone": "",
        "secretary_name": "",
        "secretary_phone": "",
        "scientific_chair_name": "",
        "scientific_chair_phone": "",
        # Visibility toggles for phone numbers (per-role)
        "show_chairperson_phone": False,
        "show_secretary_phone": False,
        "show_scientific_chair_phone": False,
        # Global status
        "registration_open": True,
    }

    def __init__(self, path: str = "./data/settings.json"):
        self.path = path
        self._lock = threading.RLock()
        self._cache = None
        self._mtime = None
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write(self.DEFAULTS)

    def _read(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed reading settings: {e}")
            return dict(self.DEFAULTS)

    def _write(self, data: dict):
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def get(self) -> dict:
        try:
            mtime = os.path.getmtime(self.path)
        except FileNotFoundError:
            self._write(self.DEFAULTS)
            mtime = os.path.getmtime(self.path)

        with self._lock:
            if self._cache is None or self._mtime != mtime:
                self._cache = {**self.DEFAULTS, **self._read()}
                self._mtime = mtime
            return self._cache

    def _coerce_bool(self, value) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def update(self, **kwargs) -> dict:
        with self._lock:
            current = self.get()
            data = dict(current)
            for k, v in kwargs.items():
                if k not in self.DEFAULTS:
                    continue
                # Preserve booleans; empty strings allowed for text
                if isinstance(self.DEFAULTS[k], bool):
                    data[k] = self._coerce_bool(v)
                else:
                    data[k] = v or ""
            self._write(data)
            self._cache = data
            self._mtime = os.path.getmtime(self.path)
            logger.info(f"Settings updated at {datetime.now().isoformat()}")
            return data


# Singleton
settings_service = SettingsService()
