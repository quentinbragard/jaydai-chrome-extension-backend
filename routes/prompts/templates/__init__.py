# routes/prompts/templates/__init__.py
from fastapi import APIRouter

router = APIRouter(tags=["Templates"])

# Import all route modules to register them with the router
from . import get_folders
from . import create_folder
from . import update_folder
from . import delete_folder
from . import pin_folder
from . import unpin_folder
from . import update_pinned_folders_endpoint
from . import get_template_folders
from . import reorder_folders
from . import toggle_priority
from . import move_folder
from . import get_available_parents
