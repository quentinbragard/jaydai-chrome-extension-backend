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
    organization_id: int | None = None  # Added field for organization_id
    pinned_official_folder_ids: list[int] | None = None
    pinned_organization_folder_ids: list[int] | None = None

async def get_organization_folder_ids(organization_id):
    """Get all folder IDs for a specific organization."""
    if not organization_id:
        return []
        
    try:
        response = supabase.table("organization_folders").select("id").eq("organization_id", organization_id).execute()
        return [folder['id'] for folder in (response.data or [])]
    except Exception as e:
        print(f"Error fetching organization folder IDs: {str(e)}")
        return []

@router.get("/metadata")
async def get_user_metadata(user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Get metadata for a specific user."""
    try:
        response = supabase.table("users_metadata") \
            .select("name, additional_email, phone_number, additional_organization, organization_id, pinned_official_folder_ids, pinned_organization_folder_ids") \
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
                    "organization_id": None,
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

@router.put("/metadata")
async def update_user_metadata(metadata: UserMetadata, user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Update user metadata with organization folder auto-pinning."""
    try:
        # Check if user metadata exists
        existing_metadata = supabase.table("users_metadata") \
            .select("organization_id, pinned_organization_folder_ids") \
            .eq("user_id", user_id) \
            .single() \
            .execute()
        
        update_data = {}
        
        # Only include fields that are provided
        if metadata.name is not None:
            update_data["name"] = metadata.name
            
        if metadata.additional_email is not None:
            update_data["additional_email"] = metadata.additional_email
            
        if metadata.phone_number is not None:
            update_data["phone_number"] = metadata.phone_number
            
        if metadata.additional_organization is not None:
            update_data["additional_organization"] = metadata.additional_organization
        
        # Handle organization_id update and auto-pin organization folders
        if metadata.organization_id is not None:
            # If organization has changed or is being set for the first time
            current_org_id = existing_metadata.data.get("organization_id") if existing_metadata.data else None
            if metadata.organization_id != current_org_id:
                update_data["organization_id"] = metadata.organization_id
                
                # Auto-pin all folders for this organization
                organization_folder_ids = await get_organization_folder_ids(metadata.organization_id)
                update_data["pinned_organization_folder_ids"] = organization_folder_ids
        
        # Handle explicit updates to pinned folder IDs (only if provided)
        if metadata.pinned_official_folder_ids is not None:
            update_data["pinned_official_folder_ids"] = metadata.pinned_official_folder_ids
            
        if metadata.pinned_organization_folder_ids is not None:
            update_data["pinned_organization_folder_ids"] = metadata.pinned_organization_folder_ids
        
        # Only proceed if there are changes to make
        if update_data:
            if existing_metadata.data:
                # Update existing record
                response = supabase.table("users_metadata") \
                    .update(update_data) \
                    .eq("user_id", user_id) \
                    .execute()
            else:
                # Create new record
                update_data["user_id"] = user_id
                response = supabase.table("users_metadata") \
                    .insert(update_data) \
                    .execute()
            
            return {
                "success": True,
                "data": response.data[0] if response.data else None
            }
        else:
            return {
                "success": True,
                "message": "No changes to update"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating user metadata: {str(e)}")

@router.get("/folders-with-prompts")
async def get_folders_with_prompts(
    locale: str = "en",  # Added locale parameter for content selection
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
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
            processed_folder = folder.copy()
            
            # Handle locale-specific folder name
            name_field = f"name_{locale}" if locale in ["en", "fr"] else "name_en"
            fallback_field = "name_en"
            
            if name_field in folder and folder[name_field]:
                processed_folder["name"] = folder[name_field]
            elif fallback_field in folder and folder[fallback_field]:
                processed_folder["name"] = folder[fallback_field]
            else:
                processed_folder["name"] = "Unnamed Folder"
                
            # Remove locale-specific fields
            processed_folder.pop("name_en", None)
            processed_folder.pop("name_fr", None)
            
            # Process prompts for this folder
            folder_prompts = []
            for p in prompts.data:
                if p.get("folder_id") == folder["id"] and p.get("type") == "official":
                    processed_prompt = p.copy()
                    
                    # Select content based on locale
                    content_field = f"content_{locale}" if locale in ["en", "fr"] else "content_en"
                    fallback_content = "content_en"
                    
                    if content_field in p and p[content_field]:
                        processed_prompt["content"] = p[content_field]
                    elif fallback_content in p and p[fallback_content]:
                        processed_prompt["content"] = p[fallback_content]
                    else:
                        processed_prompt["content"] = ""
                        
                    # Handle title if it has locale versions
                    title_field = f"title_{locale}" if locale in ["en", "fr"] else "title_en"
                    fallback_title = "title_en"
                    
                    if title_field in p and p[title_field]:
                        processed_prompt["title"] = p[title_field]
                    elif fallback_title in p and p[fallback_title]:
                        processed_prompt["title"] = p[fallback_title]
                        
                    # Remove locale fields
                    processed_prompt.pop("content_en", None)
                    processed_prompt.pop("content_fr", None)
                    processed_prompt.pop("title_en", None)
                    processed_prompt.pop("title_fr", None)
                    
                    folder_prompts.append(processed_prompt)
                    
            processed_folder["prompts"] = folder_prompts
            processed_folder["is_pinned"] = folder["id"] in pinned_official_folders
            organized_folders["official"].append(processed_folder)

        # Process organization folders (similarly to official folders)
        for folder in org_folders.data or []:
            processed_folder = folder.copy()
            
            # Handle locale-specific folder name
            name_field = f"name_{locale}" if locale in ["en", "fr"] else "name_en"
            fallback_field = "name_en"
            
            if name_field in folder and folder[name_field]:
                processed_folder["name"] = folder[name_field]
            elif fallback_field in folder and folder[fallback_field]:
                processed_folder["name"] = folder[fallback_field]
            else:
                processed_folder["name"] = "Unnamed Folder"
                
            # Remove locale-specific fields
            processed_folder.pop("name_en", None)
            processed_folder.pop("name_fr", None)
            
            # Process prompts for this folder
            folder_prompts = []
            for p in prompts.data:
                if p.get("folder_id") == folder["id"] and p.get("type") == "organization":
                    processed_prompt = p.copy()
                    
                    # Select content based on locale
                    content_field = f"content_{locale}" if locale in ["en", "fr"] else "content_en"
                    fallback_content = "content_en"
                    
                    if content_field in p and p[content_field]:
                        processed_prompt["content"] = p[content_field]
                    elif fallback_content in p and p[fallback_content]:
                        processed_prompt["content"] = p[fallback_content]
                    else:
                        processed_prompt["content"] = ""
                        
                    # Handle title if it has locale versions
                    title_field = f"title_{locale}" if locale in ["en", "fr"] else "title_en"
                    fallback_title = "title_en"
                    
                    if title_field in p and p[title_field]:
                        processed_prompt["title"] = p[title_field]
                    elif fallback_title in p and p[fallback_title]:
                        processed_prompt["title"] = p[fallback_title]
                        
                    # Remove locale fields
                    processed_prompt.pop("content_en", None)
                    processed_prompt.pop("content_fr", None)
                    processed_prompt.pop("title_en", None)
                    processed_prompt.pop("title_fr", None)
                    
                    folder_prompts.append(processed_prompt)
                    
            processed_folder["prompts"] = folder_prompts
            processed_folder["is_pinned"] = folder["id"] in pinned_org_folders
            organized_folders["organization"].append(processed_folder)

        # Process user folders (no name locale handling needed)
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