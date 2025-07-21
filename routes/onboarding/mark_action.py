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
        existing_metadata = (
            supabase.table("users_metadata")
            .select("*")
            .eq("user_id", user_id)
            .single()
            .execute()
        )

        update_data = {}
        if request.action in ["first_template_used", "keyboard_shortcut_used"]:
            update_data[request.action] = True

        if existing_metadata.data:
            # Update existing record only if there is something to update
            if update_data:
                response = (
                    supabase.table("users_metadata")
                    .update(update_data)
                    .eq("user_id", user_id)
                    .execute()
                )
            else:
                response = existing_metadata
        else:
            # Create new record with default values
            update_data["user_id"] = user_id
            update_data.update(
                {
                    "first_template_used": False,
                    "keyboard_shortcut_used": False,
                    "onboarding_dismissed": False,
                }
            )
            if request.action in ["first_template_used", "keyboard_shortcut_used"]:
                update_data[request.action] = True

            response = supabase.table("users_metadata").insert(update_data).execute()
        
        # Get updated metadata to return current status
        updated_metadata = (
            supabase.table("users_metadata")
            .select(
                "first_template_used, keyboard_shortcut_used, onboarding_dismissed"
            )
            .eq("user_id", user_id)
            .single()
            .execute()
        )

        # Check if user has created at least one template
        templates_resp = (
            supabase.table("prompt_templates")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        template_count = getattr(templates_resp, "count", None)
        if template_count is None:
            template_count = len(templates_resp.data or [])
        first_template_created = template_count > 0

        # Check if user has created at least one block
        blocks_resp = (
            supabase.table("prompt_blocks")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        block_count = getattr(blocks_resp, "count", None)
        if block_count is None:
            block_count = len(blocks_resp.data or [])
        first_block_created = block_count > 0
        
        if updated_metadata.data:
            metadata = updated_metadata.data

            # Calculate progress using derived values for creation actions
            completed_actions = [
                first_template_created,
                metadata.get("first_template_used", False),
                first_block_created,
                metadata.get("keyboard_shortcut_used", False),
            ]

            completed_count = sum(completed_actions)
            total_count = 4
            is_complete = completed_count == total_count

            return {
                "success": True,
                "data": {
                    "first_template_created": first_template_created,
                    "first_template_used": metadata.get("first_template_used", False),
                    "first_block_created": first_block_created,
                    "keyboard_shortcut_used": metadata.get("keyboard_shortcut_used", False),
                    "progress": f"{completed_count}/{total_count}",
                    "completed_count": completed_count,
                    "total_count": total_count,
                    "is_complete": is_complete,
                    "is_dismissed": metadata.get("onboarding_dismissed", False),
                },
                "message": f"Action {request.action} marked as completed",
            }
        else:
            raise Exception("Failed to retrieve updated metadata")
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error marking onboarding action: {str(e)}")