# Updated routes/prompts/folders/get_folders.py

from typing import List, Optional, Dict, Any
from fastapi import Depends, HTTPException, Query, Request
from models.common import APIResponse
from utils import supabase_helpers
from .helpers import supabase, router
from utils.prompts import process_folder_for_response, process_template_for_response
from utils.access_control import get_user_metadata, apply_access_conditions
from utils.middleware.localization import extract_locale_from_request
from utils.monitoring.prometheus_metrics import track_db_query, track_cache_operation
from .get_folders_fixed import get_folders_fixed
async def fetch_accessible_folders(
    supabase,
    user_id: str,
    folder_types: List[str],
    locale: str,
) -> Dict[str, List[Dict]]:
    """
    Fetch all accessible folders by type with proper access control.
    """
    
    user_metadata = get_user_metadata(supabase, user_id)
    print(f"User metadataaaaaaaaa: {user_metadata}")

    folders_by_type = {}

    for folder_type in folder_types:
        folders = []

        if folder_type in ["user", "company", "organization"]:
            query = supabase.table("prompt_folders").select("*").eq("type", folder_type)
            query = apply_access_conditions(query, supabase, user_id)
            response = query.execute()
            folders = response.data or []
        
        # Process folders for response
        processed_folders = []
        for folder in folders:
            processed_folder = process_folder_for_response(folder, locale)
            processed_folders.append(processed_folder)
        
        folders_by_type[folder_type] = processed_folders
    
    return folders_by_type

@router.get("", response_model=APIResponse[Dict])
async def get_folders(
    request: Request,
    type: Optional[str] = Query(None, description="Folder type filter (user, company, organization)"),
    withSubfolders: bool = Query(False, description="Include nested subfolders"),
    withTemplates: bool = Query(False, description="Include templates for each folder"),
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[Dict]:
    """
    Main get_folders endpoint - now uses the fixed implementation
    """
    # Just call the fixed version
    return await get_folders_fixed(request, type, withSubfolders, withTemplates, user_id)


async def get_user_pinned_folder_ids(supabase, user_id: str) -> List[int]:
    """Get user's pinned folder IDs from the updated schema."""
    try:
        user_metadata = supabase.table("users_metadata").select("pinned_folder_ids").eq("user_id", user_id).single().execute()
        
        if not user_metadata.data:
            print(f"Debug: No user metadata found for user {user_id}")
            return []
        
        pinned_ids = user_metadata.data.get("pinned_folder_ids", [])
        print(f"Debug: Found pinned folder IDs for user {user_id}: {pinned_ids}")
        return pinned_ids
    except Exception as e:
        print(f"Debug: Error fetching pinned folders for user {user_id}: {str(e)}")
        return []

async def fetch_templates_for_all_folders(
    supabase,
    folder_ids: List[int],
    locale: str = "en"
) -> Dict[int, List[Dict]]:
    """
    Fetch all templates for the given folder IDs.
    """
    if not folder_ids:
        return {}
    
    # Get all templates for these folders
    response = supabase.table("prompt_templates").select("*").in_("folder_id", folder_ids).execute()
    templates = response.data or []
    
    # Group templates by folder_id
    templates_by_folder = {}
    for template in templates:
        folder_id = template.get("folder_id")
        if folder_id:
            if folder_id not in templates_by_folder:
                templates_by_folder[folder_id] = []
            
            processed_template = process_template_for_response(template, locale)
            templates_by_folder[folder_id].append(processed_template)
    
    return templates_by_folder

async def build_nested_folder_structure(
    folders: List[Dict],
    templates_by_folder: Dict[int, List[Dict]],
    parent_folder_id: Optional[int] = None,
    with_templates: bool = False,
    processed_ids: Optional[set] = None
) -> List[Dict]:
    """
    Recursively build nested folder structure with circular reference protection.
    """
    if processed_ids is None:
        processed_ids = set()
    
    result = []
    
    # Find folders with the specified parent_folder_id
    child_folders = []
    for f in folders:
        folder_parent_folder_id = f.get("parent_folder_id")
        folder_id = f.get("id")
        
        # Skip circular references (folder cannot be its own parent)
        if folder_id == folder_parent_folder_id:
            print(f"Debug: Skipping circular reference for folder {folder_id}")
            continue
            
        # Skip if this folder was already processed (prevents infinite loops)
        if folder_id in processed_ids:
            continue
            
        if folder_parent_folder_id == parent_folder_id:
            child_folders.append(f)
    
    for folder in child_folders:
        folder_id = folder["id"]
        
        # Mark this folder as processed
        processed_ids.add(folder_id)
        
        folder_data = folder.copy()
        
        # Get child folders recursively
        children = await build_nested_folder_structure(
            folders, templates_by_folder, folder_id, with_templates, processed_ids
        )
        
        if children:
            folder_data["subfolders"] = children
        
        # Add templates if requested
        if with_templates:
            folder_templates = templates_by_folder.get(folder_id, [])
            if folder_templates:
                folder_data["templates"] = folder_templates
        
        result.append(folder_data)
    
    return result