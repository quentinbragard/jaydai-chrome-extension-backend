from fastapi import Depends, HTTPException, Request
from models.common import APIResponse
from utils import supabase_helpers
from .helpers import router, supabase
from utils.middleware.localization import extract_locale_from_request

@router.post("/pin/{template_id}")
async def pin_template(
    template_id: int,
    request: Request,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[dict]:
    """Pin a template for a user."""
    try:
        locale = extract_locale_from_request(request)
        print(f"🌍 PIN_TEMPLATE - LOCALE DETECTED: {locale} for template_id: {template_id}")
        
        # Verify template exists and user has access
        template = supabase.table("prompt_templates").select("*").eq("id", template_id).single().execute()
        if not template.data:
            raise HTTPException(status_code=404, detail="Template not found")
        
        template_data = template.data
        template_type = template_data.get("type", "user")
        
        # Verify user has access to this template
        if template_type == "user" and template_data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this template")
        elif template_type == "company":
            user_metadata = supabase.table("users_metadata").select("company_id").eq("user_id", user_id).single().execute()
            if not user_metadata.data or user_metadata.data.get("company_id") != template_data.get("company_id"):
                raise HTTPException(status_code=403, detail="Access denied to this company template")
        elif template_type == "organization":
            user_metadata = supabase.table("users_metadata").select("organization_ids").eq("user_id", user_id).single().execute()
            if not user_metadata.data:
                raise HTTPException(status_code=403, detail="Access denied to this organization template")
            org_ids = user_metadata.data.get("organization_ids", [])
            if template_data.get("organization_id") not in org_ids:
                raise HTTPException(status_code=403, detail="Access denied to this organization template")
        
        # Get current pinned templates
        user_metadata = supabase.table("users_metadata").select("pinned_templates").eq("user_id", user_id).single().execute()
        current_pinned = user_metadata.data.get("pinned_templates", []) if user_metadata.data else []
        
        # Add template to pinned list if not already pinned
        if template_id not in current_pinned:
            new_pinned = current_pinned + [template_id]
            
            if user_metadata.data:
                # Update existing record
                supabase.table("users_metadata").update({"pinned_templates": new_pinned}).eq("user_id", user_id).execute()
            else:
                # Create new record
                supabase.table("users_metadata").insert({"user_id": user_id, "pinned_templates": new_pinned}).execute()
            
            print(f"📌 PIN_TEMPLATE - Successfully pinned template_id: {template_id}")
            return APIResponse(success=True, data={
                "template_id": template_id,
                "pinned": True,
                "message": "Template pinned successfully"
            })
        else:
            return APIResponse(success=True, data={
                "template_id": template_id,
                "pinned": True,
                "message": "Template already pinned"
            })
            
    except Exception as e:
        print(f"❌ PIN_TEMPLATE ERROR: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error pinning template: {str(e)}")

@router.post("/unpin/{template_id}")
async def unpin_template(
    template_id: int,
    request: Request,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[dict]:
    """Unpin a template for a user."""
    try:
        locale = extract_locale_from_request(request)
        print(f"🌍 UNPIN_TEMPLATE - LOCALE DETECTED: {locale} for template_id: {template_id}")
        
        # Get current pinned templates
        user_metadata = supabase.table("users_metadata").select("pinned_templates").eq("user_id", user_id).single().execute()
        current_pinned = user_metadata.data.get("pinned_templates", []) if user_metadata.data else []
        
        # Remove template from pinned list
        if template_id in current_pinned:
            new_pinned = [tid for tid in current_pinned if tid != template_id]
            supabase.table("users_metadata").update({"pinned_templates": new_pinned}).eq("user_id", user_id).execute()
            
            print(f"📌 UNPIN_TEMPLATE - Successfully unpinned template_id: {template_id}")
            return APIResponse(success=True, data={
                "template_id": template_id,
                "pinned": False,
                "message": "Template unpinned successfully"
            })
        else:
            return APIResponse(success=True, data={
                "template_id": template_id,
                "pinned": False,
                "message": "Template was not pinned"
            })
            
    except Exception as e:
        print(f"❌ UNPIN_TEMPLATE ERROR: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error unpinning template: {str(e)}")