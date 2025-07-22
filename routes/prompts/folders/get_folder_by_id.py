from typing import Optional, Dict, List
from fastapi import Depends, HTTPException, Query, Request
from models.common import APIResponse
from utils import supabase_helpers
from .helpers import router, supabase
from .get_folders import build_nested_folder_structure, fetch_templates_for_all_folders
from utils.prompts import process_folder_for_response, process_template_for_response
from utils.access_control import apply_access_conditions, user_has_access_to_folder
from utils.middleware.localization import extract_locale_from_request

@router.get("/{folder_id}", response_model=APIResponse[Dict])
async def get_folder_by_id(
    folder_id: int,
    request: Request,
    withNested: bool = Query(False, description="Include nested folders and templates"),
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[Dict]:
    """Retrieve a folder by ID with optional nested structure."""
    try:
        locale = extract_locale_from_request(request)

        access = user_has_access_to_folder(supabase, user_id, folder_id)
        if access is None:
            raise HTTPException(status_code=404, detail="Folder not found")
        if not access:
            raise HTTPException(status_code=403, detail="Access denied to this folder")

        # Fetch the requested folder
        query = supabase.table("prompt_folders").select("*").eq("id", folder_id)
        query = apply_access_conditions(query, supabase, user_id)
        response = query.single().execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Folder not found")

        folder = process_folder_for_response(response.data, locale)

        if not withNested:
            return APIResponse(success=True, data=folder)

        # Get all accessible folders to build hierarchy
        all_folders_resp = supabase.table("prompt_folders").select("*")
        all_folders_resp = apply_access_conditions(all_folders_resp, supabase, user_id)
        all_folders = all_folders_resp.execute().data or []
        processed_folders = [process_folder_for_response(f, locale) for f in all_folders]

        folder_ids = [f["id"] for f in processed_folders]
        templates_by_folder = await fetch_templates_for_all_folders(supabase, folder_ids, locale)

        # Build nested structure starting from this folder
        subfolders = await build_nested_folder_structure(
            processed_folders, templates_by_folder, parent_folder_id=folder_id, with_templates=True
        )

        if templates_by_folder.get(folder_id):
            folder["templates"] = templates_by_folder[folder_id]
        if subfolders:
            folder["subfolders"] = subfolders

        return APIResponse(success=True, data=folder)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error retrieving folder: {str(e)}")
