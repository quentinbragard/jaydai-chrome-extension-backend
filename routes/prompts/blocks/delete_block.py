from fastapi import Depends, HTTPException, Request  # ADD Request import
from models.common import APIResponse
from utils import supabase_helpers
from .helpers import router, supabase
from utils.middleware.localization import extract_locale_from_request  # ADD this import

@router.delete("/{block_id}")
async def delete_block(
    block_id: int,
    request: Request,  # ADD this parameter
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """Delete a block (only if user owns it)"""
    try:
        # Extract locale from request (for logging consistency)
        locale = extract_locale_from_request(request)
        print(f"🌍 DELETE_BLOCK - LOCALE DETECTED: {locale} for block_id: {block_id}")  # DEBUG PRINT
        
        existing_block = supabase.table("prompt_blocks").select("*").eq("id", block_id).eq("user_id", user_id).single().execute()
        print(existing_block.data)

        if not existing_block.data:
            raise HTTPException(status_code=404, detail="Block not found or access denied")

        templates_using_block = (
            supabase.table("prompt_templates")
            .select("id")
            .filter("blocks", "cs", f"{{{block_id}}}")
            .execute()
        )

        if templates_using_block.data:
            raise HTTPException(status_code=400, detail="Cannot delete block that is being used in templates")

        supabase.table("prompt_blocks").delete().eq("id", block_id).execute()
        
        print(f"🗑️ DELETE_BLOCK - Successfully deleted block_id: {block_id}")  # DEBUG PRINT

        return APIResponse(success=True, message="Block deleted")

    except Exception as e:
        print(f"❌ DELETE_BLOCK ERROR: {str(e)}")  # DEBUG PRINT
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error deleting block: {str(e)}")