from typing import Optional
from fastapi import Depends, HTTPException
from models.prompts.templates import TemplateResponse
from models.common import APIResponse
from utils import supabase_helpers
from utils.prompts import process_template_for_response
from utils.access_control import apply_access_conditions
from utils.stripe_config import stripe_config
from routes.stripe import stripe_service
from . import router, supabase

@router.get("/{template_id}", response_model=APIResponse[TemplateResponse])
async def get_template_by_id(
    template_id: str,
    locale: Optional[str] = "en",
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """Get a specific template by ID."""
    try:
        query = supabase.table("prompt_templates").select("*").eq("id", template_id)
        query = apply_access_conditions(query, supabase, user_id)
        response = query.single().execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Template not found")

        template_data = response.data

        if template_data.get("is_free"):
            sub_status = await stripe_service.get_subscription_status(user_id)
            if not (
                sub_status.isActive and
                sub_status.planId == stripe_config.plus_product_id
            ):
                raise HTTPException(status_code=402, detail="Subscription required")

        processed_template = process_template_for_response(template_data, locale)

        return APIResponse(success=True, data=processed_template)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error retrieving template: {str(e)}")
