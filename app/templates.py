from fastapi.templating import Jinja2Templates
from datetime import datetime
import os

from app.utils.conference_settings import load_settings

# Initialize templates with a default path, will be updated in main.py
templates = Jinja2Templates(directory="templates")

# Add global variables
templates.env.globals["now"] = datetime.now()
templates.env.globals["conference"] = load_settings()

def update_template_directory(directory_path):
    """Update template directory after config is loaded"""
    global templates
    if not os.path.exists(directory_path):
        os.makedirs(directory_path, exist_ok=True)
    templates = Jinja2Templates(directory=directory_path)
    templates.env.globals["now"] = datetime.now()
    templates.env.globals["conference"] = load_settings()
