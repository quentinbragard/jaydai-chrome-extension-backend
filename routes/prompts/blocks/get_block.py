from typing import List, Optional
from fastapi import Depends, HTTPException, Request
from .helpers import router, supabase, get_access_conditions, process_block_for_response
from models.prompts.blocks import BlockResponse, BlockType
from models.common import APIResponse
from utils import supabase_helpers
from utils.middleware.localization import extract_locale_from_request

@router.get("", response_model=APIResponse[List[BlockResponse]])
async def get_blocks(
    request: Request,
    type: Optional[BlockType] = None,
    published: Optional[bool] = None,
    q: Optional[str] = None,
    ids: Optional[str] = None,  # New parameter for comma-separated IDs
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """Get blocks accessible to the user"""
    try:
        # Extract locale from request
        locale = extract_locale_from_request(request)
        
        query = supabase.table("prompt_blocks").select("*")
        
        # If specific IDs are requested, filter by those first
        if ids:
            try:
                block_ids = [int(id.strip()) for id in ids.split(',') if id.strip()]
                if block_ids:
                    query = query.in_("id", block_ids)
                    # When fetching specific IDs, don't filter by published status
                    # as we need to get unpublished blocks referenced in metadata
                    published = None
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid block IDs format")
        
        if type:
            query = query.eq("type", type)
        if published is not None:
            query = query.eq("published", published)
        if q:
            query = query.or_(f"title.ilike.%{q}%,content.ilike.%{q}%")
        
        access_conditions = get_access_conditions(supabase, user_id)
        query = query.or_(",".join(access_conditions))
        query = query.order("created_at", desc=True)
        response = query.execute()

        # Process blocks for localized response
        processed_blocks = []
        for block_data in (response.data or []):
            processed_block = process_block_for_response(block_data, locale)
            processed_blocks.append(processed_block)

        print(f"📤 GET_BLOCKS - RETURNING {len(processed_blocks)} blocks in {locale}")

        return APIResponse(success=True, data=processed_blocks)
    except Exception as e:
        print(f"❌ GET_BLOCKS ERROR: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error fetching blocks: {str(e)}")