from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
import dotenv
import os
from typing import List, Optional

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter(prefix="/templates", tags=["Templates"])

class TemplateBase(BaseModel):
    content: str
    name: str
    description: Optional[str] = None
    folder: Optional[str] = None

class TemplateCreate(TemplateBase):
    based_on_official_id: Optional[int] = None

class TemplateUpdate(TemplateBase):
    pass

@router.get("/")
async def get_templates(
    type: Optional[str] = None,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """
    Get templates with optional filtering by type.
    
    Parameters:
    - type: Optional filter by template type ('user', 'official', or 'organization')
    """
    try:
        if type == "user":
            return await get_user_templates(user_id)
        elif type == "official":
            return await get_official_templates(user_id)
        elif type == "organization":
            return await get_organization_templates(user_id)
        else:
            # Get all templates
            return await get_all_templates(user_id)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving templates: {str(e)}")

async def get_user_templates(user_id: str):
    """Get user's personal templates."""
    # Get all folders attached to the user_id
    folder_response = supabase.table("user_folders").select("id, path").eq("user_id", user_id).execute()
    user_folders = folder_response.data if folder_response.data else []

    # Extract folder IDs
    folder_ids = [folder['id'] for folder in user_folders]

    # Get templates in those folders with type "user"
    template_response = supabase.table("prompt_templates").select("*").in_("folder_id", folder_ids).eq("type", "user").execute()
    templates = template_response.data if template_response.data else []

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

async def get_official_templates(user_id: Optional[str] = None):
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

    # Get templates in those folders with type "official"
    if pinned_folder_ids:
        template_response = supabase.table("prompt_templates").select("*").in_("folder_id", pinned_folder_ids).eq("type", "official").execute()
    else:
        template_response = supabase.table("prompt_templates").select("*").eq("type", "official").execute()

    templates = template_response.data if template_response.data else []

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

async def get_organization_templates(user_id: Optional[str] = None):
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

    templates = templates_response.data or []

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

async def get_all_templates(user_id: str):
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
        official_folders = official_folders_response.data or []
        
        # User folders for this user
        user_folders_response = supabase.table("user_folders").select("*").eq("user_id", user_id).execute()
        user_folders = user_folders_response.data or []
        
        # Organization folders if applicable
        org_folders = []
        if organization_id:
            org_folders_response = supabase.table("organization_folders").select("*").eq("organization_id", organization_id).execute()
            org_folders = org_folders_response.data or []
        
        # 2. Fetch templates for each folder
        # For official folders
        official_templates = []
        for folder in official_folders:
            folder['is_pinned'] = folder['id'] in pinned_folders
            templates_response = supabase.table("prompt_templates").select("*").eq("folder_id", folder['id']).execute()
            folder['templates'] = templates_response.data or []
            official_templates.extend(templates_response.data or [])
        
        # For user folders
        user_templates = []
        for folder in user_folders:
            templates_response = supabase.table("prompt_templates").select("*").eq("folder_id", folder['id']).execute()
            folder['templates'] = templates_response.data or []
            user_templates.extend(templates_response.data or [])
        
        # For organization folders
        org_templates = []
        for folder in org_folders:
            templates_response = supabase.table("prompt_templates").select("*").eq("folder_id", folder['id']).execute()
            folder['templates'] = templates_response.data or []
            org_templates.extend(templates_response.data or [])
        
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

@router.post("/")
async def create_template(
    template: TemplateCreate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Create a new template, optionally based on an official template."""
    try:
        # If based on an official template, retrieve it first
        content = template.content
        name = template.name
        description = template.description
        
        if template.based_on_official_id:
            official = supabase.table("official_prompt_templates").select("*").eq("id", template.based_on_official_id).single().execute()
            if official.data:
                # Use official template content if not provided by user
                if not content:
                    content = official.data.get('content')
                # Use official template name if not provided by user
                if not name:
                    name = f"Copy of {official.data.get('name')}"
                # Use official template description if not provided by user
                if not description:
                    description = official.data.get('description')
        
        # Insert new template
        response = supabase.table("prompt_templates").insert({
            "user_id": user_id,
            "name": name,
            "content": content,
            "description": description,
            "folder": template.folder,
            "based_on_official_id": template.based_on_official_id,
            "usage_count": 0
        }).execute()
        
        return {
            "success": True,
            "template": response.data[0] if response.data else None
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
        # Verify template belongs to user
        verify = supabase.table("prompt_templates").select("id").eq("id", template_id).eq("user_id", user_id).execute()
        
        if not verify.data:
            raise HTTPException(status_code=404, detail="Template not found or doesn't belong to user")
        
        # Update fields
        update_data = {}
        if template.name is not None:
            update_data["name"] = template.name
        if template.content is not None:
            update_data["content"] = template.content
        if template.description is not None:
            update_data["description"] = template.description
        if template.folder is not None:
            update_data["folder"] = template.folder
        
        response = supabase.table("prompt_templates").update(update_data).eq("id", template_id).execute()
        
        return {
            "success": True,
            "template": response.data[0] if response.data else None
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