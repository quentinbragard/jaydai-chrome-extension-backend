# routes/prompts/folders/__init__.py
from fastapi import APIRouter

router = APIRouter(tags=["Folders"])

# Import helper functions and utilities first
from .helpers import (
    router,
    supabase,
    PromptType,
    get_user_organizations,
    get_user_company,
    fetch_folders_by_type,
    fetch_templates_for_folders,
    organize_templates_by_folder,
    add_templates_to_folders,
    get_user_pinned_folders,
    update_user_pinned_folders,
    add_pinned_status_to_folders,
    create_localized_field,
    determine_folder_type,
)

# CRITICAL: Import specific routes BEFORE generic routes with path parameters
# This prevents FastAPI from matching /pinned as /{folder_id}

# Import specific named routes first
from . import get_pinned_folders  # Must be BEFORE get_folder_by_id
from . import pin_folder
from . import unpin_folder
from . import update_pinned_folders_endpoint
from . import get_template_folders

# Import generic routes with path parameters last
from . import get_folders
from . import get_folder_by_id  # This has /{folder_id} - must be AFTER /pinned
from . import create_folder
from . import update_folder
from . import delete_folder

# Assign helper functions for backwards compatibility
get_template_folders_by_type = fetch_folders_by_type

__all__ = [
    "router",
    "supabase",
    "create_folder",
    "update_folder", 
    "delete_folder",
    "pin_folder",
    "unpin_folder",
    "update_pinned_folders_endpoint",
    "get_template_folders",
    "get_folders",
    "get_folder_by_id",
    "get_template_folders_by_type",
    "fetch_folders_by_type",
    "fetch_templates_for_folders",
    "organize_templates_by_folder",
    "add_templates_to_folders",
    "get_user_pinned_folders",
    "update_user_pinned_folders",
    "add_pinned_status_to_folders",
    "create_localized_field",
    "determine_folder_type",
    "get_pinned_folders",
]