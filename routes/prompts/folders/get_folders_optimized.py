# routes/prompts/folders/get_folders_optimized.py
"""
Optimized version of get_folders with caching and batch operations
"""
from typing import List, Optional, Dict, Any
from fastapi import Depends, HTTPException, Query, Request
from models.common import APIResponse
from utils import supabase_helpers
from .helpers import supabase, router
from utils.prompts import process_folder_for_response, process_template_for_response
from utils.access_control import get_user_metadata
from utils.middleware.localization import extract_locale_from_request
from utils.cache.redis_cache import cached, CacheInvalidator
from utils.database.query_optimizer import get_user_accessible_items_batch
import asyncio
import logging

logger = logging.getLogger(__name__)

@router.get("/optimized", response_model=APIResponse[Dict])
@cached(ttl=300, key_prefix="folders")  # Cache for 5 minutes
async def get_folders_optimized(
    request: Request,
    type: Optional[str] = Query(None, description="Folder type filter"),
    withSubfolders: bool = Query(False, description="Include nested subfolders"),
    withTemplates: bool = Query(False, description="Include templates for each folder"),
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[Dict]:
    """
    Optimized version of get_folders with caching and batch operations.
    """
    try:
        locale = extract_locale_from_request(request)
        
        # Use batch operation to get all data in parallel
        start_time = time.time()
        
        # Get user metadata and all accessible folders in parallel
        user_metadata_task = asyncio.create_task(
            asyncio.to_thread(get_user_metadata, supabase, user_id)
        )
        
        folders_task = asyncio.create_task(
            get_user_accessible_items_batch(supabase, user_id, "folder")
        )
        
        # Execute in parallel
        user_metadata, all_folders = await asyncio.gather(
            user_metadata_task, folders_task
        )
        
        logger.info(f"Batch data fetch took {(time.time() - start_time) * 1000:.2f}ms")
        
        # Filter by type if specified
        if type and type in ["user", "company", "organization"]:
            folder_types = [type]
        else:
            folder_types = ["user", "company", "organization"]
        
        # Process folders by type
        result = {"folders": {}}
        
        for folder_type in folder_types:
            # Filter folders by type
            type_folders = [
                f for f in all_folders 
                if determine_folder_type_fast(f, user_metadata) == folder_type
            ]
            
            # Process folders for response
            processed_folders = [
                process_folder_for_response(folder, locale) 
                for folder in type_folders
            ]
            
            # Get templates if requested
            if withTemplates and processed_folders:
                folder_ids = [f["id"] for f in processed_folders]
                templates = await get_templates_batch_optimized(folder_ids, locale)
                
                # Add templates to folders
                templates_by_folder = {}
                for template in templates:
                    folder_id = template.get("folder_id")
                    if folder_id not in templates_by_folder:
                        templates_by_folder[folder_id] = []
                    templates_by_folder[folder_id].append(template)
                
                for folder in processed_folders:
                    folder["templates"] = templates_by_folder.get(folder["id"], [])
            
            result["folders"][folder_type] = processed_folders
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Total get_folders_optimized took {total_time:.2f}ms")
        
        return APIResponse(success=True, data=result)
        
    except Exception as e:
        logger.error(f"Error in get_folders_optimized: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error retrieving folders: {str(e)}")

def determine_folder_type_fast(folder: Dict[str, Any], user_metadata: Dict[str, Any]) -> str:
    """Fast folder type determination using cached user metadata"""
    if folder.get("user_id"):
        return "user"
    elif folder.get("company_id"):
        return "company"
    else:
        return "organization"

@cached(ttl=300, key_prefix="templates_batch")
async def get_templates_batch_optimized(folder_ids: List[int], locale: str = "en") -> List[Dict]:
    """Optimized batch template fetching with caching"""
    if not folder_ids:
        return []
    
    # Single query to get all templates
    templates_response = await asyncio.to_thread(
        lambda: supabase.table("prompt_templates")
        .select("*")
        .in_("folder_id", folder_ids)
        .execute()
    )
    
    # Process templates for response
    processed_templates = []
    for template in templates_response.data or []:
        processed_template = process_template_for_response(template, locale)
        processed_templates.append(processed_template)
    
    return processed_templates
