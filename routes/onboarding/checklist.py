# routes/onboarding/checklist.py
from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client, Client
from utils import supabase_helpers
import os
import dotenv

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter()

@router.get("/checklist")
async def get_onboarding_checklist(
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """Get user's onboarding checklist status."""
    try:
        # Get user metadata for onboarding tracking
        metadata_response = supabase.table("users_metadata") \
            .select("first_template_created, first_template_used, first_block_created, keyboard_shortcut_used, onboarding_dismissed") \
            .eq("user_id", user_id) \
            .single() \
            .execute()
        
        # Default values if no metadata exists
        if metadata_response.data:
            metadata = metadata_response.data
        else:
            # Create initial metadata record if it doesn't exist
            initial_metadata = {
                "user_id": user_id,
                "first_template_created": False,
                "first_template_used": False,
                "first_block_created": False,
                "keyboard_shortcut_used": False,
                "onboarding_dismissed": False
            }
            
            insert_response = supabase.table("users_metadata") \
                .insert(initial_metadata) \
                .execute()
            
            metadata = initial_metadata
        
        first_template_created = metadata.get("first_template_created", False)
        first_template_used = metadata.get("first_template_used", False)
        first_block_created = metadata.get("first_block_created", False)
        keyboard_shortcut_used = metadata.get("keyboard_shortcut_used", False)
        is_dismissed = metadata.get("onboarding_dismissed", False)
        
        # Calculate progress
        completed_actions = [
            first_template_created,
            first_template_used,
            first_block_created,
            keyboard_shortcut_used
        ]
        
        completed_count = sum(completed_actions)
        total_count = 4
        is_complete = completed_count == total_count
        
        return {
            "success": True,
            "data": {
                "first_template_created": first_template_created,
                "first_template_used": first_template_used,
                "first_block_created": first_block_created,
                "keyboard_shortcut_used": keyboard_shortcut_used,
                "progress": f"{completed_count}/{total_count}",
                "completed_count": completed_count,
                "total_count": total_count,
                "is_complete": is_complete,
                "is_dismissed": is_dismissed
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching onboarding checklist: {str(e)}")