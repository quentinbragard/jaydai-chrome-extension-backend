from typing import Optional, List
from fastapi import Depends, HTTPException, Query
from models.prompts.templates import TemplateResponse
from models.common import APIResponse
from utils import supabase_helpers
from utils.prompts import process_template_for_response, expand_template_blocks
from . import router, supabase

@router.get("", response_model=APIResponse[List[TemplateResponse]])
async def get_templates(
    type: Optional[str] = None,
    folder_ids: Optional[List[int]] = Query(None),
    locale: Optional[str] = "en",
    expand_blocks: bool = True,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """Get templates filtered by type or folder IDs."""
    try:
        query = supabase.table("prompt_templates").select("*")

        if type:
            query = query.eq("type", type)

        if folder_ids:
            query = query.in_("folder_id", folder_ids)

        response = query.execute()
        templates = []
        for template_data in (response.data or []):
            processed = process_template_for_response(template_data, locale)
            if expand_blocks:
                processed = await expand_template_blocks(processed, locale)
            templates.append(processed)

        return APIResponse(success=True, data=templates)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving templates: {str(e)}")
