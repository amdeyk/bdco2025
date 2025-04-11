from fastapi.templating import Jinja2Templates
from datetime import datetime
import os

# Initialize templates with a default path, will be updated in main.py
templates = Jinja2Templates(directory="templates")

# Add global variables
templates.env.globals["now"] = datetime.now()

def update_template_directory(directory_path):
    """Update template directory after config is loaded"""
    global templates
    if os.path.exists(directory_path):
        templates = Jinja2Templates(directory=directory_path)
        templates.env.globals["now"] = datetime.now()
    else:
        # Create the directory if it doesn't exist
        os.makedirs(directory_path, exist_ok=True)
        templates = Jinja2Templates(directory=directory_path)
        templates.env.globals["now"] = datetime.now()