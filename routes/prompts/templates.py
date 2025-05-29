# routes/prompts/templates.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List, Union, Dict
from supabase import create_client, Client
import os
from utils import supabase_helpers
from utils.prompts import (
    process_template_for_response,
    expand_template_blocks,
    validate_block_access,
    normalize_localized_field
)
import dotenv
from models.prompts.templates import TemplateCreate, TemplateUpdate, TemplateResponse, TemplateMetadata
from models.common import APIResponse
dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


router = APIRouter(tags=["Templates"])

# ---------------------- HELPER FUNCTIONS ----------------------

async def get_user_organizations(user_id: str) -> List[str]:
    """Get all organization IDs a user belongs to"""
    try:
        user_metadata = supabase.table("users_metadata").select("organization_ids").eq("user_id", user_id).single().execute()
        if user_metadata.data and user_metadata.data.get("organization_ids"):
            return user_metadata.data.get("organization_ids", [])
        return []
    except Exception as e:
        print(f"Error fetching user organizations: {str(e)}")
        return []

async def get_user_company(user_id: str) -> Optional[str]:
    """Get company ID a user belongs to"""
    try:
        user_metadata = supabase.table("users_metadata").select("company_id").eq("user_id", user_id).single().execute()
        if user_metadata.data:
            return user_metadata.data.get("company_id")
        return None
    except Exception as e:
        print(f"Error fetching user company: {str(e)}")
        return None
    

# ---------------------- ROUTE HANDLERS ----------------------

@router.get("", response_model=APIResponse[List[TemplateResponse]])
async def get_templates(
    type: Optional[str] = None,
    locale: Optional[str] = "en",
    expand_blocks: bool = True,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get templates with optional filtering by type."""
    try:
        if type == "user":
            return await get_user_templates(user_id, locale, expand_blocks)
        elif type == "official":
            return await get_official_templates(user_id, locale, expand_blocks)
        elif type == "company":
            return await get_company_templates(user_id, locale, expand_blocks)
        else:
            # Get all templates
            return await get_all_templates(user_id, locale, expand_blocks)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving templates: {str(e)}")

@router.get("/unorganized", response_model=APIResponse[List[TemplateResponse]])
async def get_unorganized_templates_endpoint(
    locale: Optional[str] = "en",
    expand_blocks: bool = True,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get all templates that are not organized in any folder."""
    try:
        # Get user templates without folder
        query = supabase.table("prompt_templates").select("*")
        query = query.eq("user_id", user_id).eq("type", "user").is_("folder_id", "null")
        response = query.execute()
        
        templates = []
        for template_data in (response.data or []):
            # Process template for response
            processed_template = process_template_for_response(template_data, locale)
            
            # Expand blocks if requested
            if expand_blocks:
                processed_template = await expand_template_blocks(processed_template, locale)
            
            templates.append(processed_template)
        
        return APIResponse(success=True, data=templates)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving unorganized templates: {str(e)}")

async def get_user_templates(user_id: str, locale: str = "en", expand_blocks: bool = True):
    """Get user's personal templates."""
    try:
        # Get user templates
        response = supabase.table("prompt_templates").select("*").eq("user_id", user_id).eq("type", "user").execute()
        
        templates = []
        for template_data in (response.data or []):
            # Process template for response
            processed_template = process_template_for_response(template_data, locale)
            
            # Expand blocks if requested
            if expand_blocks:
                processed_template = await expand_template_blocks(processed_template, locale)
            
            templates.append(processed_template)
        
        return templates
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving user templates: {str(e)}")

async def get_official_templates(user_id: Optional[str] = None, locale: str = "en", expand_blocks: bool = True):
    """
    Get official prompt templates.
    Official templates now include:
    1. Templates with no user_id, company_id, or organization_id
    2. Templates belonging to organizations the user is a member of
    """
    try:
        # Get user's organizations
        org_ids = await get_user_organizations(user_id) if user_id else []
        
        # Start with a base query
        query = supabase.table("prompt_templates").select("*").eq("type", "official")
        
        # Use proper PostgREST filter syntax
        # First, get templates that have no IDs (truly official)
        no_ids_query = query.is_("user_id", "null").is_("company_id", "null").is_("organization_id", "null")
        response = no_ids_query.execute()
        templates = response.data or []
        
        # Then, if user has organizations, get templates from those orgs
        if org_ids:
            for org_id in org_ids:
                org_query = supabase.table("prompt_templates").select("*") \
                    .eq("type", "official") \
                    .eq("organization_id", org_id)
                org_response = org_query.execute()
                if org_response.data:
                    templates.extend(org_response.data)
        
        # Process templates
        processed_templates = []
        for template_data in templates:
            # Process template for response
            processed_template = process_template_for_response(template_data, locale)
            
            # Expand blocks if requested
            if expand_blocks:
                processed_template = await expand_template_blocks(processed_template, locale)
            
            processed_templates.append(processed_template)
        
        return processed_templates
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving official templates: {str(e)}")
    
    
async def get_company_templates(user_id: Optional[str] = None, locale: str = "en", expand_blocks: bool = True):
    """Get company templates for the user's company."""
    try:
        company_id = None
        
        if user_id:
            # Get user's company_id
            company_id = await get_user_company(user_id)
        
        if not company_id:
            return []
        
        # Get company templates
        response = supabase.table("prompt_templates").select("*").eq("type", "company").eq("company_id", company_id).execute()
        
        templates = []
        for template_data in (response.data or []):
            # Process template for response
            processed_template = process_template_for_response(template_data, locale)
            
            # Expand blocks if requested
            if expand_blocks:
                processed_template = await expand_template_blocks(processed_template, locale)
            
            templates.append(processed_template)
        
        return templates
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving company templates: {str(e)}")

async def get_all_templates(user_id: str, locale: str = "en", expand_blocks: bool = True):
    """Get templates organized by type (official, company, and user)."""
    #try:
    # Get all template types
    user_templates = await get_user_templates(user_id, locale, expand_blocks)
    official_templates = await get_official_templates(user_id, locale, expand_blocks)
    company_templates = await get_company_templates(user_id, locale, expand_blocks)
    
    # Combine all templates
    all_templates = user_templates + official_templates + company_templates

    
    return APIResponse(success=True, data=all_templates)
        
    #except Exception as e:
    #    raise HTTPException(status_code=500, detail=f"Error retrieving all templates: {str(e)}")

@router.post("", response_model=APIResponse[TemplateResponse])
async def create_template(
    template: TemplateCreate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
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
        "metadata": metadata_dict,  # Store metadata as JSON
        "description": description_data,
        "folder_id": template.folder_id,
        "tags": template.tags or [],
        "usage_count": 0
    }
    
    # Insert template
    response = supabase.table("prompt_templates").insert(template_data).execute()
    
    if response.data:
        # Process template for response
        processed_template = process_template_for_response(response.data[0], template.locale)
        
        # Expand blocks in response
        expanded_template = await expand_template_blocks(processed_template, template.locale)
        
        return APIResponse(success=True, data=expanded_template)
    else:
        raise HTTPException(status_code=400, detail="Failed to create template")

@router.put("/{template_id}", response_model=APIResponse[TemplateResponse])
async def update_template(
    template_id: str,
    template: TemplateUpdate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Update an existing template with metadata support."""
    try:
        # Check if template exists and user has permission
        existing_template = supabase.table("prompt_templates").select("*").eq("id", template_id).single().execute()
        
        if not existing_template.data:
            raise HTTPException(status_code=404, detail="Template not found")
        
        template_data = existing_template.data
        
        # Check permissions (same as before)
        if template_data.get("type") == "user" and template_data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Prepare update data
        update_data = {}
        current_locale = "en"  # Default locale
        
        if template.title is not None:
            update_data["title"] = normalize_localized_field(template.title, current_locale)
        
        if template.content is not None:
            update_data["content"] = normalize_localized_field(template.content, current_locale)
        
        if template.blocks is not None:
            # Validate referenced blocks
            block_ids = [bid for bid in template.blocks if bid != 0]
            if block_ids:
                has_access = await validate_block_access(block_ids, user_id)
                if not has_access:
                    raise HTTPException(status_code=403, detail="Access denied to one or more referenced blocks")
            update_data["blocks"] = template.blocks
        
        if template.metadata is not None:
            # Validate metadata blocks
            metadata_block_ids = []
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
                metadata_block_ids = [bid for bid in metadata_block_ids if bid != 0]
                
            if metadata_block_ids:
                has_access = await validate_block_access(metadata_block_ids, user_id)
                if not has_access:
                    raise HTTPException(status_code=403, detail="Access denied to one or more metadata blocks")
            
            update_data["metadata"] = template.metadata.dict()
        
        if template.description is not None:
            update_data["description"] = normalize_localized_field(template.description, current_locale)
        
        if template.folder_id is not None:
            update_data["folder_id"] = template.folder_id
        
        if template.tags is not None:
            update_data["tags"] = template.tags
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        # Update template
        response = supabase.table("prompt_templates").update(update_data).eq("id", template_id).execute()
        
        if response.data:
            # Process template for response
            processed_template = process_template_for_response(response.data[0], current_locale)
            
            # Expand blocks in response
            expanded_template = await expand_template_blocks(processed_template, current_locale)
            
            return APIResponse(success=True, data=expanded_template)
        else:
            raise HTTPException(status_code=400, detail="Failed to update template")
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error updating template: {str(e)}")



@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Delete a template."""
    try:
        # Verify template exists and user has permission
        template_response = supabase.table("prompt_templates").select("*").eq("id", template_id).single().execute()
        
        if not template_response.data:
            raise HTTPException(status_code=404, detail="Template not found")
        
        template_data = template_response.data
        
        # Check permissions
        if template_data.get("type") == "user" and template_data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        elif template_data.get("type") == "company":
            # Check if user belongs to the same company
            user_company = await get_user_company(user_id)
            if template_data.get("company_id") != user_company:
                raise HTTPException(status_code=403, detail="Access denied")
        elif template_data.get("type") == "official" and template_data.get("organization_id"):
            # Check if user belongs to the organization
            user_orgs = await get_user_organizations(user_id)
            if template_data.get("organization_id") not in user_orgs:
                raise HTTPException(status_code=403, detail="Access denied")
        elif template_data.get("type") == "official" and not template_data.get("organization_id"):
            # Cannot delete global official templates
            raise HTTPException(status_code=403, detail="Cannot delete global official templates")
        
        # Delete template
        supabase.table("prompt_templates").delete().eq("id", template_id).execute()
        
        return APIResponse(success=True, message="Template deleted")
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error deleting template: {str(e)}")

@router.post("/use/{template_id}")
async def track_template_usage(
    template_id: str,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Track template usage."""
    try:
        # Get current template
        template_response = supabase.table("prompt_templates").select("usage_count").eq("id", template_id).single().execute()
        
        if not template_response.data:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Increment usage count
        current_count = template_response.data.get("usage_count", 0)
        
        # Update usage count and last used timestamp
        update_data = {
            "usage_count": current_count + 1,
            "last_used_at": "now()"
        }
        
        supabase.table("prompt_templates").update(update_data).eq("id", template_id).execute()
        
        return APIResponse(success=True, data={
            "usage_count": current_count + 1
        })
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error tracking template usage: {str(e)}")

@router.get("/{template_id}", response_model=APIResponse[TemplateResponse])
async def get_template_by_id(
    template_id: str,
    locale: Optional[str] = "en",
    expand_blocks: bool = True,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get a specific template by ID."""
    try:
        # Get template
        response = supabase.table("prompt_templates").select("*").eq("id", template_id).single().execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Template not found")
        
        template_data = response.data
        
        # Check access permissions
        if template_data.get("type") == "user" and template_data.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        elif template_data.get("type") == "organization":
            # Check if user belongs to the same organization
            user_metadata = supabase.table("users_metadata").select("organization_id").eq("user_id", user_id).single().execute()
            user_org_id = user_metadata.data.get("organization_id") if user_metadata.data else None
            if template_data.get("organization_id") != user_org_id:
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Process template for response
        processed_template = process_template_for_response(template_data, locale)
        
        # Expand blocks if requested
        if expand_blocks:
            processed_template = await expand_template_blocks(processed_template, locale)
        
        return APIResponse(success=True, data=processed_template)
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error retrieving template: {str(e)}")

@router.post("/{template_id}/duplicate", response_model=APIResponse[TemplateResponse])
async def duplicate_template(
    template_id: str,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Duplicate an existing template."""
    try:
        # Get the original template
        original_response = supabase.table("prompt_templates").select("*").eq("id", template_id).single().execute()
        
        if not original_response.data:
            raise HTTPException(status_code=404, detail="Template not found")
        
        original_template = original_response.data
        
        # Check if user has access to the template
        if original_template.get("type") == "user" and original_template.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        elif original_template.get("type") == "organization":
            # Check if user belongs to the same organization
            user_metadata = supabase.table("users_metadata").select("organization_id").eq("user_id", user_id).single().execute()
            user_org_id = user_metadata.data.get("organization_id") if user_metadata.data else None
            if original_template.get("organization_id") != user_org_id:
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Validate referenced blocks
        blocks = original_template.get("blocks", [])
        block_ids = [bid for bid in blocks if bid != 0]
        if block_ids:
            has_access = await validate_block_access(block_ids, user_id)
            if not has_access:
                raise HTTPException(status_code=403, detail="Access denied to one or more referenced blocks")
        
        # Create duplicate template data
        duplicate_data = {
            "user_id": user_id,
            "organization_id": None,  # Always create as user template
            "type": "user",  # Always create as user template
            "title": original_template["title"],
            "content": original_template["content"],
            "blocks": blocks,
            "description": original_template.get("description"),
            "folder_id": None,  # Don't duplicate folder assignment
            "tags": original_template.get("tags", []),
            "usage_count": 0
        }
        
        # Insert duplicate template
        response = supabase.table("prompt_templates").insert(duplicate_data).execute()
        
        if response.data:
            # Process template for response
            processed_template = process_template_for_response(response.data[0], "en")
            
            # Expand blocks in response
            expanded_template = await expand_template_blocks(processed_template, "en")
            
            return APIResponse(success=True, data=expanded_template)
        else:
            raise HTTPException(status_code=400, detail="Failed to duplicate template")
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error duplicating template: {str(e)}")