# routes/onboarding/mark_action.py
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
            .select("*") \
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
            # Set default values for other fields
            update_data.update({
                "first_template_created": False,
                "first_template_used": False,
                "first_block_created": False,
                "keyboard_shortcut_used": False,
                "onboarding_dismissed": False
            })
            # Override the specific action we're marking
            update_data[request.action] = True
            
            response = supabase.table("users_metadata") \
                .insert(update_data) \
                .execute()
        
        # Get updated metadata to return current status
        updated_metadata = supabase.table("users_metadata") \
            .select("first_template_created, first_template_used, first_block_created, keyboard_shortcut_used, onboarding_dismissed") \
            .eq("user_id", user_id) \
            .single() \
            .execute()
        
        if updated_metadata.data:
            metadata = updated_metadata.data
            
            # Calculate progress
            completed_actions = [
                metadata.get("first_template_created", False),
                metadata.get("first_template_used", False),
                metadata.get("first_block_created", False),
                metadata.get("keyboard_shortcut_used", False)
            ]
            
            completed_count = sum(completed_actions)
            total_count = 4
            is_complete = completed_count == total_count
            
            return {
                "success": True,
                "data": {
                    "first_template_created": metadata.get("first_template_created", False),
                    "first_template_used": metadata.get("first_template_used", False),
                    "first_block_created": metadata.get("first_block_created", False),
                    "keyboard_shortcut_used": metadata.get("keyboard_shortcut_used", False),
                    "progress": f"{completed_count}/{total_count}",
                    "completed_count": completed_count,
                    "total_count": total_count,
                    "is_complete": is_complete,
                    "is_dismissed": metadata.get("onboarding_dismissed", False)
                },
                "message": f"Action {request.action} marked as completed"
            }
        else:
            raise Exception("Failed to retrieve updated metadata")
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error marking onboarding action: {str(e)}")