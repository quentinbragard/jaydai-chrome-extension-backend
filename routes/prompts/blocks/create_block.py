from fastapi import Depends, HTTPException, Request 
from models.prompts.blocks import BlockCreate, BlockResponse
from models.common import APIResponse
from utils import supabase_helpers
from utils.middleware.localization import extract_locale_from_request 
from utils.prompts.locales import ensure_localized_field
from .helpers import router, supabase, process_block_for_response

@router.post("", response_model=APIResponse[BlockResponse])
async def create_block(
    block: BlockCreate,
    request: Request,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """Create a new block"""
    try:
        # Extract locale from request
        locale = extract_locale_from_request(request)
        print(f"🌍 LOCALE DETECTED: {locale}")  # DEBUG PRINT
        print(f"📝 BLOCK DATA RECEIVED: title='{block.title}', content='{block.content}', description='{block.description}'")  # DEBUG PRINT
        
        # Convert string fields to localized format for database storage
        localized_title = ensure_localized_field(block.title, locale) if block.title else {}
        localized_content = ensure_localized_field(block.content, locale) if block.content else {}
        localized_description = ensure_localized_field(block.description, locale) if block.description else {}
        
        print(f"💾 LOCALIZED FOR DB: title={localized_title}, content={localized_content}, description={localized_description}")  # DEBUG PRINT
        
        block_data = {
            "type": block.type,
            "content": localized_content,
            "title": localized_title,
            "description": localized_description,
            "user_id": user_id,
            "organization_id": block.organization_id,
            "company_id": block.company_id,
        }
        
        response = supabase.table("prompt_blocks").insert(block_data).execute()
        
        if response.data:
            # Process the response to return localized strings
            created_block = response.data[0]
            processed_block = process_block_for_response(created_block, locale)
            print(f"📤 RESPONSE SENT: {processed_block}")  # DEBUG PRINT
            
            return APIResponse(success=True, data=processed_block)
        else:
            raise HTTPException(status_code=400, detail="Failed to create block")
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")  # DEBUG PRINT
        raise HTTPException(status_code=500, detail=f"Error creating block: {str(e)}")