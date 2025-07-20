from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
import os
import dotenv

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter()

class OnboardingActionRequest(BaseModel):
    action: str

@router.post("/mark-action")
async def mark_onboarding_action(
    request: OnboardingActionRequest,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """Mark an onboarding action as completed."""
    try:
        valid_actions = [
            "first_template_created",
            "first_template_used", 
            "first_block_created",
            "keyboard_shortcut_used"
        ]
        
        if request.action not in valid_actions:
            raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")
        
        # Check if user metadata exists
        existing_metadata = supabase.table("users_metadata") \
            .select("user_id") \
            .eq("user_id", user_id) \
            .single() \
            .execute()
        
        update_data = {request.action: True}
        
        if existing_metadata.data:
            # Update existing record
            response = supabase.table("users_metadata") \
                .update(update_data) \
                .eq("user_id", user_id) \
                .execute()
        else:
            # Create new record
            update_data["user_id"] = user_id
            response = supabase.table("users_metadata") \
                .insert(update_data) \
                .execute()
        
        return {
            "success": True,
            "message": f"Action {request.action} marked as completed"
        }
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error marking onboarding action: {str(e)}") 