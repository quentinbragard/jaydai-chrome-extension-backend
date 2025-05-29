from fastapi import Depends, HTTPException
from typing import Optional
from models.prompts.templates import TemplateCreate, TemplateResponse, TemplateMetadata
from models.common import APIResponse
from utils import supabase_helpers
from utils.prompts import process_template_for_response, expand_template_blocks, validate_block_access, normalize_localized_field
from . import router, supabase

@router.post("", response_model=APIResponse[TemplateResponse])
async def create_template(
    template: TemplateCreate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """Create a new template with blocks and metadata support."""
    # Validate referenced blocks in both blocks array and metadata
    all_block_ids = []

    # Collect block IDs from blocks array
    block_ids = [bid for bid in (template.blocks or []) if bid != 0]
    all_block_ids.extend(block_ids)

    # Collect block IDs from metadata
    if template.metadata:
        metadata_block_ids = [
            template.metadata.role,
            template.metadata.main_context,
            template.metadata.main_goal,
            template.metadata.tone_style or 0,
            template.metadata.output_format or 0,
            template.metadata.audience or 0,
            template.metadata.output_language or 0
        ]
        all_block_ids.extend([bid for bid in metadata_block_ids if bid != 0])

    # Validate all blocks
    if all_block_ids:
        has_access = await validate_block_access(all_block_ids, user_id)
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to one or more referenced blocks")

    # Get user metadata
    user_metadata_response = supabase.table("users_metadata").select("company_id").eq("user_id", user_id).single().execute()
    user_metadata = user_metadata_response.data or {}

    # Normalize localized fields
    title_data = normalize_localized_field(template.title, template.locale)
    content_data = normalize_localized_field(template.content, template.locale)
    description_data = normalize_localized_field(template.description, template.locale) if template.description else {}

    # Ensure metadata has required fields
    metadata = template.metadata or TemplateMetadata()
    metadata_dict = metadata.dict()

    # Prepare template data
    template_data = {
        "user_id": user_id if template.type == "user" else None,
        "company_id": user_metadata.get("company_id") if template.type == "company" else None,
        "organization_id": None,
        "type": template.type,
        "title": title_data,
        "content": content_data,
        "blocks": template.blocks or [],
        "metadata": metadata_dict,
        "description": description_data,
        "folder_id": template.folder_id,
        "tags": template.tags or [],
        "usage_count": 0
    }

    # Insert template
    response = supabase.table("prompt_templates").insert(template_data).execute()

    if response.data:
        processed_template = process_template_for_response(response.data[0], template.locale)
        expanded_template = await expand_template_blocks(processed_template, template.locale)
        return APIResponse(success=True, data=expanded_template)
    else:
        raise HTTPException(status_code=400, detail="Failed to create template")
