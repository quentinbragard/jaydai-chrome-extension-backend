from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
from utils.prompts import (
    fetch_folders_by_type,
    fetch_templates_for_folders,
    organize_templates_by_folder,
    add_templates_to_folders,
    get_user_pinned_folders,
    update_user_pinned_folders,
    add_pinned_status_to_folders,
    create_localized_field,
    determine_folder_type
)
import dotenv
import os
from typing import List, Optional
from enum import Enum

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter(tags=["Folders"])

class FolderBase(BaseModel):
    name: str
    path: str
    description: Optional[str] = None

class FolderCreate(FolderBase):
    parent_id: Optional[int] = None

class FolderUpdate(FolderBase):
    pass

class PromptType(str, Enum):
    official = "official"
    user = "user"
    organization = "organization"

# ---------------------- ROUTE HANDLERS ----------------------

@router.get("")
async def get_folders(
    type: Optional[str] = None,
    folder_ids: Optional[str] = None,
    locale: Optional[str] = None,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get folders with optional filtering by type."""
    try:
        if type not in ["user", "official", "organization", None]:
            raise HTTPException(status_code=400, detail="Invalid folder type")
        
        # Default to English if locale not specified
        if not locale:
            locale = "en"
        
        folder_id_list = []
        if folder_ids:
            try:
                folder_id_list = [int(id_str) for id_str in folder_ids.split(',') if id_str.strip()]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid folder ID format: {str(e)}")
        
        if type:
            # Get specific folder type
            folders = await fetch_folders_by_type(
                supabase,
                folder_type=type,
                user_id=user_id if type == "user" else None,
                folder_ids=folder_id_list if folder_id_list else None,
                locale=locale
            )
            
            # Add templates if not in empty mode
            folder_ids_for_templates = [f["id"] for f in folders]
            templates = await fetch_templates_for_folders(supabase, folder_ids_for_templates, type, locale)
            templates_by_folder = organize_templates_by_folder(templates)
            folders_with_templates = add_templates_to_folders(folders, templates_by_folder)
            
            # Add pinned status for official and organization folders
            if type in ["official", "organization"]:
                pinned_folders = await get_user_pinned_folders(supabase, user_id)
                add_pinned_status_to_folders(folders_with_templates, pinned_folders[type])
            
            return {"success": True, "folders": folders_with_templates}
        else:
            # Get all folder types
            user_folders = await fetch_folders_by_type(supabase, "user", user_id=user_id, locale=locale)
            official_folders = await fetch_folders_by_type(supabase, "official", locale=locale)
            org_folders = await fetch_folders_by_type(supabase, "organization", user_id=user_id, locale=locale)
            
            # Add templates to each folder type
            for folder_type, folders in [("user", user_folders), ("official", official_folders), ("organization", org_folders)]:
                folder_ids_for_templates = [f["id"] for f in folders]
                templates = await fetch_templates_for_folders(supabase, folder_ids_for_templates, folder_type, locale)
                templates_by_folder = organize_templates_by_folder(templates)
                add_templates_to_folders(folders, templates_by_folder)
            
            # Add pinned status
            pinned_folders = await get_user_pinned_folders(supabase, user_id)
            add_pinned_status_to_folders(official_folders, pinned_folders["official"])
            add_pinned_status_to_folders(org_folders, pinned_folders["organization"])
            
            return {
                "success": True,
                "userFolders": user_folders,
                "officialFolders": official_folders,
                "organizationFolders": org_folders
            }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error retrieving folders: {str(e)}")

@router.post("")
async def create_folder(
    folder: FolderCreate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Create a new user folder."""
    try:
        # Prepare localized title and description
        title_json = create_localized_field(folder.name)
        description_json = create_localized_field(folder.description) if folder.description else {}
        
        # Insert new folder
        response = supabase.table("prompt_folders").insert({
            "user_id": user_id,
            "organization_id": None,
            "parent_folder_id": folder.parent_id,
            "title": title_json,
            "content": title_json,  # Use same as title for backward compatibility
            "description": description_json,
        }).execute()
        
        if response.data:
            from utils.prompts.folders import process_folder_for_response
            processed_folder = process_folder_for_response(response.data[0])

        
        return {
            "success": True,
            "folder": processed_folder
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating folder: {str(e)}")

@router.put("/{folder_id}")
async def update_folder(
    folder_id: int,
    folder: FolderUpdate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Update an existing user folder."""
    try:
        # Verify folder belongs to user
        verify = supabase.table("prompt_folders").select("id").eq("id", folder_id).eq("user_id", user_id).execute()
        
        if not verify.data:
            raise HTTPException(status_code=404, detail="Folder not found or doesn't belong to user")
        
        # Prepare localized updates
        title_json = create_localized_field(folder.name)
        description_json = create_localized_field(folder.description) if folder.description else {}
        
        # Update folder
        response = supabase.table("prompt_folders").update({
            "title": title_json,
            "content": title_json,
            "description": description_json
        }).eq("id", folder_id).execute()
        
        processed_folder = None
        if response.data:
            from utils.prompts.folders import process_folder_for_response
            processed_folder = process_folder_for_response(response.data[0])
            processed_folder["path"] = folder.path
        
        return {
            "success": True,
            "folder": processed_folder
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error updating folder: {str(e)}")

@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: int,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Delete a user folder."""
    try:
        # Verify folder belongs to user
        verify = supabase.table("prompt_folders").select("id").eq("id", folder_id).eq("user_id", user_id).execute()
        
        if not verify.data:
            raise HTTPException(status_code=404, detail="Folder not found or doesn't belong to user")
        
        # Delete folder
        supabase.table("prompt_folders").delete().eq("id", folder_id).execute()
        
        return {
            "success": True,
            "message": "Folder deleted"
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error deleting folder: {str(e)}")

@router.post("/pin/{folder_id}")
async def pin_folder(
    folder_id: int,
    folder_type: str = "official",
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Pin a folder for a user."""
    try:
        if folder_type not in ["official", "organization"]:
            raise HTTPException(status_code=400, detail="Invalid folder type")
        
        # Verify folder exists and is of correct type
        folder = supabase.table("prompt_folders").select("*").eq("id", folder_id).single().execute()
        if not folder.data:
            raise HTTPException(status_code=404, detail="Folder not found")
        
        actual_type = determine_folder_type(folder.data)
        if actual_type != folder_type:
            raise HTTPException(status_code=400, detail=f"Folder is not of type {folder_type}")
        
        # Get user's pinned folders
        pinned_folders = await get_user_pinned_folders(supabase, user_id)
        
        # Add folder ID to pinned list if not already there
        if folder_id not in pinned_folders[folder_type]:
            pinned_folders[folder_type].append(folder_id)
        
        # Update user's pinned folders
        await update_user_pinned_folders(supabase, user_id, folder_type, pinned_folders[folder_type])
        
        return {
            "success": True,
            "pinned_folders": pinned_folders[folder_type]
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error pinning folder: {str(e)}")

@router.post("/unpin/{folder_id}")
async def unpin_folder(
    folder_id: int,
    folder_type: str = "official",
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Unpin a folder for a user."""
    try:
        if folder_type not in ["official", "organization"]:
            raise HTTPException(status_code=400, detail="Invalid folder type")
        
        # Get user's pinned folders
        pinned_folders = await get_user_pinned_folders(supabase, user_id)
        
        # Remove folder ID from pinned list if present
        if folder_id in pinned_folders[folder_type]:
            pinned_folders[folder_type].remove(folder_id)
        
        # Update user's pinned folders
        await update_user_pinned_folders(supabase, user_id, folder_type, pinned_folders[folder_type])
        
        return {
            "success": True,
            "pinned_folders": pinned_folders[folder_type]
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error unpinning folder: {str(e)}")

@router.post("/update-pinned")
async def update_pinned_folders(
    official_folder_ids: List[int],
    organization_folder_ids: List[int],
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Update all pinned folders in one call."""
    try:
        # Update official pinned folders
        await update_user_pinned_folders(supabase, user_id, "official", official_folder_ids)
        
        # Update organization pinned folders
        await update_user_pinned_folders(supabase, user_id, "organization", organization_folder_ids)
        
        return {
            "success": True,
            "pinnedOfficialFolderIds": official_folder_ids,
            "pinnedOrganizationFolderIds": organization_folder_ids
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating pinned folders: {str(e)}")

@router.get("/template-folders")
async def get_template_folders(
    type: PromptType,
    folder_ids: Optional[str] = None,
    empty: bool = False,
    locale: Optional[str] = None,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get template folders by type with proper error handling."""
    try:
        # Default to English if locale not specified
        if not locale:
            locale = "en"
        
        # Parse folder_ids from comma-separated string to list of integers
        folder_id_list = []
        if folder_ids:
            try:
                folder_id_list = [int(id_str) for id_str in folder_ids.split(',') if id_str.strip()]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid folder ID format: {str(e)}")
        
        # Get folders based on type
        folders = await fetch_folders_by_type(
            supabase,
            folder_type=type.value,
            user_id=user_id if type == PromptType.user else None,
            folder_ids=folder_id_list if folder_id_list else None,
            locale=locale
        )
        
        # If empty flag is set, return folders without templates
        if empty:
            return {"success": True, "folders": folders}
        
        # Add templates to folders
        folder_ids_for_templates = [f["id"] for f in folders]
        templates = await fetch_templates_for_folders(supabase, folder_ids_for_templates, type.value, locale)
        templates_by_folder = organize_templates_by_folder(templates)
        folders_with_templates = add_templates_to_folders(folders, templates_by_folder)
        
        return {"success": True, "folders": folders_with_templates}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error retrieving template folders: {str(e)}")