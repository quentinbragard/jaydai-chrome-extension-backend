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

router = APIRouter(prefix="/folders", tags=["Folders"])

class FolderBase(BaseModel):
    name: str
    path: str
    description: Optional[str] = None

class FolderCreate(FolderBase):
    parent_id: Optional[int] = None

class FolderUpdate(FolderBase):
    pass

@router.get("/")
async def get_folders(
    type: Optional[str] = None,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """
    Get folders with optional filtering by type.
    
    Parameters:
    - type: Optional filter by folder type ('user', 'official', or 'organization')
    - user_id: Optional user ID to filter folders
    """
    try:    
        if type == "user":
            return await get_user_folders(user_id)
        elif type == "official":
            return await get_official_folders(user_id)
        elif type == "organization":
            return await get_organization_folders(user_id)
        else:
            # Get all folders
            return await get_all_folders(user_id)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving folders: {str(e)}")

async def get_user_folders(user_id: str):
    """Get user's personal folders."""
    try:
        # Get user's folders
        response = supabase.table("user_folders").select("*").eq("user_id", user_id).execute()
        user_folder_ids = [folder['id'] for folder in response.data]
        
        # Get templates to count how many are in each folder
        templates_response = supabase.table("prompt_templates").select("*").in_("folder_id", user_folder_ids).execute()
        templates = templates_response.data or []
        
        # Count templates per folder
        folder_template_counts = {}
        for template in templates:
            folder_id = template.get('folder_id')
            if folder_id:
                folder_template_counts[folder_id] = folder_template_counts.get(folder_id, 0) + 1
        
        # Add template count to folders
        folders = response.data or []
        for folder in folders:
            folder['template_count'] = folder_template_counts.get(folder['id'], 0)
        
        return {
            "success": True,
            "folders": folders
        }
    except Exception as e:
       raise HTTPException(status_code=500, detail=f"Error retrieving user folders: {str(e)}")

async def get_official_folders(user_id: str):
    """Get official folders."""
    try:
        # Get user metadata to check for pinned folders
        user_metadata = supabase.table("users_metadata").select("*").eq("user_id", user_id).single().execute()
        
        pinned_folder_ids = []
        if user_metadata.data and 'pinned_official_folder_ids' in user_metadata.data:
            pinned_folder_ids = user_metadata.data['pinned_official_folder_ids'] or []
        
        # Get official folders
        response = supabase.table("official_folders").select("*").execute()
        
        # Mark folders as pinned
        folders = response.data or []
        for folder in folders:
            folder['is_pinned'] = folder['id'] in pinned_folder_ids
        
        return {
            "success": True,
            "folders": folders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving official folders: {str(e)}")

async def get_organization_folders(user_id: str):
    """Get organization folders for the user's organization."""
    try:
        # Get user metadata to check for organization_id and pinned folders
        user_metadata = supabase.table("users_metadata").select("*").eq("user_id", user_id).single().execute()
        
        organization_id = None
        if user_metadata.data and 'organization_id' in user_metadata.data:
            organization_id = user_metadata.data['organization_id']
        
        if not organization_id:
            return {
                "success": True,
                "folders": [],
            }
        
        pinned_folder_ids = []
        if user_metadata.data and 'pinned_organization_folder_ids' in user_metadata.data:
            pinned_folder_ids = user_metadata.data['pinned_organization_folder_ids'] or []
        
        # Get organization folders
        response = supabase.table("organization_folders").select("*").eq("organization_id", organization_id).execute()
        
        # Mark folders as pinned
        folders = response.data or []
        for folder in folders:
            folder['is_pinned'] = folder['id'] in pinned_folder_ids
        
        return {
            "success": True,
            "folders": folders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving organization folders: {str(e)}")

async def get_all_folders(user_id: str):
    """Get all folders (user, official, organization)."""
    try:
        # Get user's folders
        user_folders_result = await get_user_folders(user_id)
        
        # Get official folders
        official_folders_result = await get_official_folders(user_id)
        
        # Get organization folders
        organization_folders_result = await get_organization_folders(user_id)
        
        return {
            "success": True,
            "userFolders": user_folders_result.get("folders", []),
            "officialFolders": official_folders_result.get("folders", []),
            "organizationFolders": organization_folders_result.get("folders", []),
            "pinnedOfficialFolderIds": official_folders_result.get("pinned_folder_ids", []),
            "pinnedOrganizationFolderIds": organization_folders_result.get("pinned_folder_ids", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving all folders: {str(e)}")

@router.post("/")
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
            "parent_id": folder.parent_id
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
    is_official: bool = True,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Pin a folder for a user."""
    try:
        # Get current user metadata
        user_metadata = supabase.table("users_metadata").select("*").eq("user_id", user_id).single().execute()
        
        if not user_metadata.data:
            # Create user metadata if it doesn't exist
            if is_official:
                pinned_folders = [folder_id]
                supabase.table("users_metadata").insert({
                    "user_id": user_id,
                    "pinned_official_folder_ids": pinned_folders,
                    "pinned_organization_folder_ids": []
                }).execute()
            else:
                pinned_folders = [folder_id]
                supabase.table("users_metadata").insert({
                    "user_id": user_id,
                    "pinned_official_folder_ids": [],
                    "pinned_organization_folder_ids": pinned_folders
                }).execute()
        else:
            # Update existing pinned folders
            if is_official:
                pinned_folders = user_metadata.data.get('pinned_official_folder_ids') or []
                if folder_id not in pinned_folders:
                    pinned_folders.append(folder_id)
                    
                # Update metadata
                supabase.table("users_metadata").update({
                    "pinned_official_folder_ids": pinned_folders
                }).eq("user_id", user_id).execute()
            else:
                pinned_folders = user_metadata.data.get('pinned_organization_folder_ids') or []
                if folder_id not in pinned_folders:
                    pinned_folders.append(folder_id)
                    
                # Update metadata
                supabase.table("users_metadata").update({
                    "pinned_organization_folder_ids": pinned_folders
                }).eq("user_id", user_id).execute()
        
        return {
            "success": True,
            "pinned_folders": pinned_folders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error pinning folder: {str(e)}")

@router.post("/unpin/{folder_id}")
async def unpin_folder(
    folder_id: int,
    is_official: bool = True,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Unpin a folder for a user."""
    try:
        # Get current user metadata
        user_metadata = supabase.table("users_metadata").select("*").eq("user_id", user_id).single().execute()
        
        if not user_metadata.data:
            return {
                "success": True,
                "pinned_folders": []
            }
        
        # Update existing pinned folders
        if is_official:
            pinned_folders = user_metadata.data.get('pinned_official_folder_ids') or []
            if folder_id in pinned_folders:
                pinned_folders.remove(folder_id)
                
            # Update metadata
            supabase.table("users_metadata").update({
                "pinned_official_folder_ids": pinned_folders
            }).eq("user_id", user_id).execute()
        else:
            pinned_folders = user_metadata.data.get('pinned_organization_folder_ids') or []
            if folder_id in pinned_folders:
                pinned_folders.remove(folder_id)
                
            # Update metadata
            supabase.table("users_metadata").update({
                "pinned_organization_folder_ids": pinned_folders
            }).eq("user_id", user_id).execute()
        
        return {
            "success": True,
            "pinned_folders": pinned_folders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error unpinning folder: {str(e)}")

@router.post("/update-pinned")
async def update_pinned_folders(
    official_folder_ids: List[int],
    organization_folder_ids: List[int],
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Update all pinned folders in one call."""
    try:
        # Get current user metadata
        user_metadata = supabase.table("users_metadata").select("*").eq("user_id", user_id).single().execute()
        
        if not user_metadata.data:
            # Create user metadata if it doesn't exist
            supabase.table("users_metadata").insert({
                "user_id": user_id,
                "pinned_official_folder_ids": official_folder_ids,
                "pinned_organization_folder_ids": organization_folder_ids
            }).execute()
        else:
            # Update metadata
            supabase.table("users_metadata").update({
                "pinned_official_folder_ids": official_folder_ids,
                "pinned_organization_folder_ids": organization_folder_ids
            }).eq("user_id", user_id).execute()
        
        return {
            "success": True,
            "pinnedOfficialFolderIds": official_folder_ids,
            "pinnedOrganizationFolderIds": organization_folder_ids
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating pinned folders: {str(e)}")