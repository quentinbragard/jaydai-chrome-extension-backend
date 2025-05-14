from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
from utils.prompts import (
    fetch_templates_by_type,
    get_unorganized_templates,
    create_template as create_template_util,
    update_template as update_template_util,
    track_template_usage as track_template_usage_util,
    fetch_folders_by_type,
    get_user_pinned_folders,
    add_pinned_status_to_folders,
    process_template_for_response
)
import dotenv
import os
from typing import List, Optional

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
    locale: Optional[str] = None
    folder_id: Optional[int] = None

class TemplateCreate(TemplateBase):
    pass

class TemplateUpdate(TemplateBase):
    pass

@router.get("")
async def get_templates(
    type: Optional[str] = None,
    locale: Optional[str] = "en",
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get templates with optional filtering by type."""
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
async def get_unorganized_templates_endpoint(
    locale: Optional[str] = "en",
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get all templates that are not organized in any folder."""
    try:
        templates = await get_unorganized_templates(supabase, user_id, locale)
        
        return {
            "success": True,
            "templates": templates
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving unorganized templates: {str(e)}")

async def get_user_templates(user_id: str, locale: str = "en"):
    """Get user's personal templates."""
    # Get user folders
    user_folders = await fetch_folders_by_type(supabase, "user", user_id=user_id, locale=locale)
    
    # Get user templates
    templates = await fetch_templates_by_type(supabase, "user", user_id=user_id, locale=locale)
    
    # Organize templates by folders
    folders = {folder['path']: [] for folder in user_folders if 'path' in folder}
    folders['root'] = []  # For templates without a folder

    for template in templates:
        folder_id = template.get('folder_id')
        folder_path = 'root'
        
        # Find folder path for this template
        for folder in user_folders:
            if folder['id'] == folder_id:
                folder_path = folder.get('path', 'root')
                break
        
        folders[folder_path].append(template)

    # Extract unique folder paths
    unique_folders = []
    for folder in user_folders:
        if 'path' in folder:
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
    """Get official prompt templates."""
    pinned_folder_ids = []

    if user_id:
        # Get user metadata to retrieve pinned official folder IDs
        user_metadata = supabase.table("users_metadata").select("pinned_official_folder_ids").eq("user_id", user_id).single().execute()
        pinned_folder_ids = user_metadata.data.get('pinned_official_folder_ids', []) if user_metadata.data else []

    # Get official folders
    if pinned_folder_ids:
        official_folders = await fetch_folders_by_type(
            supabase, 
            "official", 
            folder_ids=pinned_folder_ids, 
            locale=locale
        )
    else:
        official_folders = await fetch_folders_by_type(supabase, "official", locale=locale)

    # Get official templates
    templates = await fetch_templates_by_type(supabase, "official", locale=locale)
    
    # Filter templates by pinned folders if user has them
    if pinned_folder_ids:
        templates = [t for t in templates if t.get('folder_id') in pinned_folder_ids]

    # Extract all unique folders from the official folders
    folders = set()
    for folder in official_folders:
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

    # Get organization templates
    templates = await fetch_templates_by_type(
        supabase, 
        "organization", 
        organization_id=organization_id, 
        locale=locale
    )
    
    # Filter by pinned folders if specified
    if folder_ids:
        templates = [t for t in templates if t.get('folder_id') in folder_ids]

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
        
        # 1. Get folders
        official_folders = await fetch_folders_by_type(supabase, "official", locale=locale)
        user_folders = await fetch_folders_by_type(supabase, "user", user_id=user_id, locale=locale)
        org_folders = await fetch_folders_by_type(supabase, "organization", user_id=user_id, locale=locale)
        
        # Add pinned status to official folders
        add_pinned_status_to_folders(official_folders, pinned_folders)
        
        # 2. Fetch templates for each folder using the utility
        # For official folders
        official_templates = []
        for folder in official_folders:
            templates_response = supabase.table("prompt_templates").select("*").eq("folder_id", folder['id']).eq("type", "official").execute()
            raw_templates = templates_response.data or []
            folder['templates'] = [process_template_for_response(t, locale) for t in raw_templates]
            official_templates.extend(folder['templates'])
        
        # For user folders
        user_templates = []
        for folder in user_folders:
            templates_response = supabase.table("prompt_templates").select("*").eq("folder_id", folder['id']).eq("type", "user").execute()
            raw_templates = templates_response.data or []
            folder['templates'] = [process_template_for_response(t, locale) for t in raw_templates]
            user_templates.extend(folder['templates'])
        
        # For organization folders
        org_templates = []
        for folder in org_folders:
            templates_response = supabase.table("prompt_templates").select("*").eq("folder_id", folder['id']).eq("type", "organization").execute()
            raw_templates = templates_response.data or []
            folder['templates'] = [process_template_for_response(t, locale) for t in raw_templates]
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
    """Create a new template."""
    try:
        # Use the utility function for creating templates
        created_template = await create_template_util(
            supabase,
            template.dict(),
            user_id,
            template.locale or "en"
        )
        
        return {
            "success": True,
            "template": created_template
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating template: {str(e)}")

@router.put("/{template_id}")
async def update_template(
    template_id: str,
    template: TemplateUpdate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Update an existing template."""
    try:
        # Use the utility function for updating templates
        updated_template = await update_template_util(
            supabase,
            template_id,
            template.dict(),
            user_id,
            template.locale or "en"
        )
        
        return {
            "success": True,
            "template": updated_template
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
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
        # Use the utility function for tracking usage
        result = await track_template_usage_util(supabase, template_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error tracking template usage: {str(e)}")