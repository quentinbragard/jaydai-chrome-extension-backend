"""
Utility functions for template operations in the prompts system.
"""
from typing import Dict, List, Optional, Any
from supabase import Client
from .locales import extract_localized_field, create_localized_field

def process_template_for_response(template: Dict, locale: str = "en") -> Dict:
    """
    Process a template record for API response with proper locale handling.
    
    Args:
        template: Raw template record from database
        locale: Requested locale
        
    Returns:
        Processed template dict ready for API response
    """
    processed_template = template.copy()
    template_type = template.get("type", "")
    
    # Determine if this is user content
    is_user_content = template_type == "user"
    
    # For all templates now, we use JSONB fields for title, content, and description
    if "title" in template:
        processed_template["title"] = extract_localized_field(template["title"], locale, is_user_content)
    
    if "content" in template:
        processed_template["content"] = extract_localized_field(template["content"], locale, is_user_content)
    
    if "description" in template:
        processed_template["description"] = extract_localized_field(template["description"], locale, is_user_content)
    
    return processed_template

async def fetch_templates_for_folders(
    supabase: Client,
    folder_ids: List[int],
    folder_type: str,
    locale: str = "en"
) -> List[Dict]:
    """
    Fetch templates for given folder IDs with proper locale handling.
    
    Args:
        supabase: Supabase client
        folder_ids: List of folder IDs
        folder_type: Type of folders ("user", "official", "organization")
        locale: Requested locale
        
    Returns:
        List of processed template dicts
    """
    if not folder_ids:
        return []
    
    response = supabase.table("prompt_templates") \
        .select("*") \
        .eq("type", folder_type) \
        .in_("folder_id", folder_ids) \
        .execute()
    
    templates = response.data or []
    
    # Process templates for locale
    return [process_template_for_response(template, locale) for template in templates]

async def fetch_templates_by_type(
    supabase: Client,
    template_type: str,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    locale: str = "en"
) -> List[Dict]:
    """
    Fetch templates by type with locale handling.
    
    Args:
        supabase: Supabase client
        template_type: Type of templates ("user", "official", "organization")
        user_id: User ID for user templates
        organization_id: Organization ID for org templates
        locale: Requested locale
        
    Returns:
        List of processed template dicts
    """
    query = supabase.table("prompt_templates").select("*").eq("type", template_type)
    
    # Add additional filters based on type
    if template_type == "user" and user_id:
        query = query.eq("user_id", user_id)
    elif template_type == "organization" and organization_id:
        # Get templates for specific organization through folder relationships
        org_folders = supabase.table("prompt_folders").select("id").eq("organization_id", organization_id).execute()
        if org_folders.data:
            folder_ids = [f["id"] for f in org_folders.data]
            query = query.in_("folder_id", folder_ids)
        else:
            return []
    
    response = query.execute()
    templates = response.data or []
    
    return [process_template_for_response(template, locale) for template in templates]

async def get_unorganized_templates(
    supabase: Client,
    user_id: str,
    locale: str = "en"
) -> List[Dict]:
    """
    Get templates that are not organized in any folder.
    
    Args:
        supabase: Supabase client
        user_id: User ID
        locale: Requested locale
        
    Returns:
        List of unorganized template dicts
    """
    response = supabase.table("prompt_templates") \
        .select("*") \
        .eq("type", "user") \
        .eq("user_id", user_id) \
        .is_("folder_id", "null") \
        .execute()
    
    templates = response.data or []
    return [process_template_for_response(template, locale) for template in templates]

async def create_template(
    supabase: Client,
    template_data: Dict,
    user_id: str,
    locale: str = "en"
) -> Dict:
    """
    Create a new template with proper locale handling.
    For user templates, always use the first locale (no specific locale required).
    
    Args:
        supabase: Supabase client
        template_data: Template data dict
        user_id: User ID
        locale: Locale for the template content (only used for non-user templates)
        
    Returns:
        Created template dict
    """
    # Prepare template data with JSONB fields
    insert_data = {
        "type": template_data.get("type", "user"),
        "user_id": user_id,
        "folder_id": template_data.get("folder_id"),
        "tags": template_data.get("tags", [])
    }
    
    # For user templates, we don't care about locale - just use 'en' as default
    template_type = template_data.get("type", "user")
    if template_type == "user":
        effective_locale = "en"  # Always use 'en' for user content, but it doesn't matter since we'll take first available
    else:
        effective_locale = locale
    
    # Create localized JSONB fields
    if "title" in template_data:
        insert_data["title"] = create_localized_field(template_data["title"], effective_locale)
    
    if "content" in template_data:
        insert_data["content"] = create_localized_field(template_data["content"], effective_locale)
    
    if "description" in template_data:
        insert_data["description"] = create_localized_field(template_data["description"], effective_locale)
    
    response = supabase.table("prompt_templates").insert(insert_data).execute()
    
    if response.data:
        return process_template_for_response(response.data[0], locale)
    
    return {}

async def update_template(
    supabase: Client,
    template_id: str,
    template_data: Dict,
    user_id: str,
    locale: str = "en"
) -> Dict:
    """
    Update an existing template with proper locale handling.
    For user templates, just update with first available value.
    
    Args:
        supabase: Supabase client
        template_id: Template ID
        template_data: Updated template data
        user_id: User ID
        locale: Locale for the updates (only relevant for non-user templates)
        
    Returns:
        Updated template dict
    """
    # Verify template belongs to user
    verify = supabase.table("prompt_templates").select("*").eq("id", template_id).eq("user_id", user_id).execute()
    
    if not verify.data:
        raise ValueError("Template not found or doesn't belong to user")
    
    existing_template = verify.data[0]
    update_data = {}
    
    # Update tags and folder_id if provided
    if "tags" in template_data:
        update_data["tags"] = template_data["tags"]
    
    if "folder_id" in template_data:
        update_data["folder_id"] = template_data["folder_id"]
    
    # Get template type to determine locale handling
    template_type = existing_template.get("type", "user")
    
    # Update localized fields
    for field in ["title", "content", "description"]:
        if field in template_data:
            # Get existing localized field or create new one
            existing_field = existing_template.get(field, {})
            if not isinstance(existing_field, dict):
                existing_field = {}
            
            if template_type == "user":
                # For user templates, just update with any locale (use 'en' as default)
                # But when processing for response, we'll take the first available
                existing_field["en"] = template_data[field]
            else:
                # For official/organization templates, use the specified locale
                existing_field[locale] = template_data[field]
            
            update_data[field] = existing_field
    
    response = supabase.table("prompt_templates").update(update_data).eq("id", template_id).execute()
    
    if response.data:
        return process_template_for_response(response.data[0], locale)
    
    return {}

async def track_template_usage(supabase: Client, template_id: str) -> Dict:
    """
    Track template usage by incrementing usage count.
    
    Args:
        supabase: Supabase client
        template_id: Template ID
        
    Returns:
        Success response with updated usage count
    """
    # Get current template
    template = supabase.table("prompt_templates").select("*").eq("id", template_id).single().execute()
    
    if not template.data:
        raise ValueError("Template not found")
    
    # Increment usage count
    current_count = template.data.get('usage_count', 0) or 0
    new_count = current_count + 1
    
    # Update template
    response = supabase.table("prompt_templates").update({
        "usage_count": new_count,
        "last_used_at": "now()"
    }).eq("id", template_id).execute()
    
    return {"success": True, "usage_count": new_count}

def organize_templates_by_folder(templates: List[Dict]) -> Dict[int, List[Dict]]:
    """
    Group templates by their folder_id.
    
    Args:
        templates: List of template dicts
        
    Returns:
        Dict mapping folder_id to list of templates
    """
    templates_by_folder = {}
    for template in templates:
        folder_id = template.get("folder_id")
        if folder_id is not None:
            if folder_id not in templates_by_folder:
                templates_by_folder[folder_id] = []
            templates_by_folder[folder_id].append(template)
    return templates_by_folder

def add_templates_to_folders(folders: List[Dict], templates_by_folder: Dict[int, List[Dict]]) -> List[Dict]:
    """
    Add templates to their respective folders.
    
    Args:
        folders: List of folder dicts
        templates_by_folder: Dict mapping folder_id to templates
        
    Returns:
        Folders with templates added
    """
    folders_with_templates = []
    for folder in folders:
        folder_with_templates = folder.copy()
        folder_with_templates["templates"] = templates_by_folder.get(folder["id"], [])
        folders_with_templates.append(folder_with_templates)
    return folders_with_templates