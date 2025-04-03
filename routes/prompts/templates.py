from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
import dotenv
import os
from typing import List, Optional, Dict, Any

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter(tags=["Templates"])

class TemplateBase(BaseModel):
    content: str
    title: str
    type: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    locale: Optional[str] = None  # Still accept locale for backward compatibility
    folder_id: Optional[int] = None

class TemplateCreate(TemplateBase):
    pass

class TemplateUpdate(TemplateBase):
    pass

def process_templates_for_locale(templates: List[Dict], locale: str = "en") -> List[Dict]:
    """
    Process templates to use the appropriate content fields based on type and locale.
    - User templates: Use title_custom and content_custom
    - Official/Organization templates: Use locale-specific content (en/fr)
    """
    processed_templates = []
    for template in templates:
        processed_template = template.copy()
        template_type = template.get("type", "")
        
        if template_type == "user":
            # For user templates, use the custom fields
            if "title_custom" in template:
                processed_template["title"] = template["title_custom"]
            
            if "content_custom" in template:
                processed_template["content"] = template["content_custom"]
        else:
            # For official/organization templates, use locale-specific fields
            # Handle content fields - select based on locale with fallback to English
            content_field = f"content_{locale}" if locale in ["en", "fr"] else "content_en"
            fallback_field = "content_en"
            
            if content_field in template and template[content_field]:
                processed_template["content"] = template[content_field]
            elif fallback_field in template and template[fallback_field]:
                processed_template["content"] = template[fallback_field]
            else:
                processed_template["content"] = ""
            
            # Handle title fields
            title_field = f"title_{locale}" if locale in ["en", "fr"] else "title_en"
            fallback_title_field = "title_en"
            
            if title_field in template and template[title_field]:
                processed_template["title"] = template[title_field]
            elif fallback_title_field in template and template[fallback_title_field]:
                processed_template["title"] = template[fallback_title_field]
        
        # Remove all specialized fields for backward compatibility
        processed_template.pop("content_en", None)
        processed_template.pop("content_fr", None)
        processed_template.pop("content_custom", None)
        processed_template.pop("title_en", None)
        processed_template.pop("title_fr", None)
        processed_template.pop("title_custom", None)
        
        processed_templates.append(processed_template)
    
    return processed_templates

@router.get("")
async def get_templates(
    type: Optional[str] = None,
    locale: Optional[str] = "en",  # Default to English
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """
    Get templates with optional filtering by type.
    
    Parameters:
    - type: Optional filter by template type ('user', 'official', or 'organization')
    - locale: Optional locale code for content ('en', 'fr')
    """
    try:
        if type == "user":
            return await get_user_templates(user_id, locale)
        elif type == "official":
            return await get_official_templates(user_id, locale)
        elif type == "organization":
            return await get_organization_templates(user_id, locale)
        else:
            # Get all templates
            return await get_all_templates(user_id, locale)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving templates: {str(e)}")
    
@router.get("/unorganized")
async def get_unorganized_templates(
    locale: Optional[str] = "en",  # Default to English
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get all templates that are not organized in any folder."""
    # Use is.null() instead of eq(None) for checking NULL values
    unorganized_user_templates = (
        supabase.table("prompt_templates")
        .select("*")
        .eq("type", "user")
        .eq("user_id", user_id)  # Ensure we only get templates for this user
        .is_("folder_id", "null")  # Use is_ with "null" string for NULL check
        .execute()
    )
    
    # Process templates for locale
    templates = process_templates_for_locale(unorganized_user_templates.data, locale)
    
    return {
        "success": True,
        "templates": templates
    }

async def get_user_templates(user_id: str, locale: str = "en"):
    """Get user's personal templates."""
    # Get all folders attached to the user_id
    folder_response = supabase.table("user_folders").select("id, path").eq("user_id", user_id).execute()
    user_folders = folder_response.data if folder_response.data else []

    # Extract folder IDs
    folder_ids = [folder['id'] for folder in user_folders]

    # Get templates in those folders with type "user"
    template_response = supabase.table("prompt_templates").select("*").in_("folder_id", folder_ids).eq("type", "user").execute()
    raw_templates = template_response.data if template_response.data else []
    
    # Process templates - for user templates, use the custom fields
    templates = process_templates_for_locale(raw_templates, locale)

    # Organize templates by folders
    folders = {folder['path']: [] for folder in user_folders}
    folders['root'] = []  # For templates without a folder

    for template in templates:
        folder_id = template.get('folder_id')
        folder_path = next((folder['path'] for folder in user_folders if folder['id'] == folder_id), 'root')
        folders[folder_path].append(template)

    # Get unique folder paths
    unique_folders = []
    for folder in user_folders:
        path = folder['path']
        parts = path.split('/')
        current_path = ""
        
        for i, part in enumerate(parts):
            if i > 0:
                current_path += "/"
            current_path += part
            
            # Add folder if not already in list
            if not any(f['path'] == current_path for f in unique_folders):
                unique_folders.append({
                    'path': current_path,
                    'name': part,
                    'level': i
                })

    return {
        "success": True,
        "templates": templates,
        "folders": unique_folders,
        "templates_by_folder": folders
    }

async def get_official_templates(user_id: Optional[str] = None, locale: str = "en"):
    """Get official prompt templates that can be used as a basis."""
    pinned_folder_ids = []
    print("user_id==========================================", user_id)

    if user_id:
        # Get user metadata to retrieve pinned official folder IDs
        user_metadata = supabase.table("users_metadata").select("pinned_official_folder_ids").eq("user_id", user_id).single().execute()
        pinned_folder_ids = user_metadata.data.get('pinned_official_folder_ids', []) if user_metadata.data else []

    # Get official folders matching the pinned folder IDs if user_id is provided, otherwise get all
    if pinned_folder_ids:
        official_folders_response = supabase.table("official_folders").select("*").in_("id", pinned_folder_ids).execute()
    else:
        official_folders_response = supabase.table("official_folders").select("*").execute()

    official_folders = official_folders_response.data if official_folders_response.data else []
    
    # Process folder names for locale
    processed_folders = []
    for folder in official_folders:
        processed_folder = folder.copy()
        name_field = f"name_{locale}" if locale in ["en", "fr"] else "name_en"
        fallback_field = "name_en"
        
        if name_field in folder and folder[name_field]:
            processed_folder["name"] = folder[name_field]
        elif fallback_field in folder and folder[fallback_field]:
            processed_folder["name"] = folder[fallback_field]
        else:
            processed_folder["name"] = "Unnamed Folder"
            
        # Remove locale-specific fields
        processed_folder.pop("name_en", None)
        processed_folder.pop("name_fr", None)
        
        processed_folders.append(processed_folder)

    # Get templates in those folders with type "official"
    if pinned_folder_ids:
        template_response = supabase.table("prompt_templates").select("*").in_("folder_id", pinned_folder_ids).eq("type", "official").execute()
    else:
        template_response = supabase.table("prompt_templates").select("*").eq("type", "official").execute()

    raw_templates = template_response.data if template_response.data else []
    
    # Process templates for locale - official templates use locale-specific fields
    templates = process_templates_for_locale(raw_templates, locale)

    # Extract all unique folders from the official folders
    folders = set()
    for folder in processed_folders:
        folder_path = folder.get('path')
        if folder_path:
            parts = folder_path.split('/')
            current_path = ""
            for i, part in enumerate(parts):
                if i > 0:
                    current_path += "/"
                current_path += part
                folders.add(current_path)

    # Convert to a sorted list
    folders_list = sorted(list(folders))

    return {
        "success": True,
        "templates": templates,
        "folders": folders_list
    }

async def get_organization_templates(user_id: Optional[str] = None, locale: str = "en"):
    """Get organization templates for the user's organization."""
    organization_id = None
    folder_ids = []

    if user_id:
        # Get user metadata to check for organization_id and pinned organization folder IDs
        user_metadata = supabase.table("users_metadata").select("*").eq("user_id", user_id).single().execute()
        
        if user_metadata.data:
            organization_id = user_metadata.data.get('organization_id')
            pinned_folder_ids = user_metadata.data.get('pinned_organization_folder_ids', [])
            folder_ids = pinned_folder_ids if pinned_folder_ids else []

    if organization_id and not folder_ids:
        # Get organization folder ids if not using pinned folder IDs
        folder_ids_response = supabase.table("organization_folders").select("id").eq("organization_id", organization_id).execute()
        folder_ids = [folder['id'] for folder in folder_ids_response.data] if folder_ids_response.data else []

    # Get organization templates
    if folder_ids:
        templates_response = supabase.table("prompt_templates").select("*").in_("folder_id", folder_ids).eq("type", "organization").execute()
    else:
        templates_response = supabase.table("prompt_templates").select("*").eq("type", "organization").execute()

    raw_templates = templates_response.data or []
    
    # Process templates for locale - organization templates use locale-specific fields
    templates = process_templates_for_locale(raw_templates, locale)

    # Extract all unique folders from the templates
    folders = set()
    for template in templates:
        folder_path = template.get('folder')
        if folder_path:
            parts = folder_path.split('/')
            current_path = ""
            for i, part in enumerate(parts):
                if i > 0:
                    current_path += "/"
                current_path += part
                folders.add(current_path)

    # Convert to a sorted list
    folders_list = sorted(list(folders))

    return {
        "success": True,
        "templates": templates,
        "folders": folders_list
    }

async def get_all_templates(user_id: str, locale: str = "en"):
    """Get templates organized by type (official, organization, and user)."""
    try:
        # Get user metadata to check for organization_id and pinned folders
        user_metadata = supabase.table("users_metadata").select("*").eq("user_id", user_id).single().execute()
        
        organization_id = None
        if user_metadata.data and 'organization_id' in user_metadata.data:
            organization_id = user_metadata.data['organization_id']
        
        # Get pinned folders
        pinned_folders = []
        if user_metadata.data and 'pinned_official_folder_ids' in user_metadata.data:
            pinned_folders = user_metadata.data['pinned_official_folder_ids'] or []
        
        # 1. Fetch all folders
        # Official folders
        official_folders_response = supabase.table("official_folders").select("*").execute()
        raw_official_folders = official_folders_response.data or []
        
        # Process official folder names
        official_folders = []
        for folder in raw_official_folders:
            processed_folder = folder.copy()
            name_field = f"name_{locale}" if locale in ["en", "fr"] else "name_en"
            fallback_field = "name_en"
            
            if name_field in folder and folder[name_field]:
                processed_folder["name"] = folder[name_field]
            elif fallback_field in folder and folder[fallback_field]:
                processed_folder["name"] = folder[fallback_field]
            else:
                processed_folder["name"] = "Unnamed Folder"
                
            # Remove locale-specific fields
            processed_folder.pop("name_en", None)
            processed_folder.pop("name_fr", None)
            
            official_folders.append(processed_folder)
        
        # User folders for this user
        user_folders_response = supabase.table("user_folders").select("*").eq("user_id", user_id).execute()
        user_folders = user_folders_response.data or []
        
        # Organization folders if applicable
        org_folders = []
        if organization_id:
            org_folders_response = supabase.table("organization_folders").select("*").eq("organization_id", organization_id).execute()
            raw_org_folders = org_folders_response.data or []
            
            # Process organization folder names
            for folder in raw_org_folders:
                processed_folder = folder.copy()
                name_field = f"name_{locale}" if locale in ["en", "fr"] else "name_en"
                fallback_field = "name_en"
                
                if name_field in folder and folder[name_field]:
                    processed_folder["name"] = folder[name_field]
                elif fallback_field in folder and folder[fallback_field]:
                    processed_folder["name"] = folder[fallback_field]
                else:
                    processed_folder["name"] = "Unnamed Folder"
                    
                # Remove locale-specific fields
                processed_folder.pop("name_en", None)
                processed_folder.pop("name_fr", None)
                
                org_folders.append(processed_folder)
        
        # 2. Fetch templates for each folder
        # For official folders
        official_templates = []
        for folder in official_folders:
            folder['is_pinned'] = folder['id'] in pinned_folders
            templates_response = supabase.table("prompt_templates").select("*").eq("folder_id", folder['id']).execute()
            raw_templates = templates_response.data or []
            # Process templates with locale - official templates use locale-specific fields
            folder['templates'] = process_templates_for_locale(raw_templates, locale)
            official_templates.extend(folder['templates'])
        
        # For user folders
        user_templates = []
        for folder in user_folders:
            templates_response = supabase.table("prompt_templates").select("*").eq("folder_id", folder['id']).execute()
            raw_templates = templates_response.data or []
            # Process templates - user templates use custom fields
            folder['templates'] = process_templates_for_locale(raw_templates, locale)
            user_templates.extend(folder['templates'])
        
        # For organization folders
        org_templates = []
        for folder in org_folders:
            templates_response = supabase.table("prompt_templates").select("*").eq("folder_id", folder['id']).execute()
            raw_templates = templates_response.data or []
            # Process templates with locale - organization templates use locale-specific fields
            folder['templates'] = process_templates_for_locale(raw_templates, locale)
            org_templates.extend(folder['templates'])
        
        return {
            "success": True,
            "pinnedFolders": {
                "userTemplates": {
                    "templates": user_templates,
                    "folders": user_folders
                },
                "officialTemplates": {
                    "templates": official_templates,
                    "folders": official_folders
                },
                "organizationTemplates": {
                    "templates": org_templates,
                    "folders": org_folders
                }
            }
        }
    except Exception as e:
        print(f"Error retrieving templates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving templates: {str(e)}")
    
    
@router.post("")
async def create_template(
    template: TemplateCreate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Create a new template, with support for custom and localized content."""
    try:
        # Determine locale for non-user templates
        locale = template.locale or "en"
        
        # Prepare template data
        template_data = {
            "type": template.type,
            "user_id": user_id,
            "folder_id": template.folder_id,
            "tags": template.tags
        }
        
        # Set content and title fields based on template type
        if template.type == "user":
            # User templates use custom fields
            template_data["title_custom"] = template.title
            template_data["content_custom"] = template.content
            # Initialize locale fields with empty strings for consistency
            template_data["title_en"] = ""
            template_data["title_fr"] = ""
            template_data["content_en"] = ""
            template_data["content_fr"] = ""
        else:
            # Non-user templates use locale-specific fields
            if locale == "fr":
                template_data["title_fr"] = template.title
                template_data["content_fr"] = template.content
                template_data["title_en"] = ""  # Empty default
                template_data["content_en"] = ""
            else:
                template_data["title_en"] = template.title
                template_data["content_en"] = template.content
                template_data["title_fr"] = ""  # Empty default
                template_data["content_fr"] = ""
            
            # Initialize custom fields with empty strings
            template_data["title_custom"] = ""
            template_data["content_custom"] = ""
        
        # Insert new template
        response = supabase.table("prompt_templates").insert(template_data).execute()
        
        # Process the returned template for the response
        processed_template = None
        if response.data:
            processed_template = process_templates_for_locale([response.data[0]], locale)[0]
        
        return {
            "success": True,
            "template": processed_template
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating template: {str(e)}")

@router.put("/{template_id}")
async def update_template(
    template_id: str,
    template: TemplateUpdate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    print("template==========================================", template)
    """Update an existing template with custom/locale-specific content handling."""
    try:
        # Verify template belongs to user
        verify = supabase.table("prompt_templates").select("id, type").eq("id", template_id).eq("user_id", user_id).execute()
        
        if not verify.data:
            raise HTTPException(status_code=404, detail="Template not found or doesn't belong to user")
        
        # Get the template type to determine which fields to update
        template_type = verify.data[0].get("type") if verify.data else "user"
        
        # Determine locale for non-user templates
        locale = template.locale or "en"
        
        # Prepare update data based on template type
        update_data = {}
        
        if template.tags is not None:
            update_data["tags"] = template.tags
            
        if template.folder_id is not None:
            update_data["folder_id"] = template.folder_id
        
        # Set title and content fields based on template type
        if template_type == "user":
            # User templates use custom fields
            if template.title is not None:
                update_data["title_custom"] = template.title
            
            if template.content is not None:
                update_data["content_custom"] = template.content
        else:
            # Non-user templates use locale-specific fields
            if template.title is not None:
                title_field = f"title_{locale}"
                update_data[title_field] = template.title
            
            if template.content is not None:
                content_field = f"content_{locale}"
                update_data[content_field] = template.content
        
        # Update the template
        response = supabase.table("prompt_templates").update(update_data).eq("id", template_id).execute()
        
        # Process the template for response
        processed_template = None
        if response.data:
            processed_template = process_templates_for_locale([response.data[0]], locale)[0]
        
        return {
            "success": True,
            "template": processed_template
        }
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
        # Verify template belongs to user
        verify = supabase.table("prompt_templates").select("id").eq("id", template_id).eq("user_id", user_id).execute()
        
        if not verify.data:
            raise HTTPException(status_code=404, detail="Template not found or doesn't belong to user")
        
        # Delete template
        supabase.table("prompt_templates").delete().eq("id", template_id).execute()
        
        return {
            "success": True,
            "message": "Template deleted"
        }
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
        # Verify template exists
        template = supabase.table("prompt_templates").select("*").eq("id", template_id).single().execute()
        
        if not template.data:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Increment usage count
        current_count = template.data.get('usage_count', 0) or 0
        new_count = current_count + 1
        
        # Update template
        response = supabase.table("prompt_templates").update({
            "usage_count": new_count,
            "last_used_at": "now()"  # Use SQL function for current timestamp
        }).eq("id", template_id).execute()
        
        return {
            "success": True,
            "usage_count": new_count
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error tracking template usage: {str(e)}")