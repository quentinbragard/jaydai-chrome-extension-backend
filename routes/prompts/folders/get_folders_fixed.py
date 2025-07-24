# routes/prompts/folders/get_folders_fixed.py
"""
Fixed version of get_folders that works with the Supabase Python client
"""
from typing import List, Optional, Dict, Any
from fastapi import Depends, HTTPException, Query, Request
from models.common import APIResponse
from utils import supabase_helpers
from .helpers import supabase, router
from utils.prompts import process_folder_for_response, process_template_for_response
from utils.middleware.localization import extract_locale_from_request
from utils.access_control import get_accessible_folders_batch, get_accessible_templates_batch, get_user_metadata
import time
import logging

logger = logging.getLogger(__name__)

@router.get("/fixed", response_model=APIResponse[Dict])
async def get_folders_fixed(
    request: Request,
    type: Optional[str] = Query(None, description="Folder type filter (user, company, organization)"),
    withSubfolders: bool = Query(False, description="Include nested subfolders"),
    withTemplates: bool = Query(False, description="Include templates for each folder"),
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[Dict]:
    """
    Fixed version of get_folders that works with the current Supabase client.
    Uses multiple queries instead of complex OR conditions.
    """
    try:
        start_time = time.time()
        locale = extract_locale_from_request(request)
        
        logger.info(f"Getting folders for user {user_id}, type={type}, locale={locale}")
        
        # Get all accessible folders using the fixed batch function
        all_folders = get_accessible_folders_batch(supabase, user_id)
        
        query_time = (time.time() - start_time) * 1000
        logger.info(f"Retrieved {len(all_folders)} folders in {query_time:.2f}ms")
        
        # Get user metadata for folder type determination
        user_metadata = get_user_metadata(supabase, user_id)
        
        # Organize folders by type
        folders_by_type = {"user": [], "company": [], "organization": []}
        
        for folder in all_folders:
            folder_type = determine_folder_type_safe(folder, user_metadata)
            
            # Filter by type if specified
            if type and folder_type != type:
                continue
                
            # Process folder for response
            processed_folder = process_folder_for_response(folder, locale)
            folders_by_type[folder_type].append(processed_folder)
        
        # Get templates if requested
        if withTemplates:
            template_start = time.time()
            
            # Get all folder IDs that we're returning
            all_folder_ids = []
            for folder_type_name in folders_by_type:
                for folder in folders_by_type[folder_type_name]:
                    all_folder_ids.append(folder["id"])
            
            if all_folder_ids:
                # Get all templates for these folders
                all_templates = get_accessible_templates_batch(supabase, user_id, all_folder_ids)
                
                # Group templates by folder_id
                templates_by_folder = {}
                for template in all_templates:
                    folder_id = template.get("folder_id")
                    if folder_id:
                        if folder_id not in templates_by_folder:
                            templates_by_folder[folder_id] = []
                        
                        processed_template = process_template_for_response(template, locale)
                        templates_by_folder[folder_id].append(processed_template)
                
                # Add templates to folders
                for folder_type_name in folders_by_type:
                    for folder in folders_by_type[folder_type_name]:
                        folder["templates"] = templates_by_folder.get(folder["id"], [])
            
            template_time = (time.time() - template_start) * 1000
            logger.info(f"Template processing took {template_time:.2f}ms")
        
        # Handle nested folders if requested
        if withSubfolders:
            for folder_type_name in folders_by_type:
                folders_by_type[folder_type_name] = build_folder_hierarchy(
                    folders_by_type[folder_type_name]
                )
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Total get_folders_fixed took {total_time:.2f}ms")
        
        # Prepare result
        result = {"folders": {}}
        
        # Only include requested folder types
        if type:
            if type in folders_by_type:
                result["folders"][type] = folders_by_type[type]
        else:
            result["folders"] = folders_by_type
        
        return APIResponse(success=True, data=result)
        
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"Error in get_folders_fixed after {total_time:.2f}ms: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving folders: {str(e)}")


def determine_folder_type_safe(folder: Dict[str, Any], user_metadata: Dict[str, Any]) -> str:
    """Safely determine folder type based on ownership"""
    try:
        if folder.get("user_id"):
            return "user"
        elif folder.get("company_id"):
            return "company"
        elif folder.get("organization_id"):
            return "organization" 
        else:
            # Global folder - classify as organization for now
            return "organization"
    except Exception as e:
        logger.error(f"Error determining folder type: {str(e)}")
        return "user"  # Default fallback


def build_folder_hierarchy(folders: List[Dict]) -> List[Dict]:
    """Build nested folder structure"""
    try:
        # Create a map of folder_id -> folder for quick lookup
        folder_map = {folder["id"]: folder for folder in folders}
        
        # Find root folders (no parent) and build hierarchy
        root_folders = []
        
        for folder in folders:
            parent_id = folder.get("parent_folder_id")
            
            if not parent_id:
                # This is a root folder
                folder["subfolders"] = get_child_folders(folder["id"], folder_map)
                root_folders.append(folder)
        
        return root_folders
        
    except Exception as e:
        logger.error(f"Error building folder hierarchy: {str(e)}")
        return folders  # Return flat structure as fallback


def get_child_folders(parent_id: int, folder_map: Dict[int, Dict]) -> List[Dict]:
    """Recursively get child folders"""
    try:
        children = []
        
        for folder_id, folder in folder_map.items():
            if folder.get("parent_folder_id") == parent_id:
                folder["subfolders"] = get_child_folders(folder_id, folder_map)
                children.append(folder)
        
        return children
        
    except Exception as e:
        logger.error(f"Error getting child folders: {str(e)}")
        return []


