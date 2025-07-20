# routes/onboarding/dismiss.py
from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client, Client
from utils import supabase_helpers
import os
import dotenv

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter()

@router.post("/dismiss")
async def dismiss_onboarding(
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """Dismiss onboarding checklist permanently."""
    try:
        # Check if user metadata exists
        existing_metadata = supabase.table("users_metadata") \
            .select("user_id") \
            .eq("user_id", user_id) \
            .single() \
            .execute()
        
        update_data = {"onboarding_dismissed": True}
        
        if existing_metadata.data:
            # Update existing record
            response = supabase.table("users_metadata") \
                .update(update_data) \
                .eq("user_id", user_id) \
                .execute()
        else:
            # Create new record with default values
            update_data.update({
                "user_id": user_id,
                "first_template_created": False,
                "first_template_used": False,
                "first_block_created": False,
                "keyboard_shortcut_used": False,
                "onboarding_dismissed": True
            })
            response = supabase.table("users_metadata") \
                .insert(update_data) \
                .execute()
        
        return {
            "success": True,
            "message": "Onboarding dismissed successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error dismissing onboarding: {str(e)}")