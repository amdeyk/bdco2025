from fastapi.templating import Jinja2Templates
from datetime import datetime
from app.config import Config

# Load config
config = Config()

# Initialize templates with global variables for all routes
templates = Jinja2Templates(directory=config.get('PATHS', 'TemplatesDir'))
templates.env.globals["now"] = datetime.now()