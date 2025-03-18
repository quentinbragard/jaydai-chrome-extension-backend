from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
import dotenv
import os
import openai
from typing import List, Optional

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
openai.api_key = os.getenv("OPENAI_API_KEY")

router = APIRouter(prefix="/prompt-templates", tags=["Prompt Templates"])


class PromptTemplate(BaseModel):
    name: str
    content: str
    description: Optional[str] = None
    folder: Optional[str] = None
    based_on_official_id: Optional[int] = None
    usage_count: Optional[int] = 0

class TemplateFolder(BaseModel):
    path: str
    name: str
    
class TemplateCreate(BaseModel):
    content: str
    name: str
    folder: Optional[str] = None
    description: Optional[str] = None
    based_on_official_id: Optional[int] = None



@router.get("/user-templates")
async def get_user_templates(
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get user's prompt templates organized by folders."""
    try:
        response = supabase.table("prompt_templates").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        
        templates = response.data
        folders = {}
        
        # Process templates and organize by folders
        for template in templates:
            folder_path = template.get('folder')
            
            if not folder_path:
                # Root level template
                if 'root' not in folders:
                    folders['root'] = []
                folders['root'].append(template)
            else:
                # Template in a folder
                if folder_path not in folders:
                    folders[folder_path] = []
                folders[folder_path].append(template)
        
        # Get unique folder paths
        unique_folders = []
        for path in folders.keys():
            if path != 'root':
                # Split folder paths to get hierarchy
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving templates: {str(e)}")

@router.get("/official-templates")
async def get_official_templates(
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get official prompt templates that can be used as a basis."""
    try:
        response = supabase.table("official_prompt_templates").select("*").order("folder", desc=False).execute()
        
        # Process templates to include folder information
        templates = response.data
        
        # Extract all unique folders
        folders = set()
        for template in templates:
            folder_path = template.get('folder')
            if folder_path:
                # Split folder path to get hierarchy
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving official templates: {str(e)}")
    
@router.get("/all-templates")
async def get_all_templates(
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get templates organized by folders (official, organization, and user)."""
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
        
        print({
            "success": True,
            "userTemplates": user_templates,
            "officialTemplates": official_templates,
            "organizationTemplates": org_templates,
            "officialFolders": official_folders,
            "userFolders": user_folders,
            "organizationFolders": org_folders,
            "pinnedFolders": pinned_folders
        })
        
        return {
            "success": True,
            "userTemplates": user_templates,
            "officialTemplates": official_templates,
            "organizationTemplates": org_templates,
            "officialFolders": official_folders,
            "userFolders": user_folders,
            "organizationFolders": org_folders,
            "pinnedFolders": pinned_folders
        }
    except Exception as e:
        print(f"Error retrieving templates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving templates: {str(e)}")
    
    
@router.post("/pin-folder/{folder_id}")
async def pin_folder(
    folder_id: int,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Pin an official folder for a user."""
    try:
        # Get current user metadata
        user_metadata = supabase.table("users_metadata").select("*").eq("user_id", user_id).single().execute()
        
        if not user_metadata.data:
            # Create user metadata if it doesn't exist
            pinned_folders = [folder_id]
            supabase.table("users_metadata").insert({
                "user_id": user_id,
                "pinned_official_folder_ids": pinned_folders
            }).execute()
        else:
            # Update existing pinned folders
            pinned_folders = user_metadata.data.get('pinned_official_folder_ids') or []
            if folder_id not in pinned_folders:
                pinned_folders.append(folder_id)
                
            # Update metadata
            supabase.table("users_metadata").update({
                "pinned_official_folder_ids": pinned_folders
            }).eq("user_id", user_id).execute()
        
        return {
            "success": True,
            "pinned_folders": pinned_folders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error pinning folder: {str(e)}")

@router.post("/unpin-folder/{folder_id}")
async def unpin_folder(
    folder_id: int,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Unpin an official folder for a user."""
    try:
        # Get current user metadata
        user_metadata = supabase.table("users_metadata").select("*").eq("user_id", user_id).single().execute()
        
        if not user_metadata.data:
            return {
                "success": True,
                "pinned_folders": []
            }
        
        # Update existing pinned folders
        pinned_folders = user_metadata.data.get('pinned_official_folder_ids') or []
        if folder_id in pinned_folders:
            pinned_folders.remove(folder_id)
            
        # Update metadata
        supabase.table("users_metadata").update({
            "pinned_official_folder_ids": pinned_folders
        }).eq("user_id", user_id).execute()
        
        return {
            "success": True,
            "pinned_folders": pinned_folders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error unpinning folder: {str(e)}")
    
     
@router.post("/template")
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

@router.put("/template/{template_id}")
async def update_template(
    template_id: str,
    template: TemplateCreate,
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

@router.delete("/template/{template_id}")
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