from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
import dotenv
import os

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter(prefix="/user", tags=["User"])

class UserMetadata(BaseModel):
    name: str | None = None
    additional_email: str | None = None
    phone_number: str | None = None
    additional_organization: str | None = None
    pinned_official_folder_ids: list[int] | None = None
    pinned_organization_folder_ids: list[int] | None = None

@router.get("/metadata")
async def get_user_metadata(user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Get metadata for a specific user."""
    try:
        response = supabase.table("users_metadata") \
            .select("name, additional_email, phone_number, additional_organization, pinned_official_folder_ids, pinned_organization_folder_ids") \
            .eq("user_id", user_id) \
            .single() \
            .execute()
            
        if not response.data:
            return {
                "success": True,
                "data": {
                    "name": None,
                    "additional_email": None,
                    "phone_number": None,
                    "additional_organization": None,
                    "pinned_official_folder_ids": [],
                    "pinned_organization_folder_ids": []
                }
            }
            
        return {
            "success": True,
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user metadata: {str(e)}")

@router.get("/folders-with-prompts")
async def get_folders_with_prompts(user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Get all folders with their prompts, including pinned status."""
    try:
        # Get user metadata for pinned folders
        metadata = supabase.table("users_metadata") \
            .select("pinned_official_folder_ids, pinned_organization_folder_ids") \
            .eq("user_id", user_id) \
            .single() \
            .execute()
            
        pinned_official_folders = metadata.data.get('pinned_official_folder_ids', []) if metadata.data else []
        pinned_org_folders = metadata.data.get('pinned_organization_folder_ids', []) if metadata.data else []

        # Get all prompts
        prompts = supabase.table("prompt_templates") \
            .select("*") \
            .execute()

        # Get all folders
        official_folders = supabase.table("official_folders") \
            .select("*") \
            .execute()
            
        org_folders = supabase.table("organization_folders") \
            .select("*") \
            .execute()
            
        user_folders = supabase.table("user_folders") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()

        # Organize prompts by folder and type
        organized_folders = {
            "official": [],
            "organization": [],
            "user": []
        }

        # Process official folders
        for folder in official_folders.data or []:
            folder_prompts = [
                p for p in prompts.data 
                if p.get("folder_id") == folder["id"] and p.get("type") == "official"
            ]
            folder["prompts"] = folder_prompts
            folder["is_pinned"] = folder["id"] in pinned_official_folders
            organized_folders["official"].append(folder)

        # Process organization folders
        for folder in org_folders.data or []:
            folder_prompts = [
                p for p in prompts.data 
                if p.get("folder_id") == folder["id"] and p.get("type") == "organization"
            ]
            folder["prompts"] = folder_prompts
            folder["is_pinned"] = folder["id"] in pinned_org_folders
            organized_folders["organization"].append(folder)

        # Process user folders
        for folder in user_folders.data or []:
            folder_prompts = [
                p for p in prompts.data 
                if p.get("folder_id") == folder["id"] and p.get("type") == "user"
            ]
            folder["prompts"] = folder_prompts
            organized_folders["user"].append(folder)

        return {
            "success": True,
            "data": organized_folders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching folders with prompts: {str(e)}") 