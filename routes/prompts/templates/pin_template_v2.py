from fastapi import Depends, HTTPException
from models.common import APIResponse
from utils import supabase_helpers
from .helpers import router, supabase

@router.post("/pin-v2/{template_id}")
async def pin_template_v2(
    template_id: int,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[dict]:
    """Pin a template using the pinned_template_ids field."""
    try:
        # Verify template exists and user has access
        template_resp = (
            supabase.table("prompt_templates")
            .select("*")
            .eq("id", template_id)
            .single()
            .execute()
        )
        if not template_resp.data:
            raise HTTPException(status_code=404, detail="Template not found")

        template = template_resp.data
        template_type = template.get("type", "user")

        if template_type == "user" and template.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this template")
        elif template_type == "company":
            metadata_resp = (
                supabase.table("users_metadata")
                .select("company_id")
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            if not metadata_resp.data or metadata_resp.data.get("company_id") != template.get("company_id"):
                raise HTTPException(status_code=403, detail="Access denied to this company template")
        elif template_type == "organization":
            metadata_resp = (
                supabase.table("users_metadata")
                .select("organization_ids")
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            if not metadata_resp.data:
                raise HTTPException(status_code=403, detail="Access denied to this organization template")
            org_ids = metadata_resp.data.get("organization_ids", [])
            if template.get("organization_id") not in org_ids:
                raise HTTPException(status_code=403, detail="Access denied to this organization template")

        # Get current pinned template ids
        user_meta_resp = (
            supabase.table("users_metadata")
            .select("pinned_template_ids")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        current_ids = user_meta_resp.data.get("pinned_template_ids", []) if user_meta_resp.data else []

        if template_id not in current_ids:
            new_ids = current_ids + [template_id]
            if user_meta_resp.data:
                supabase.table("users_metadata").update({"pinned_template_ids": new_ids}).eq("user_id", user_id).execute()
            else:
                supabase.table("users_metadata").insert({"user_id": user_id, "pinned_template_ids": new_ids}).execute()

        return APIResponse(success=True, data={"template_id": template_id, "pinned": True})

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error pinning template: {str(e)}")
