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
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_API_KEY"))
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
        response = supabase.table("user_prompt_templates").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        
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
        
        print({"templates": templates, "folders": unique_folders, "templates_by_folder": folders})
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
    print("####################")
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
        print(folders_list)
        
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
    """Get both user and official prompt templates."""
    try:
        # Fetch user's templates
        user_templates_response = supabase.table("user_prompt_templates") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .execute()
        
        # Fetch official templates
        official_templates_response = supabase.table("official_prompt_templates") \
            .select("*") \
            .execute()
            
        print({"user_templates_response": user_templates_response.data, "official_templates_response": official_templates_response.data})
        
        return {
            "success": True,
            "userTemplates": user_templates_response.data or [],
            "officialTemplates": official_templates_response.data or []
        }
    except Exception as e:
        print(f"Error retrieving templates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving templates: {str(e)}")

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
        response = supabase.table("user_prompt_templates").insert({
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
        verify = supabase.table("user_prompt_templates").select("id").eq("id", template_id).eq("user_id", user_id).execute()
        
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
        
        response = supabase.table("user_prompt_templates").update(update_data).eq("id", template_id).execute()
        
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
        verify = supabase.table("user_prompt_templates").select("id").eq("id", template_id).eq("user_id", user_id).execute()
        
        if not verify.data:
            raise HTTPException(status_code=404, detail="Template not found or doesn't belong to user")
        
        # Delete template
        supabase.table("user_prompt_templates").delete().eq("id", template_id).execute()
        
        return {
            "success": True,
            "message": "Template deleted"
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error deleting template: {str(e)}")