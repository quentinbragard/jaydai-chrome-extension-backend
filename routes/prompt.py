from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
import dotenv
import os
from typing import List, Optional
from enum import Enum

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter(prefix="/prompt", tags=["Prompt"])

class Locale(str, Enum):
    fr = "fr"
    en = "en"
    
class PromptType(str, Enum):
    official = "official"
    user = "user"
    organization = "organization"


class PromptTemplateBase(BaseModel):
    id: int
    created_at: str
    type: PromptType
    folder_id: int
    tags: List[str]
    title: str
    content: str
    locale: Locale

class PromptTemplateCreate(PromptTemplateBase):
    pass

class PromptTemplateUpdate(PromptTemplateBase):
    pass


class PromptTemplatesFolder(BaseModel):
    id: int
    created_at: str
    type: str
    tags: List[str]
    path: str
    prompt_templates: Optional[List[PromptTemplateBase]] = None
    

@router.get("/template-folders")
async def get_template_folders(
    type: PromptType,
    folder_ids: Optional[str] = None,  # Accept a comma-separated string
    empty: bool = False,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get template folders by type with proper error handling"""
    try:
        # Parse folder_ids from comma-separated string to list of integers
        folder_id_list = []
        if folder_ids:
            try:
                folder_id_list = [int(id_str) for id_str in folder_ids.split(',') if id_str.strip()]
                print(f"Parsed folder IDs: {folder_id_list} from {folder_ids}")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid folder ID format: {str(e)}")
        
        print(f"Get template folders request: type={type}, folder_ids={folder_id_list}, empty={empty}")
        
        if type == PromptType.official:
            # When no folder_ids are provided, return all folders for browsing
            if not folder_id_list:
                return await get_all_official_template_folders(empty)
            else:
                return await get_official_template_folders(folder_id_list, empty)
        elif type == PromptType.organization:
            # When no folder_ids are provided, return all folders for browsing
            if not folder_id_list:
                return await get_all_organization_template_folders(empty)
            else:
                return await get_organization_template_folders(folder_id_list, empty)
        elif type == PromptType.user:
            return await get_user_template_folders(user_id, empty)
        else:
            raise HTTPException(status_code=400, detail="Invalid prompt type")
    except Exception as e:
        print(f"Error retrieving template folders: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving template folders: {str(e)}")


@router.get("/official-template-folders")
async def get_official_template_folders(
    folder_ids: List[int],
    empty: bool = False
):
    """Get specific official template folders by IDs"""
    try:
        # Handle case when folder_ids is empty
        if not folder_ids:
            return {"success": True, "folders": []}
            
        print(f"Getting official folders with IDs: {folder_ids}")
            
        # Get all folders in one query
        folders_response = supabase.table("official_folders").select("*").in_("id", folder_ids).execute()
        folders = folders_response.data
        
        # If no folders found, return empty list
        if not folders:
            return {"success": True, "folders": []}
        
        # If not empty, get all templates in one query
        templates = []
        if not empty:
            templates_response = supabase.table("prompt_templates") \
                .select("*") \
                .eq("type", "official") \
                .in_("folder_id", folder_ids) \
                .execute()
            templates = templates_response.data
        
        # Create a map of folder_id to templates
        templates_by_folder = {}
        for template in templates:
            folder_id = template["folder_id"]
            if folder_id not in templates_by_folder:
                templates_by_folder[folder_id] = []
            templates_by_folder[folder_id].append(template)
        
        # Create folder objects with their templates
        folders_with_templates = []
        for folder in folders:
            folder_with_templates = folder.copy()
            folder_with_templates["templates"] = templates_by_folder.get(folder["id"], [])
            folders_with_templates.append(folder_with_templates)
        return {"success": True, "folders": folders_with_templates}
    except Exception as e:
        print(f"Error retrieving official template folders: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving official template folders: {str(e)}")

@router.get("/organization-template-folders")
async def get_organization_template_folders(
    folder_ids: List[int],
    empty: bool = False
):
    """Get specific organization template folders by IDs"""
    try:
        # Handle case when folder_ids is empty
        if not folder_ids:
            return {"success": True, "folders": []}
            
        # Get all folders in one query
        folders_response = supabase.table("organization_folders").select("*").in_("id", folder_ids).execute()
        folders = folders_response.data
        
        # If no folders found, return empty list
        if not folders:
            return {"success": True, "folders": []}
        
        # If not empty, get all templates in one query
        templates = []
        if not empty:
            templates_response = supabase.table("prompt_templates") \
                .select("*") \
                .eq("type", "organization") \
                .in_("folder_id", folder_ids) \
                .execute()
            templates = templates_response.data
        
        # Create a map of folder_id to templates
        templates_by_folder = {}
        for template in templates:
            folder_id = template["folder_id"]
            if folder_id not in templates_by_folder:
                templates_by_folder[folder_id] = []
            templates_by_folder[folder_id].append(template)
        
        # Create folder objects with their templates
        folders_with_templates = []
        for folder in folders:
            folder_with_templates = folder.copy()
            folder_with_templates["templates"] = templates_by_folder.get(folder["id"], [])
            folders_with_templates.append(folder_with_templates)
        return {"success": True, "folders": folders_with_templates}
    except Exception as e:
        print(f"Error retrieving organization template folders: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving organization template folders: {str(e)}")

@router.get("/user-template-folders")
async def get_user_template_folders(
    user_id: str,
    empty: bool = False
):
    """Get all template folders for a specific user"""
    try:
        # Get all folders in one query
        folders_response = supabase.table("user_folders").select("*").eq("user_id", user_id).execute()
        folders = folders_response.data
        
        # If no folders found, return empty list
        if not folders:
            return {"success": True, "folders": []}
            
        folder_ids = [folder["id"] for folder in folders]
        
        # If not empty, get all templates in one query
        templates = []
        if not empty and folder_ids:
            templates_response = supabase.table("prompt_templates") \
                .select("*") \
                .eq("type", "user") \
                .in_("folder_id", folder_ids) \
                .execute()
            templates = templates_response.data
        
        # Create a map of folder_id to templates
        templates_by_folder = {}
        for template in templates:
            folder_id = template["folder_id"]
            if folder_id not in templates_by_folder:
                templates_by_folder[folder_id] = []
            templates_by_folder[folder_id].append(template)
        
        # Create folder objects with their templates
        folders_with_templates = []
        for folder in folders:
            folder_with_templates = folder.copy()
            folder_with_templates["templates"] = templates_by_folder.get(folder["id"], [])
            folders_with_templates.append(folder_with_templates)
        return {"success": True, "folders": folders_with_templates}
    except Exception as e:
        print(f"Error retrieving user template folders: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving user template folders: {str(e)}")

# Helper functions for getting all folders (used when folder_ids is not provided)
async def get_all_official_template_folders(empty: bool = False):
    """Get all official template folders for browsing"""
    try:
        # Get all folders in one query
        folders_response = supabase.table("official_folders").select("*").execute()
        folders = folders_response.data
        
        # If no folders found, return empty list
        if not folders:
            return {"success": True, "folders": []}
            
        folder_ids = [folder["id"] for folder in folders]
        
        # If not empty, get all templates in one query
        templates = []
        if not empty and folder_ids:
            templates_response = supabase.table("prompt_templates") \
                .select("*") \
                .eq("type", "official") \
                .in_("folder_id", folder_ids) \
                .execute()
            templates = templates_response.data
        
        # Create a map of folder_id to templates
        templates_by_folder = {}
        for template in templates:
            folder_id = template["folder_id"]
            if folder_id not in templates_by_folder:
                templates_by_folder[folder_id] = []
            templates_by_folder[folder_id].append(template)
        
        # Create folder objects with their templates
        folders_with_templates = []
        for folder in folders:
            folder_with_templates = folder.copy()
            folder_with_templates["templates"] = templates_by_folder.get(folder["id"], [])
            folders_with_templates.append(folder_with_templates)
        return {"success": True, "folders": folders_with_templates}
    except Exception as e:
        print(f"Error retrieving all official folders: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving all official folders: {str(e)}")

async def get_all_organization_template_folders(empty: bool = False):
    """Get all organization template folders for browsing"""
    try:
        # Get all folders in one query
        # Note: You may need to filter by organization based on the user
        folders_response = supabase.table("organization_folders").select("*").execute()
        folders = folders_response.data
        
        # If no folders found, return empty list
        if not folders:
            return {"success": True, "folders": []}
            
        folder_ids = [folder["id"] for folder in folders]
        
        # If not empty, get all templates in one query
        templates = []
        if not empty and folder_ids:
            templates_response = supabase.table("prompt_templates") \
                .select("*") \
                .eq("type", "organization") \
                .in_("folder_id", folder_ids) \
                .execute()
            templates = templates_response.data
        
        # Create a map of folder_id to templates
        templates_by_folder = {}
        for template in templates:
            folder_id = template["folder_id"]
            if folder_id not in templates_by_folder:
                templates_by_folder[folder_id] = []
            templates_by_folder[folder_id].append(template)
        
        # Create folder objects with their templates
        folders_with_templates = []
        for folder in folders:
            folder_with_templates = folder.copy()
            folder_with_templates["templates"] = templates_by_folder.get(folder["id"], [])
            folders_with_templates.append(folder_with_templates)
        return {"success": True, "folders": folders_with_templates}
    except Exception as e:
        print(f"Error retrieving all organization folders: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving all organization folders: {str(e)}")

@router.post("/template")
async def create_template(
    template_data: PromptTemplateCreate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Create a new template"""
    try:
        # Add user_id to the template data
        template_insert_data = template_data.dict()
        template_insert_data["user_id"] = user_id
        
        # Insert into database
        response = supabase.table("prompt_templates").insert(template_insert_data).execute()
        
        return {"success": True, "template": response.data[0] if response.data else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating template: {str(e)}")

@router.put("/template/{template_id}")
async def update_template(
    template_id: int,
    template_data: PromptTemplateUpdate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Update an existing template"""
    try:
        # Check if template exists and belongs to the user
        template_check = supabase.table("prompt_templates").select("*") \
            .eq("id", template_id) \
            .eq("user_id", user_id) \
            .execute()
            
        if not template_check.data:
            raise HTTPException(status_code=404, detail="Template not found or not owned by user")
        
        # Update the template
        update_data = template_data.dict(exclude={"id", "user_id", "created_at"})
        response = supabase.table("prompt_templates").update(update_data) \
            .eq("id", template_id) \
            .execute()
        
        return {"success": True, "template": response.data[0] if response.data else None}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating template: {str(e)}")

@router.delete("/template/{template_id}")
async def delete_template(
    template_id: int,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Delete a template"""
    try:
        # Check if template exists and belongs to the user
        template_check = supabase.table("prompt_templates").select("*") \
            .eq("id", template_id) \
            .eq("user_id", user_id) \
            .execute()
            
        if not template_check.data:
            raise HTTPException(status_code=404, detail="Template not found or not owned by user")
        
        # Delete the template
        response = supabase.table("prompt_templates").delete() \
            .eq("id", template_id) \
            .execute()
        
        return {"success": True, "message": "Template deleted successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting template: {str(e)}")