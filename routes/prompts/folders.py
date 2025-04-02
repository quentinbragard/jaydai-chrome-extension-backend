from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
import dotenv
import os
from typing import List, Optional, Dict, Any, Union
from enum import Enum

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter(tags=["Folders"])  # Remove prefix here to avoid double prefix

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

# ---------------------- REUSABLE DATA ACCESS FUNCTIONS ----------------------

async def fetch_folders(table_name: str, **filters) -> List[Dict]:
    """Generic function to fetch folders with optional filters including locale."""
    query = supabase.table(table_name).select("*")
    
    # Handle locale filtering for official and organization folders
    locale = filters.pop("locale", None)
    
    # Apply standard filters
    for key, value in filters.items():
        if key == "in_column":
            if "in_values" in filters and filters["in_values"]:
                query = query.in_(value, filters["in_values"])
        elif key != "in_values":  # Skip the in_values item since it's used with in_column
            query = query.eq(key, value)
    
    # Apply locale filter for official and organization folders
    if locale and table_name in ["official_folders", "organization_folders"]:
        query = query.eq("locale", locale)
        response = query.execute()
        
        # If no folders found with specific locale, fallback to English
        if not response.data and locale != "en":
            # Reset query and try with English locale
            query = supabase.table(table_name).select("*")
            
            # Reapply standard filters
            for key, value in filters.items():
                if key == "in_column":
                    if "in_values" in filters and filters["in_values"]:
                        query = query.in_(value, filters["in_values"])
                elif key != "in_values":  
                    query = query.eq(key, value)
            
            # Apply English locale filter
            query = query.eq("locale", "en")
            response = query.execute()
            return response.data or []
    else:
        # Execute without locale filtering
        response = query.execute()
    
    return response.data or []

async def fetch_templates(folder_ids: List[int], folder_type: str) -> List[Dict]:
    """Generic function to fetch templates for given folder IDs and type."""
    if not folder_ids:
        return []
        
    response = supabase.table("prompt_templates") \
        .select("*") \
        .eq("type", folder_type) \
        .in_("folder_id", folder_ids) \
        .execute()
        
    return response.data or []

def organize_templates_by_folder(templates: List[Dict]) -> Dict[int, List[Dict]]:
    """Group templates by their folder_id."""
    templates_by_folder = {}
    for template in templates:
        folder_id = template.get("folder_id")
        if folder_id is not None:
            if folder_id not in templates_by_folder:
                templates_by_folder[folder_id] = []
            templates_by_folder[folder_id].append(template)
    return templates_by_folder

def add_templates_to_folders(folders: List[Dict], templates_by_folder: Dict[int, List[Dict]]) -> List[Dict]:
    """Add templates to their respective folders."""
    folders_with_templates = []
    for folder in folders:
        folder_with_templates = folder.copy()
        folder_with_templates["templates"] = templates_by_folder.get(folder["id"], [])
        folders_with_templates.append(folder_with_templates)
    return folders_with_templates

async def get_template_folders_by_type(
    folder_type: str, 
    folder_ids: Optional[List[int]] = None, 
    user_id: Optional[str] = None,
    empty: bool = False,
    locale: Optional[str] = None
) -> Dict:
    """Central function to get template folders by type with optional filtering."""
    # Determine table name based on folder type
    table_name = {
        "official": "official_folders",
        "organization": "organization_folders",
        "user": "user_folders"
    }.get(folder_type)
    
    if not table_name:
        raise ValueError(f"Invalid folder type: {folder_type}")
    
    # Define filters based on parameters
    filters = {}
    
    # Add locale to filters for official and organization folders
    if folder_type in ["official", "organization"] and locale:
        filters["locale"] = locale
    
    if folder_type == "user" and user_id:
        filters["user_id"] = user_id
    elif folder_type == "organization" and user_id:
        # Get user's organization ID first
        user_metadata = supabase.table("users_metadata").select("organization_id").eq("user_id", user_id).single().execute()
        org_id = user_metadata.data.get("organization_id") if user_metadata.data else None
        if org_id:
            filters["organization_id"] = org_id
    
    # If specific folder IDs are provided, use them
    if folder_ids:
        filters["in_column"] = "id"
        filters["in_values"] = folder_ids
    
    # Fetch folders with possible locale filtering
    folders = await fetch_folders(table_name, **filters)
    
    # If empty flag is set, return folders without templates
    if empty:
        return {"success": True, "folders": folders}
    
    # Get folder IDs for template query
    all_folder_ids = [folder["id"] for folder in folders]
    
    # Fetch templates - no need to filter by locale here since we filtered the folders
    templates = await fetch_templates(all_folder_ids, folder_type)
    
    # Organize templates by folder
    templates_by_folder = organize_templates_by_folder(templates)
    
    # Add templates to folders
    folders_with_templates = add_templates_to_folders(folders, templates_by_folder)
    
    return {"success": True, "folders": folders_with_templates}


async def get_user_pinned_folders(user_id: str) -> Dict[str, List[int]]:
    """Get user's pinned folder IDs."""
    user_metadata = supabase.table("users_metadata").select("*").eq("user_id", user_id).single().execute()
    
    if not user_metadata.data:
        return {"official": [], "organization": []}
    
    return {
        "official": user_metadata.data.get("pinned_official_folder_ids") or [],
        "organization": user_metadata.data.get("pinned_organization_folder_ids") or []
    }

async def update_user_pinned_folders(user_id: str, folder_type: str, folder_ids: List[int]) -> Dict:
    """Update user's pinned folder IDs."""
    user_metadata = supabase.table("users_metadata").select("*").eq("user_id", user_id).single().execute()
    
    field_name = f"pinned_{folder_type}_folder_ids"
    
    if not user_metadata.data:
        # Create new user metadata
        metadata = {"user_id": user_id}
        metadata[field_name] = folder_ids
        response = supabase.table("users_metadata").insert(metadata).execute()
    else:
        # Update existing metadata
        response = supabase.table("users_metadata").update({
            field_name: folder_ids
        }).eq("user_id", user_id).execute()
    
    return {"success": True, "updated_folder_ids": folder_ids}

# ---------------------- ROUTE HANDLERS ----------------------

@router.get("")
async def get_folders(
    type: Optional[str] = None,
    folder_ids: Optional[str] = None,  # Accept a comma-separated string
    locale: Optional[str] = None,  # Add locale parameter
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """
    Get folders with optional filtering by type.
    
    Parameters:
    - type: Optional filter by folder type ('user', 'official', or 'organization')
    - folder_ids: Optional comma-separated string of folder IDs to filter by
    - locale: Optional locale code to filter templates by language (e.g., 'en', 'fr')
    """
    try:
        if type not in ["user", "official", "organization", None]:
            raise HTTPException(status_code=400, detail="Invalid folder type")
        folder_id_list = []
        if folder_ids:
            try:
                folder_id_list = [int(id_str) for id_str in folder_ids.split(',') if id_str.strip()]
                print(f"Parsed folder IDs: {folder_id_list} from {folder_ids}")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid folder ID format: {str(e)}")
            
        if type:
            # Get specific folder type
            result = await get_template_folders_by_type(
                folder_type=type,
                folder_ids=folder_id_list if folder_id_list else None,
                user_id=user_id if type == PromptType.user else None,
                locale=locale  # Pass locale parameter
            )
            
            # For official and organization folders, add pinned status
            if type in ["official", "organization"]:
                pinned_folders = await get_user_pinned_folders(user_id)
                
                for folder in result["folders"]:
                    folder["is_pinned"] = folder["id"] in pinned_folders[type]
            
            return result
        else:
            # Get all folder types
            user_folders = await get_template_folders_by_type("user", user_id=user_id)
            
            official_folders = await get_template_folders_by_type("official", locale=locale)
            org_folders = await get_template_folders_by_type("organization", user_id=user_id, locale=locale)
            
            # Add pinned status for official and organization folders
            pinned_folders = await get_user_pinned_folders(user_id)
            
            for folder in official_folders["folders"]:
                folder["is_pinned"] = folder["id"] in pinned_folders["official"]
                
            for folder in org_folders["folders"]:
                folder["is_pinned"] = folder["id"] in pinned_folders["organization"]
            
            return {
                "success": True,
                "userFolders": user_folders["folders"],
                "officialFolders": official_folders["folders"],
                "organizationFolders": org_folders["folders"]
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
        # Insert new folder
        response = supabase.table("user_folders").insert({
            "user_id": user_id,
            "name": folder.name,
            "path": folder.path,
            "description": folder.description,
        }).execute()
        
        return {
            "success": True,
            "folder": response.data[0] if response.data else None
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
        verify = supabase.table("user_folders").select("id").eq("id", folder_id).eq("user_id", user_id).execute()
        
        if not verify.data:
            raise HTTPException(status_code=404, detail="Folder not found or doesn't belong to user")
        
        # Update folder
        response = supabase.table("user_folders").update({
            "name": folder.name,
            "path": folder.path,
            "description": folder.description
        }).eq("id", folder_id).execute()
        
        return {
            "success": True,
            "folder": response.data[0] if response.data else None
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
        verify = supabase.table("user_folders").select("id").eq("id", folder_id).eq("user_id", user_id).execute()
        
        if not verify.data:
            raise HTTPException(status_code=404, detail="Folder not found or doesn't belong to user")
        
        # Delete folder
        supabase.table("user_folders").delete().eq("id", folder_id).execute()
        
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
    folder_type: str = "official",  # Changed from is_official to folder_type for flexibility
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Pin a folder for a user."""
    try:
        if folder_type not in ["official", "organization"]:
            raise HTTPException(status_code=400, detail="Invalid folder type")
            
        # Get user's pinned folders
        pinned_folders = await get_user_pinned_folders(user_id)
        
        # Add folder ID to pinned list if not already there
        if folder_id not in pinned_folders[folder_type]:
            pinned_folders[folder_type].append(folder_id)
            
        # Update user's pinned folders
        await update_user_pinned_folders(user_id, folder_type, pinned_folders[folder_type])
        
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
    folder_type: str = "official",  # Changed from is_official to folder_type
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Unpin a folder for a user."""
    try:
        if folder_type not in ["official", "organization"]:
            raise HTTPException(status_code=400, detail="Invalid folder type")
            
        # Get user's pinned folders
        pinned_folders = await get_user_pinned_folders(user_id)
        
        # Remove folder ID from pinned list if present
        if folder_id in pinned_folders[folder_type]:
            pinned_folders[folder_type].remove(folder_id)
            
        # Update user's pinned folders
        await update_user_pinned_folders(user_id, folder_type, pinned_folders[folder_type])
        
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
        await update_user_pinned_folders(user_id, "official", official_folder_ids)
        
        # Update organization pinned folders
        await update_user_pinned_folders(user_id, "organization", organization_folder_ids)
        
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
    folder_ids: Optional[str] = None,  # Accept a comma-separated string
    empty: bool = False,
    locale: Optional[str] = None,  # Add locale parameter
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """
    Get template folders by type with proper error handling
    
    Parameters:
    - type: Type of folders to fetch ('user', 'official', or 'organization')
    - folder_ids: Optional comma-separated string of folder IDs to filter by
    - empty: Whether to return folders without templates
    - locale: Optional locale code to filter templates by language (e.g., 'en', 'fr')
    """
    try:
        # Parse folder_ids from comma-separated string to list of integers
        folder_id_list = []
        if folder_ids:
            try:
                folder_id_list = [int(id_str) for id_str in folder_ids.split(',') if id_str.strip()]
                print(f"Parsed folder IDs: {folder_id_list} from {folder_ids}")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid folder ID format: {str(e)}")
        
        print(f"Get template folders request: type={type}, folder_ids={folder_id_list}, empty={empty}, locale={locale}")
        
        # Get folders based on type
        result = await get_template_folders_by_type(
            folder_type=type.value,
            folder_ids=folder_id_list if folder_id_list else None,
            user_id=user_id if type == PromptType.user else None,
            empty=empty,
            locale=locale  # Pass locale parameter
        )
        
        return result
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"Error retrieving template folders: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving template folders: {str(e)}")