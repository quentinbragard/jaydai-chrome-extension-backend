# routes/user.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
from utils.prompts import (
    get_all_folder_ids_by_type,
    process_folder_for_response,
    process_template_for_response
)
import dotenv
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class OnboardingChecklistStatus(BaseModel):
    first_template_created: bool = False
    first_template_used: bool = False
    first_block_created: bool = False
    keyboard_shortcut_used: bool = False

class OnboardingChecklistUpdate(BaseModel):
    first_template_created: Optional[bool] = None
    first_template_used: Optional[bool] = None
    first_block_created: Optional[bool] = None
    keyboard_shortcut_used: Optional[bool] = None

dotenv.load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter(prefix="/user", tags=["User"])

class UserMetadata(BaseModel):
    name: str | None = None
    additional_email: str | None = None
    phone_number: str | None = None
    additional_organization: str | None = None
    company_id: str | None = None
    pinned_folder_ids: list[int] | None = None

class DataCollectionRequest(BaseModel):
    data_collection: bool

        
@router.get("/metadata")
async def get_user_metadata(user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Get metadata for a specific user."""
    try:
        response = supabase.table("users_metadata") \
            .select("name, additional_email, phone_number, additional_organization, company_id, pinned_folder_ids, pinned_template_ids, organization_ids, data_collection") \
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
                    "company_id": None,
                    "pinned_folder_ids": [],
                    "pinned_template_ids": [],
                    "data_collection": True
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
            .select("user_id") \
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
        
        # Handle company_id update and auto-pin organization folders
        if metadata.company_id is not None:
            # If organization has changed or is being set for the first time
            current_org_id = existing_metadata.data.get("company_id") if existing_metadata.data else None
            if metadata.company_id != current_org_id:
                update_data["company_id"] = metadata.company_id
                
                # Auto-pin all folders for this organization using utility
                organization_folder_ids = await get_all_folder_ids_by_type(
                    supabase, 
                    "organization", 
                    str(metadata.company_id)
                )
                update_data["pinned_organization_folder_ids"] = organization_folder_ids
        
        # Handle explicit updates to pinned folder IDs (only if provided)
        if metadata.pinned_folder_ids is not None:
            update_data["pinned_folder_ids"] = metadata.pinned_folder_ids
        
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

@router.put("/data-collection")
async def update_data_collection(request: DataCollectionRequest, user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Update user's data collection preference."""
    try:
        # Check if user metadata exists
        existing_metadata = supabase.table("users_metadata") \
            .select("user_id") \
            .eq("user_id", user_id) \
            .single() \
            .execute()
        
        update_data = {"data_collection": request.data_collection}
        
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
            "data": response.data[0] if response.data else None,
            "message": f"Data collection {'enabled' if request.data_collection else 'disabled'}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating data collection preference: {str(e)}")

@router.get("/folders-with-prompts")
async def get_folders_with_prompts(
    locale: str = "en",
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Get all folders with their prompts, including pinned status."""
    try:
        # Get user metadata for pinned folders
        metadata = supabase.table("users_metadata") \
            .select("pinned_folder_ids, company_id") \
            .eq("user_id", user_id) \
            .single() \
            .execute()
            
        # Get the unified pinned folder IDs list
        pinned_folder_ids = metadata.data.get('pinned_folder_ids', []) if metadata.data else []
        user_company_id = metadata.data.get('company_id') if metadata.data else None
        
        # Get all prompts
        prompts = supabase.table("prompt_templates") \
            .select("*") \
            .execute()

        # Get folders from unified table
        # Official folders (type = 'official')
        official_folders_response = supabase.table("prompt_folders") \
            .select("*") \
            .eq("type", "official") \
            .execute()
        
        # Organization/Company folders (type = 'organization' or 'company')
        company_folders_response = None
        if user_company_id:
            company_folders_response = supabase.table("prompt_folders") \
                .select("*") \
                .eq("company_id", user_company_id) \
                .in_("type", ["organization", "company"]) \
                .execute()
        
        # User folders (type = 'user')
        user_folders_response = supabase.table("prompt_folders") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("type", "user") \
            .execute()

        # Organize prompts by folder and type
        organized_folders = {
            "official": [],
            "organization": [],
            "user": []
        }

        # Process official folders
        for folder in official_folders_response.data or []:
            processed_folder = process_folder_for_response(folder, locale)
            
            # Process prompts for this folder
            folder_prompts = []
            for p in prompts.data or []:
                if p.get("folder_id") == folder["id"] and p.get("type") == "official":
                    processed_prompt = process_template_for_response(p, locale)
                    folder_prompts.append(processed_prompt)
                    
            processed_folder["prompts"] = folder_prompts
            # Check if this folder is pinned using the unified list
            processed_folder["is_pinned"] = folder["id"] in pinned_folder_ids
            organized_folders["official"].append(processed_folder)

        # Process organization/company folders
        if company_folders_response:
            for folder in company_folders_response.data or []:
                processed_folder = process_folder_for_response(folder, locale)
                
                # Process prompts for this folder
                folder_prompts = []
                for p in prompts.data or []:
                    # Check for both 'organization' and 'company' type templates
                    if (p.get("folder_id") == folder["id"] and 
                        p.get("type") in ["organization", "company"]):
                        processed_prompt = process_template_for_response(p, locale)
                        folder_prompts.append(processed_prompt)
                        
                processed_folder["prompts"] = folder_prompts
                # Check if this folder is pinned using the unified list
                processed_folder["is_pinned"] = folder["id"] in pinned_folder_ids
                organized_folders["organization"].append(processed_folder)

        # Process user folders + root templates
        # First, handle folders with IDs
        for folder in user_folders_response.data or []:
            processed_folder = process_folder_for_response(folder, locale)
            
            # Get prompts for this folder
            folder_prompts = []
            for p in prompts.data or []:
                if p.get("folder_id") == folder["id"] and p.get("type") == "user":
                    processed_prompt = process_template_for_response(p, locale)
                    folder_prompts.append(processed_prompt)
            
            processed_folder["prompts"] = folder_prompts
            # User folders are never pinned (pinning only applies to official/org folders)
            processed_folder["is_pinned"] = False
            organized_folders["user"].append(processed_folder)

        # Handle root templates (user templates with no folder_id)
        root_prompts = []
        for p in prompts.data or []:
            if (p.get("folder_id") is None and 
                p.get("type") == "user" and 
                p.get("user_id") == user_id):
                processed_prompt = process_template_for_response(p, locale)
                root_prompts.append(processed_prompt)
        
        # If there are root prompts, create a virtual root folder
        if root_prompts:
            virtual_root_folder = {
                "id": 0,
                "created_at": None,
                "user_id": user_id,
                "organization_id": None,
                "parent_folder_id": None,
                "content": {
                    "en": "Root Templates",
                    "fr": "Modèles Racine"
                },
                "description": "Templates not assigned to any folder",
                "company_id": None,
                "type": "user",
                "name": "Root Templates",
                "prompts": root_prompts,
                "is_pinned": False
            }
            
            # Add virtual root folder at the beginning
            organized_folders["user"].insert(0, virtual_root_folder)

        return {
            "success": True,
            "data": organized_folders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching folders with prompts: {str(e)}")
    
@router.get("/onboarding/status")
async def get_onboarding_status(user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    try:
        # Get user metadata for onboarding status
        metadata = supabase.table("users_metadata") \
            .select("job_type, job_industry, job_seniority, interests, signup_source") \
            .eq("user_id", user_id) \
            .single() \
            .execute()

        # Check if metadata exists and has any of the required fields
        has_completed = False
        if metadata.data:
            job_type = metadata.data.get("job_type")
            job_industry = metadata.data.get("job_industry")
            job_seniority = metadata.data.get("job_seniority")
            interests = metadata.data.get("interests")
            signup_source = metadata.data.get("signup_source")
            
            has_completed = bool(job_type or job_industry or job_seniority or interests or signup_source)

        return {
            "success": True,
            "data": {"has_completed_onboarding": has_completed}
        }
    except Exception as e:
        logger.error(f"Error in onboarding status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking onboarding status: {str(e)}")
    

@router.get("/onboarding-checklist")
async def get_onboarding_checklist(user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Get the current onboarding checklist status for a user."""
    try:
        # Get user metadata for onboarding checklist
        metadata = supabase.table("users_metadata") \
            .select("first_template_created, first_template_used, first_block_created, keyboard_shortcut_used") \
            .eq("user_id", user_id) \
            .single() \
            .execute()

        # Default values if no metadata exists
        default_status = {
            "first_template_created": False,
            "first_template_used": False, 
            "first_block_created": False,
            "keyboard_shortcut_used": False
        }

        if metadata.data:
            # Update defaults with actual values, keeping defaults for missing fields
            for key in default_status:
                if key in metadata.data and metadata.data[key] is not None:
                    default_status[key] = metadata.data[key]

        # Calculate progress
        completed_count = sum(1 for status in default_status.values() if status)
        total_count = len(default_status)

        return {
            "success": True,
            "data": {
                **default_status,
                "progress": f"{completed_count}/{total_count}",
                "completed_count": completed_count,
                "total_count": total_count,
                "is_complete": completed_count == total_count
            }
        }
    except Exception as e:
        logger.error(f"Error fetching onboarding checklist: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching onboarding checklist: {str(e)}")

@router.post("/onboarding-checklist")
async def update_onboarding_checklist(
    checklist_update: OnboardingChecklistUpdate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Update specific items in the onboarding checklist."""
    try:
        # Check if user metadata exists
        existing_metadata = supabase.table("users_metadata") \
            .select("user_id") \
            .eq("user_id", user_id) \
            .single() \
            .execute()

        # Build update data with only the fields that were provided
        update_data = {}
        if checklist_update.first_template_created is not None:
            update_data["first_template_created"] = checklist_update.first_template_created
        if checklist_update.first_template_used is not None:
            update_data["first_template_used"] = checklist_update.first_template_used
        if checklist_update.first_block_created is not None:
            update_data["first_block_created"] = checklist_update.first_block_created
        if checklist_update.keyboard_shortcut_used is not None:
            update_data["keyboard_shortcut_used"] = checklist_update.keyboard_shortcut_used

        if not update_data:
            raise HTTPException(status_code=400, detail="No valid fields to update")

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

        # Return updated status
        updated_checklist = await get_onboarding_checklist(user_id)
        
        return {
            "success": True,
            "data": updated_checklist["data"],
            "message": "Onboarding checklist updated successfully"
        }

    except Exception as e:
        logger.error(f"Error updating onboarding checklist: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error updating onboarding checklist: {str(e)}")

@router.post("/onboarding-checklist/mark-complete/{action}")
async def mark_onboarding_action_complete(
    action: str,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Mark a specific onboarding action as complete. Convenience endpoint for individual actions."""
    try:
        valid_actions = ["first_template_created", "first_template_used", "first_block_created", "keyboard_shortcut_used"]
        
        if action not in valid_actions:
            raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {valid_actions}")

        # Create update object with just this action
        update_data = OnboardingChecklistUpdate(**{action: True})
        
        # Use the existing update endpoint
        return await update_onboarding_checklist(update_data, user_id)

    except Exception as e:
        logger.error(f"Error marking onboarding action complete: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error marking onboarding action complete: {str(e)}")
    
