from fastapi.templating import Jinja2Templates
from datetime import datetime
import os
from app.config import Config

# Initialize templates with a default path, will be updated in main.py
templates = Jinja2Templates(directory="templates")

# Load config and add globals for templates
_config = Config()

def _apply_conference_globals(tpl: Jinja2Templates, cfg: Config):
    tpl.env.globals["now"] = datetime.now()
    tpl.env.globals["conference_name"] = cfg.get('CONFERENCE', 'Name')
    tpl.env.globals["conference_tagline"] = cfg.get('CONFERENCE', 'Tagline')
    tpl.env.globals["conference_dates"] = cfg.get('CONFERENCE', 'Dates')
    tpl.env.globals["conference_venue"] = cfg.get('CONFERENCE', 'Venue')
    tpl.env.globals["conference_city"] = cfg.get('CONFERENCE', 'City')
    tpl.env.globals["conference_website"] = cfg.get('CONFERENCE', 'Website')
    tpl.env.globals["conference_contact_email"] = cfg.get('CONFERENCE', 'ContactEmail')
    tpl.env.globals["support_phone1"] = cfg.get('CONFERENCE', 'SupportPhone1')
    tpl.env.globals["support_phone2"] = cfg.get('CONFERENCE', 'SupportPhone2')
    tpl.env.globals["schedule_file"] = cfg.get('CONFERENCE', 'ScheduleFile')
    tpl.env.globals["app_version"] = cfg.get('DEFAULT', 'SoftwareVersion')

_apply_conference_globals(templates, _config)

def update_template_directory(directory_path):
    """Update template directory after config is loaded"""
    global templates
    if os.path.exists(directory_path):
        templates = Jinja2Templates(directory=directory_path)
        _apply_conference_globals(templates, _config)
    else:
        # Create the directory if it doesn't exist
        os.makedirs(directory_path, exist_ok=True)
        templates = Jinja2Templates(directory=directory_path)
        _apply_conference_globals(templates, _config)
