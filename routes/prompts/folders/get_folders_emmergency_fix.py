# routes/prompts/folders/get_folders_emergency_fix.py
"""
Emergency performance fix for the folders endpoint
"""
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, Query, Request
from models.common import APIResponse
from utils import supabase_helpers
from .helpers import supabase, router
from utils.middleware.localization import extract_locale_from_request
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

@router.get("/emergency-fix", response_model=APIResponse[Dict])
async def get_folders_emergency_fix(
    request: Request,
    type: Optional[str] = Query(None, description="Folder type filter"),
    withSubfolders: bool = Query(False, description="Include nested subfolders"),
    withTemplates: bool = Query(False, description="Include templates for each folder"),
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[Dict]:
    """
    Emergency performance fix for folders endpoint.
    This replaces multiple queries with optimized batch operations.
    """
    try:
        start_time = time.time()
        locale = extract_locale_from_request(request)
        
        # Step 1: Get user metadata in single query
        user_metadata_response = supabase.table("users_metadata") \
            .select("pinned_folder_ids, organization_ids, company_id") \
            .eq("user_id", user_id) \
            .single() \
            .execute()
        
        user_metadata = user_metadata_response.data or {}
        query_time_1 = (time.time() - start_time) * 1000
        logger.info(f"User metadata query: {query_time_1:.2f}ms")
        
        # Step 2: Get ALL accessible folders in single query using SQL
        step2_start = time.time()
        
        # Build access conditions
        org_ids = user_metadata.get("organization_ids", []) or []
        company_id = user_metadata.get("company_id")
        
        # Use raw SQL for better performance
        access_conditions = [f"user_id = '{user_id}'"]
        
        if company_id:
            access_conditions.append(f"company_id = '{company_id}'")
        
        if org_ids:
            org_list = "', '".join(str(oid) for oid in org_ids)
            access_conditions.append(f"organization_id IN ('{org_list}')")
        
        # Global folders
        access_conditions.append("(user_id IS NULL AND company_id IS NULL AND organization_id IS NULL)")
        
        where_clause = " OR ".join(f"({cond})" for cond in access_conditions)
        
        # Single query for all folders
        folders_query = f"""
        SELECT id, title, description, type, created_at, user_id, organization_id, company_id, parent_folder_id
        FROM prompt_folders 
        WHERE {where_clause}
        ORDER BY created_at DESC
        """
        
        try:
            folders_response = supabase.rpc('execute_raw_sql', {'query': folders_query}).execute()
            all_folders = folders_response.data or []
        except Exception as e:
            # Fallback to multiple queries if raw SQL fails
            logger.warning(f"Raw SQL failed, using fallback: {str(e)}")
            all_folders = await get_folders_fallback(supabase, user_id, user_metadata)
        
        query_time_2 = (time.time() - step2_start) * 1000
        logger.info(f"Folders query: {query_time_2:.2f}ms, found {len(all_folders)} folders")
        
        # Step 3: Process folders by type (in memory, fast)
        step3_start = time.time()
        
        folders_by_type = {"user": [], "company": [], "organization": []}
        
        for folder in all_folders:
            folder_type = determine_folder_type_fast(folder, user_metadata)
            if not type or folder_type == type:
                processed_folder = process_folder_for_response_fast(folder, locale)
                folders_by_type[folder_type].append(processed_folder)
        
        processing_time = (time.time() - step3_start) * 1000
        logger.info(f"Folder processing: {processing_time:.2f}ms")
        
        # Step 4: Get templates if requested (single query)
        if withTemplates:
            step4_start = time.time()
            all_folder_ids = [f["id"] for folders in folders_by_type.values() for f in folders]
            
            if all_folder_ids:
                templates_response = supabase.table("prompt_templates") \
                    .select("id, title, content, description, folder_id, type, usage_count, created_at") \
                    .in_("folder_id", all_folder_ids) \
                    .execute()
                
                templates = templates_response.data or []
                
                # Group templates by folder
                templates_by_folder = {}
                for template in templates:
                    folder_id = template["folder_id"]
                    if folder_id not in templates_by_folder:
                        templates_by_folder[folder_id] = []
                    templates_by_folder[folder_id].append(
                        process_template_for_response_fast(template, locale)
                    )
                
                # Add templates to folders
                for folder_type in folders_by_type:
                    for folder in folders_by_type[folder_type]:
                        folder["templates"] = templates_by_folder.get(folder["id"], [])
            
            template_time = (time.time() - step4_start) * 1000
            logger.info(f"Template processing: {template_time:.2f}ms")
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Total optimized folders query: {total_time:.2f}ms")
        
        result = {
            "folders": folders_by_type,
            "performance": {
                "total_time_ms": round(total_time, 2),
                "query_breakdown": {
                    "user_metadata": round(query_time_1, 2),
                    "folders": round(query_time_2, 2),
                    "processing": round(processing_time, 2)
                }
            }
        }
        
        return APIResponse(success=True, data=result)
        
    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        logger.error(f"Emergency fix failed after {total_time:.2f}ms: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving folders: {str(e)}")

def determine_folder_type_fast(folder: Dict[str, Any], user_metadata: Dict[str, Any]) -> str:
    """Fast folder type determination"""
    if folder.get("user_id"):
        return "user"
    elif folder.get("company_id"):
        return "company"
    else:
        return "organization"

def process_folder_for_response_fast(folder_data: dict, locale: str = "en") -> dict:
    """Fast folder processing without heavy utilities"""
    title = folder_data.get("title", {})
    if isinstance(title, dict):
        title_text = title.get(locale) or title.get("en") or ""
    else:
        title_text = str(title or "")
    
    description = folder_data.get("description", {})
    if isinstance(description, dict):
        description_text = description.get(locale) or description.get("en") or ""
    else:
        description_text = str(description or "")
    
    return {
        "id": folder_data.get("id"),
        "title": title_text,
        "description": description_text,
        "type": folder_data.get("type"),
        "created_at": folder_data.get("created_at"),
        "user_id": folder_data.get("user_id"),
        "organization_id": folder_data.get("organization_id"),
        "company_id": folder_data.get("company_id"),
        "parent_folder_id": folder_data.get("parent_folder_id"),
    }

def process_template_for_response_fast(template_data: dict, locale: str = "en") -> dict:
    """Fast template processing"""
    title = template_data.get("title", {})
    if isinstance(title, dict):
        title_text = title.get(locale) or title.get("en") or ""
    else:
        title_text = str(title or "")
    
    return {
        "id": template_data.get("id"),
        "title": title_text,
        "folder_id": template_data.get("folder_id"),
        "type": template_data.get("type"),
        "usage_count": template_data.get("usage_count", 0),
        "created_at": template_data.get("created_at")
    }

async def get_folders_fallback(supabase, user_id: str, user_metadata: dict):
    """Fallback method using multiple queries if SQL fails"""
    folders = []
    
    # User folders
    user_response = supabase.table("prompt_folders").select("*").eq("user_id", user_id).execute()
    folders.extend(user_response.data or [])
    
    # Company folders
    company_id = user_metadata.get("company_id")
    if company_id:
        company_response = supabase.table("prompt_folders").select("*").eq("company_id", company_id).execute()
        folders.extend(company_response.data or [])
    
    # Organization folders
    org_ids = user_metadata.get("organization_ids", []) or []
    for org_id in org_ids:
        org_response = supabase.table("prompt_folders").select("*").eq("organization_id", org_id).execute()
        folders.extend(org_response.data or [])
    
    # Global folders
    global_response = supabase.table("prompt_folders").select("*") \
        .is_("user_id", "null") \
        .is_("company_id", "null") \
        .is_("organization_id", "null") \
        .execute()
    folders.extend(global_response.data or [])
    
    return folders