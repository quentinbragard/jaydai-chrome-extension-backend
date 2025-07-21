from typing import Optional
from models.stripe import SubscriptionStatus
from models.prompts.templates import TemplateResponse
from models.common import APIResponse
from utils import supabase_helpers
from utils.prompts import process_template_for_response
from utils.access_control import apply_access_conditions
from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client, Client
from utils import supabase_helpers
import os
import dotenv

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter()

@router.get("/which-template", response_model=APIResponse[TemplateResponse])
async def get_onboarding_template(
    locale: Optional[str] = "en",
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """Get the onboarding template."""
    try:
        query = supabase.table("prompt_templates").select("*").eq("id", "1")
        query = apply_access_conditions(query, supabase, user_id)
        response = query.single().execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Template not found")

        template_data = response.data
        processed_template = process_template_for_response(template_data, locale)

        return APIResponse(success=True, data=processed_template)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error retrieving template: {str(e)}")
