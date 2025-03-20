# This file makes the prompts directory a Python package
from fastapi import APIRouter, Depends, HTTPException
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

# Create a parent router for all prompts-related endpoints
router = APIRouter(prefix="/prompts", tags=["Prompts"])

class FolderType(str, Enum):
    official = "official"
    organization = "organization"
    user = "user"

@router.get("/pinned-folders")
async def get_pinned_folders(
    type: Optional[FolderType] = None,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """
    Get pinned folders and their associated templates.
    If type is not specified, returns all types of folders.
    """
    try:
        # Get user metadata for pinned folders and organization ID
        user_metadata = supabase.table("users_metadata") \
            .select("pinned_official_folder_ids, pinned_organization_folder_ids, organization_id") \
            .eq("user_id", user_id) \
            .single() \
            .execute()

        if not user_metadata.data:
            return {"success": True, "folders": []}

        folders = []
        
        # Helper function to format templates
        def format_templates(templates):
            return [{
                "id": t["id"],
                "title": t["title"],
                "content": t["content"],
                "locale": t["locale"],
                "tags": t["tags"],
                "type": t["type"]
            } for t in templates]

        # Get official folders if requested
        if type in (None, FolderType.official):
            pinned_official_ids = user_metadata.data.get('pinned_official_folder_ids', [])
            if pinned_official_ids:
                official_folders = supabase.table("official_folders") \
                    .select("*") \
                    .in_("id", pinned_official_ids) \
                    .execute()
                
                if official_folders.data:
                    # Get templates for these folders
                    for folder in official_folders.data:
                        templates = supabase.table("prompt_templates") \
                            .select("*") \
                            .eq("folder_id", folder["id"]) \
                            .eq("type", "official") \
                            .execute()
                        
                        folders.append({
                            **folder,
                            "type": "official",
                            "templates": format_templates(templates.data) if templates.data else []
                        })

        # Get organization folders if requested
        if type in (None, FolderType.organization):
            org_id = user_metadata.data.get('organization_id')
            if org_id:
                org_folders = supabase.table("organization_folders") \
                    .select("*") \
                    .eq("organization_id", org_id) \
                    .execute()
                
                if org_folders.data:
                    for folder in org_folders.data:
                        templates = supabase.table("prompt_templates") \
                            .select("*") \
                            .eq("folder_id", folder["id"]) \
                            .eq("type", "organization") \
                            .execute()
                        
                        folders.append({
                            **folder,
                            "type": "organization",
                            "templates": format_templates(templates.data) if templates.data else []
                        })

        # Get user folders if requested
        if type in (None, FolderType.user):
            user_folders = supabase.table("user_folders") \
                .select("*") \
                .eq("user_id", user_id) \
                .execute()
            
            if user_folders.data:
                for folder in user_folders.data:
                    templates = supabase.table("prompt_templates") \
                        .select("*") \
                        .eq("folder_id", folder["id"]) \
                        .eq("type", "user") \
                        .execute()
                    
                    folders.append({
                        **folder,
                        "type": "user",
                        "templates": format_templates(templates.data) if templates.data else []
                    })

        # Get templates without folders (folder_id is null)
        if type is None or len(folders) == 0:
            root_templates = supabase.table("prompt_templates") \
                .select("*") \
                .is_("folder_id", "null")
            
            if type:
                root_templates = root_templates.eq("type", type)
            
            root_templates = root_templates.execute()
            
            if root_templates.data:
                folders.append({
                    "id": 0,
                    "path": "root",
                    "type": "root",
                    "templates": format_templates(root_templates.data)
                })

        return {
            "success": True,
            "folders": folders
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching pinned folders: {str(e)}")