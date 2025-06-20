from fastapi import Depends, HTTPException, Request
from models.common import APIResponse
from utils import supabase_helpers
from .helpers import router, supabase, create_localized_field
from models.prompts.folders import FolderCreate
from utils.middleware.localization import extract_locale_from_request 
from utils.prompts.locales import ensure_localized_field


@router.post("")
async def create_folder(
    folder: FolderCreate,
    request: Request,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[dict]:
    """Create a new user folder."""
    try:
        locale = extract_locale_from_request(request)
        localized_title = ensure_localized_field(folder.title, locale) if folder.title else {}
        localized_description = ensure_localized_field(folder.description, locale) if folder.description else {}


        response = supabase.table("prompt_folders").insert({
            "user_id": user_id,
            "organization_id": None,
            "company_id": None,
            "type": "user",
            "parent_folder_id": folder.parent_id,
            "title": localized_title,
            "description": localized_description,
        }).execute()

        if response.data:
            from utils.prompts.folders import process_folder_for_response
            processed_folder = process_folder_for_response(response.data[0])

        return APIResponse(success=True, data=processed_folder)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating folder: {str(e)}")
