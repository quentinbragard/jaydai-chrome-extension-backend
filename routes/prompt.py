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
    folder_ids: str = None,  # Accept a comma-separated string instead of a list
    empty: bool = False,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get template folders by type with proper error handling"""
    try:
        if type == PromptType.official:
            return await get_official_template_folders(folder_ids, empty)
        elif type == PromptType.organization:
            return await get_organization_template_folders(folder_ids, empty)
        elif type == PromptType.user:
            return await get_user_template_folders(user_id, empty)
        else:
            raise HTTPException(status_code=400, detail="Invalid prompt type")
    except Exception as e:
        print(f"Error retrieving template folders: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving template folders: {str(e)}")


@router.get("/official-template-folders")
async def get_official_template_folders(
    folder_ids: str = None,
    empty: bool = False
):
    # Parse folder_ids from comma-separated string to list of integers
    folder_id_list = []
    if folder_ids:
        try:
            folder_id_list = [int(id_str) for id_str in folder_ids.split(',') if id_str.strip()]
            print(f"Parsed folder IDs: {folder_id_list} from {folder_ids}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid folder ID format: {str(e)}")

    try:
        # Handle case when folder_ids is None or empty
        if not folder_id_list or len(folder_id_list) == 0:
            return {"success": True, "folders": []}
            
        # Get all folders in one query
        folders_response = supabase.table("official_folders").select("*").in_("id", folder_id_list).execute()
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
                .in_("folder_id", folder_id_list) \
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
        raise HTTPException(status_code=500, detail=f"Error retrieving official template folders: {str(e)}")

@router.get("/organization-template-folders")
async def get_organization_template_folders(
    folder_ids: str = None,
    empty: bool = False
):
    try:
        # Parse folder_ids from comma-separated string to list of integers
        folder_id_list = []
        if folder_ids:
            try:
                folder_id_list = [int(id_str) for id_str in folder_ids.split(',') if id_str.strip()]
                print(f"Parsed folder IDs: {folder_id_list} from {folder_ids}")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid folder ID format: {str(e)}")
            
        # Handle case when folder_ids is None or empty
        if not folder_id_list or len(folder_id_list) == 0:
            return {"success": True, "folders": []}
            
        # Get all folders in one query
        folders_response = supabase.table("organization_folders").select("*").in_("id", folder_id_list).execute()
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
                .in_("folder_id", folder_id_list) \
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
        raise HTTPException(status_code=500, detail=f"Error retrieving organization template folders: {str(e)}")

@router.get("/user-template-folders")
async def get_user_template_folders(
    user_id: str,
    empty: bool = False
):
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
        raise HTTPException(status_code=500, detail=f"Error retrieving user template folders: {str(e)}")