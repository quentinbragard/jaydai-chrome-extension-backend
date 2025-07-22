# routes/prompts/folders/get_folders_lightweight.py
from typing import Optional, List, Dict
from fastapi import Depends, HTTPException, Query, Request
from models.common import APIResponse
from utils import supabase_helpers
from .helpers import supabase, router
from utils.access_control import apply_access_conditions
from utils.middleware.localization import extract_locale_from_request

@router.get("/lightweight", response_model=APIResponse[Dict])
async def get_folders_lightweight(
    request: Request,
    type: Optional[str] = Query(None, description="Folder type filter"),
    pinned_only: bool = Query(False, description="Return only pinned folders with full structure"),
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[Dict]:
    """
    Get lightweight folder data - only names and IDs for regular folders,
    full structure only for pinned folders.
    """
    try:
        locale = extract_locale_from_request(request)
        
        if pinned_only:
            # Get user's pinned folder IDs
            user_meta_resp = supabase.table("users_metadata").select("pinned_folder_ids").eq("user_id", user_id).single().execute()
            pinned_ids = user_meta_resp.data.get("pinned_folder_ids", []) if user_meta_resp.data else []
            
            if not pinned_ids:
                return APIResponse(success=True, data={"folders": {}})
            
            # Return full structure only for pinned folders
            return await get_full_pinned_folders_structure(supabase, user_id, pinned_ids, locale)
        
        # For non-pinned folders, return only lightweight data
        folder_types = [type] if type else ["user", "organization", "company"]
        result = {"folders": {}}
        
        for folder_type in folder_types:
            query = supabase.table("prompt_folders").select("id, title, parent_folder_id, type")
            query = query.eq("type", folder_type)
            query = apply_access_conditions(query, supabase, user_id)
            response = query.execute()
            
            # Process lightweight folder data
            lightweight_folders = []
            for folder in (response.data or []):
                processed_folder = {
                    "id": folder["id"],
                    "title": extract_localized_title(folder.get("title", {}), locale),
                    "parent_folder_id": folder.get("parent_folder_id"),
                    "type": folder.get("type"),
                    "has_children": False,  # Will be computed if needed
                    "template_count": 0     # Will be computed if needed
                }
                lightweight_folders.append(processed_folder)
            
            result["folders"][folder_type] = lightweight_folders
        
        return APIResponse(success=True, data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving lightweight folders: {str(e)}")

async def get_full_pinned_folders_structure(supabase, user_id: str, pinned_ids: List[int], locale: str):
    """Get full structure only for pinned folders"""
    # Implementation similar to existing get_folders but only for pinned IDs
    query = supabase.table("prompt_folders").select("*").in_("id", pinned_ids)
    query = apply_access_conditions(query, supabase, user_id)
    response = query.execute()
    
    # Build full structure with templates for pinned folders only
    # ... (implement full structure building)
    
    return {"folders": {"pinned": response.data}}

def extract_localized_title(title_obj, locale: str) -> str:
    """Extract localized title from JSONB field"""
    if isinstance(title_obj, dict):
        return title_obj.get(locale) or title_obj.get('en') or ''
    return str(title_obj) or ''


