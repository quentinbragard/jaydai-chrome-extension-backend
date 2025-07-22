# routes/prompts/folders/get_pinned_folders.py

from typing import List, Dict, Any
from fastapi import Depends, HTTPException, Request, Query
from models.common import APIResponse
from utils import supabase_helpers
from .helpers import supabase, router
from utils.prompts import process_folder_for_response, process_template_for_response
from utils.access_control import apply_access_conditions
from utils.middleware.localization import extract_locale_from_request

async def get_user_pinned_folder_ids(supabase, user_id: str) -> List[int]:
    """Get user's pinned folder IDs from the updated schema."""
    try:
        user_metadata = supabase.table("users_metadata").select("pinned_folder_ids").eq("user_id", user_id).single().execute()
        if not user_metadata.data:
            return []
        return user_metadata.data.get("pinned_folder_ids", [])
    except Exception as e:
        print(f"Error fetching pinned folders for user {user_id}: {str(e)}")
        return []

async def fetch_templates_for_folders(
    supabase,
    folder_ids: List[int],
    locale: str = "en"
) -> Dict[int, List[Dict]]:
    """Fetch all templates for the given folder IDs."""
    if not folder_ids:
        return {}
    response = supabase.table("prompt_templates").select("*").in_("folder_id", folder_ids).execute()
    templates = response.data or []
    templates_by_folder = {}
    for template in templates:
        folder_id = template.get("folder_id")
        if folder_id:
            if folder_id not in templates_by_folder:
                templates_by_folder[folder_id] = []
            processed_template = process_template_for_response(template, locale)
            templates_by_folder[folder_id].append(processed_template)
    return templates_by_folder

@router.get("/pinned", response_model=APIResponse[Dict])
async def get_pinned_folders(
    request: Request,
    withTemplates: bool = Query(False),
    withSubfolders: bool = Query(False),
    locale: str = Query(None),
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[Dict]:
    """
    Get only the user's pinned folders, optionally with templates.
    """
    #try:
    print("+++++++++++++++++++++++++++++\n")
    print("PARAMS : ", request)
    # locale = extract_locale_from_request(request) # This line is now handled by the Query parameter
    pinned_folder_ids = await get_user_pinned_folder_ids(supabase, user_id)
    if not pinned_folder_ids:
        return APIResponse(success=True, data={"folders": []})

    # Fetch only folders that are pinned
    query = supabase.table("prompt_folders").select("*").in_("id", pinned_folder_ids)
    query = apply_access_conditions(query, supabase, user_id)
    response = query.execute()
    folders = response.data or []

    # Process folders for response
    processed_folders = [process_folder_for_response(folder, locale) for folder in folders]

    # Optionally fetch templates for these folders
    if withTemplates and processed_folders:
        folder_ids = [f["id"] for f in processed_folders]
        templates_by_folder = await fetch_templates_for_folders(supabase, folder_ids, locale)
        for folder in processed_folders:
            folder_templates = templates_by_folder.get(folder["id"], [])
            if folder_templates:
                folder["templates"] = folder_templates

    return APIResponse(success=True, data={"folders": processed_folders})

    #except Exception as e:
    #    if isinstance(e, HTTPException):
    #        raise e
    #    raise HTTPException(status_code=500, detail=f"Error retrieving pinned folders: {str(e)}")
