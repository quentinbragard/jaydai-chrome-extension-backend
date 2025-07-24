# routes/prompts/search_fixed.py - FIXED VERSION FOR JSONB FIELDS
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from models.common import APIResponse
from utils import supabase_helpers
from utils.middleware.localization import extract_locale_from_request
from utils.access_control import get_user_metadata, apply_access_conditions
from utils.prompts import process_template_for_response, process_folder_for_response
import logging

logger = logging.getLogger(__name__)

# Create a separate router for search
router = APIRouter(tags=["Search"])

@router.get("/")
async def search_templates_and_folders_fixed(
    request: Request,
    q: str = Query(..., description="Search query", min_length=2),
    page: int = Query(1, description="Page number", ge=1),
    page_size: int = Query(20, description="Results per page", ge=1, le=100),
    type_filter: Optional[str] = Query(None, description="Filter by type: template, folder, or both"),
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[Dict[str, Any]]:
    """
    Fixed search implementation that properly handles JSONB fields.
    """
    try:
        from .templates.helpers import supabase  # Import from parent helpers
        
        locale = extract_locale_from_request(request)
        search_term = q.strip()
        
        # Calculate pagination
        offset = (page - 1) * page_size
        
        results = {
            "query": search_term,
            "templates": [],
            "folders": [],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_templates": 0,
                "total_folders": 0,
                "has_more_templates": False,
                "has_more_folders": False
            }
        }
        
        # Search templates if requested
        if not type_filter or type_filter in ['template', 'both']:
            template_results = await search_templates_jsonb(
                supabase, user_id, search_term, locale, page_size, offset
            )
            results["templates"] = template_results["items"]
            results["pagination"]["total_templates"] = template_results["total"]
            results["pagination"]["has_more_templates"] = (offset + page_size) < template_results["total"]
        
        # Search folders if requested
        if not type_filter or type_filter in ['folder', 'both']:
            folder_results = await search_folders_jsonb(
                supabase, user_id, search_term, locale, page_size, offset
            )
            results["folders"] = folder_results["items"]
            results["pagination"]["total_folders"] = folder_results["total"]
            results["pagination"]["has_more_folders"] = (offset + page_size) < folder_results["total"]
        
        return APIResponse(
            success=True,
            data=results,
            message=f"Found {results['pagination']['total_templates']} templates and {results['pagination']['total_folders']} folders"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


async def search_templates_jsonb(
    supabase,
    user_id: str,
    search_term: str,
    locale: str,
    page_size: int,
    offset: int
) -> Dict[str, Any]:
    """Search templates using proper JSONB text extraction and casting."""
    
    try:
        # Get user metadata for access control
        user_metadata = get_user_metadata(supabase, user_id)
        
        # Build access conditions using query builder
        access_conditions = [f"user_id.eq.{user_id}"]
        if user_metadata.get("company_id"):
            access_conditions.append(f"company_id.eq.{user_metadata['company_id']}")
        for oid in user_metadata.get("organization_ids", []) or []:
            access_conditions.append(f"organization_id.eq.{oid}")
        access_conditions.append("and(user_id.is.null,company_id.is.null,organization_id.is.null)")

        search_like = f"%{search_term}%"
        search_filters = [
            f"title->>'{locale}'.ilike.{search_like}",
            f"title->>'en'.ilike.{search_like}",
            f"content->>'{locale}'.ilike.{search_like}",
            f"content->>'en'.ilike.{search_like}",
            f"description->>'{locale}'.ilike.{search_like}",
            f"description->>'en'.ilike.{search_like}",
        ]

        # Execute count query using parameterized filters
        count_query = supabase.table("prompt_templates").select("id", count="exact")
        count_query = count_query.or_(",".join(access_conditions))
        count_query = count_query.or_(",".join(search_filters))
        count_response = count_query.execute()
        total = getattr(count_response, "count", None)
        if total is None:
            total = len(count_response.data or [])

        # Execute search query using parameterized filters
        search_query = supabase.table("prompt_templates").select("*")
        search_query = search_query.or_(",".join(access_conditions))
        search_query = search_query.or_(",".join(search_filters))
        search_query = search_query.order("created_at", desc=True)
        search_query = search_query.range(offset, offset + page_size - 1)
        search_response = search_query.execute()
        
        # Process results
        templates = []
        for template_data in (search_response.data or []):
            processed_template = process_template_for_response(template_data, locale)
            
            # Add simple relevance scoring
            relevance_score = calculate_jsonb_relevance(template_data, search_term.lower(), locale)
            processed_template['search_rank'] = relevance_score
            templates.append(processed_template)
        
        # Sort by relevance
        templates.sort(key=lambda x: x.get('search_rank', 0), reverse=True)
        
        return {
            "items": templates,
            "total": total
        }
        
    except Exception as e:
        logger.error("JSONB template search failed: %s", str(e))
        # Fallback to client-side filtering
        return await fallback_client_search_templates(supabase, user_id, search_term, locale, page_size, offset)


async def search_folders_jsonb(
    supabase,
    user_id: str,
    search_term: str,
    locale: str,
    page_size: int,
    offset: int
) -> Dict[str, Any]:
    """Search folders using proper JSONB text extraction and casting."""
    
    try:
        # Get user metadata for access control
        user_metadata = get_user_metadata(supabase, user_id)
        
        # Build access conditions using query builder
        access_conditions = [f"user_id.eq.{user_id}"]
        if user_metadata.get("company_id"):
            access_conditions.append(f"company_id.eq.{user_metadata['company_id']}")
        for oid in user_metadata.get("organization_ids", []) or []:
            access_conditions.append(f"organization_id.eq.{oid}")
        access_conditions.append("and(user_id.is.null,company_id.is.null,organization_id.is.null)")

        search_like = f"%{search_term}%"
        search_filters = [
            f"title->>'{locale}'.ilike.{search_like}",
            f"title->>'en'.ilike.{search_like}",
            f"description->>'{locale}'.ilike.{search_like}",
            f"description->>'en'.ilike.{search_like}",
        ]

        # Execute count query using parameterized filters
        count_query = supabase.table("prompt_folders").select("id", count="exact")
        count_query = count_query.or_(",".join(access_conditions))
        count_query = count_query.or_(",".join(search_filters))
        count_response = count_query.execute()
        total = getattr(count_response, "count", None)
        if total is None:
            total = len(count_response.data or [])

        # Execute search query using parameterized filters
        search_query = supabase.table("prompt_folders").select("*")
        search_query = search_query.or_(",".join(access_conditions))
        search_query = search_query.or_(",".join(search_filters))
        search_query = search_query.order("created_at", desc=True)
        search_query = search_query.range(offset, offset + page_size - 1)
        search_response = search_query.execute()
        
        # Process results
        folders = []
        for folder_data in (search_response.data or []):
            processed_folder = process_folder_for_response(folder_data, locale)
            
            # Add simple relevance scoring
            relevance_score = calculate_jsonb_relevance(folder_data, search_term.lower(), locale)
            processed_folder['search_rank'] = relevance_score
            folders.append(processed_folder)
        
        # Sort by relevance
        folders.sort(key=lambda x: x.get('search_rank', 0), reverse=True)
        
        return {
            "items": folders,
            "total": total
        }
        
    except Exception as e:
        logger.error("JSONB folder search failed: %s", str(e))
        # Fallback to client-side filtering
        return await fallback_client_search_folders(supabase, user_id, search_term, locale, page_size, offset)


def calculate_jsonb_relevance(item_data: Dict[str, Any], search_term: str, locale: str) -> float:
    """Calculate relevance score for JSONB search results."""
    score = 0.0
    
    # Extract text from JSONB fields
    title_data = item_data.get('title', {})
    if isinstance(title_data, dict):
        title = (title_data.get(locale) or title_data.get('en') or '').lower()
    else:
        title = str(title_data).lower()
    
    description_data = item_data.get('description', {})
    if isinstance(description_data, dict):
        description = (description_data.get(locale) or description_data.get('en') or '').lower()
    else:
        description = str(description_data).lower()
    
    content_data = item_data.get('content', {})
    if isinstance(content_data, dict):
        content = (content_data.get(locale) or content_data.get('en') or '').lower()
    else:
        content = str(content_data).lower()
    
    # Score based on matches
    if search_term in title:
        if title.startswith(search_term):
            score += 10  # Title starts with search term
        else:
            score += 5   # Title contains search term
    
    if search_term in description:
        score += 3
    
    if search_term in content:
        score += 1
    
    # Exact match bonus
    if title == search_term:
        score += 20
    
    # Shorter titles are more specific
    if title:
        score += max(0, 5 - len(title.split()) * 0.5)
    
    return score


async def fallback_client_search_templates(
    supabase, user_id: str, search_term: str, locale: str, page_size: int, offset: int
) -> Dict[str, Any]:
    """Fallback: fetch all accessible templates and filter client-side."""
    
    try:
        logger.info("Using fallback client-side template search")
        
        # Get all accessible templates
        query = supabase.table("prompt_templates").select("*")
        query = apply_access_conditions(query, supabase, user_id)
        response = query.execute()
        
        all_templates = response.data or []
        
        # Filter client-side
        matching_templates = []
        for template in all_templates:
            if template_matches_search(template, search_term, locale):
                processed = process_template_for_response(template, locale)
                processed['search_rank'] = calculate_jsonb_relevance(template, search_term.lower(), locale)
                matching_templates.append(processed)
        
        # Sort by relevance
        matching_templates.sort(key=lambda x: x.get('search_rank', 0), reverse=True)
        
        # Apply pagination
        total = len(matching_templates)
        paginated = matching_templates[offset:offset + page_size]
        
        return {
            "items": paginated,
            "total": total
        }
        
    except Exception as e:
        logger.error("Fallback template search failed: %s", str(e))
        return {"items": [], "total": 0}


async def fallback_client_search_folders(
    supabase, user_id: str, search_term: str, locale: str, page_size: int, offset: int
) -> Dict[str, Any]:
    """Fallback: fetch all accessible folders and filter client-side."""
    
    try:
        logger.info("Using fallback client-side folder search")
        
        # Get all accessible folders
        query = supabase.table("prompt_folders").select("*")
        query = apply_access_conditions(query, supabase, user_id)
        response = query.execute()
        
        all_folders = response.data or []
        
        # Filter client-side
        matching_folders = []
        for folder in all_folders:
            if folder_matches_search(folder, search_term, locale):
                processed = process_folder_for_response(folder, locale)
                processed['search_rank'] = calculate_jsonb_relevance(folder, search_term.lower(), locale)
                matching_folders.append(processed)
        
        # Sort by relevance
        matching_folders.sort(key=lambda x: x.get('search_rank', 0), reverse=True)
        
        # Apply pagination
        total = len(matching_folders)
        paginated = matching_folders[offset:offset + page_size]
        
        return {
            "items": paginated,
            "total": total
        }
        
    except Exception as e:
        logger.error("Fallback folder search failed: %s", str(e))
        return {"items": [], "total": 0}


def template_matches_search(template: Dict, search_term: str, locale: str) -> bool:
    """Check if a template matches the search term."""
    search_lower = search_term.lower()
    
    # Check title
    title = template.get('title', {})
    if isinstance(title, dict):
        title_text = (title.get(locale) or title.get('en') or '').lower()
    else:
        title_text = str(title).lower()
    
    if search_lower in title_text:
        return True
    
    # Check content
    content = template.get('content', {})
    if isinstance(content, dict):
        content_text = (content.get(locale) or content.get('en') or '').lower()
    else:
        content_text = str(content).lower()
    
    if search_lower in content_text:
        return True
    
    # Check description
    description = template.get('description', {})
    if isinstance(description, dict):
        description_text = (description.get(locale) or description.get('en') or '').lower()
    else:
        description_text = str(description).lower()
    
    if search_lower in description_text:
        return True
    
    return False


def folder_matches_search(folder: Dict, search_term: str, locale: str) -> bool:
    """Check if a folder matches the search term."""
    search_lower = search_term.lower()
    
    # Check title
    title = folder.get('title', {})
    if isinstance(title, dict):
        title_text = (title.get(locale) or title.get('en') or '').lower()
    else:
        title_text = str(title).lower()
    
    if search_lower in title_text:
        return True
    
    # Check description
    description = folder.get('description', {})
    if isinstance(description, dict):
        description_text = (description.get(locale) or description.get('en') or '').lower()
    else:
        description_text = str(description).lower()
    
    if search_lower in description_text:
        return True
    
    return False


# Simple suggestions endpoint that works with any setup
@router.get("/suggestions")
async def get_search_suggestions_fixed(
    request: Request,
    q: str = Query(..., description="Partial search query", min_length=1),
    limit: int = Query(5, description="Number of suggestions", ge=1, le=10),
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
) -> APIResponse[List[str]]:
    """Get search suggestions - works with JSONB fields."""
    
    try:
        from .templates.helpers import supabase
        
        locale = extract_locale_from_request(request)
        suggestions = set()
        
        # Get a sample of templates and folders to extract suggestions from
        try:
            # Get templates
            templates_query = supabase.table("prompt_templates").select("title").limit(100)
            templates_query = apply_access_conditions(templates_query, supabase, user_id)
            templates_response = templates_query.execute()
            
            for template in (templates_response.data or []):
                title_data = template.get("title", {})
                if isinstance(title_data, dict):
                    title = title_data.get(locale) or title_data.get('en') or ''
                else:
                    title = str(title_data)
                
                if title and q.lower() in title.lower():
                    suggestions.add(title.strip())
        
        except Exception as e:
            logger.error("Template suggestions error: %s", str(e))
        
        try:
            # Get folders
            folders_query = supabase.table("prompt_folders").select("title").limit(100)
            folders_query = apply_access_conditions(folders_query, supabase, user_id)
            folders_response = folders_query.execute()
            
            for folder in (folders_response.data or []):
                title_data = folder.get("title", {})
                if isinstance(title_data, dict):
                    title = title_data.get(locale) or title_data.get('en') or ''
                else:
                    title = str(title_data)
                
                if title and q.lower() in title.lower():
                    suggestions.add(title.strip())
        
        except Exception as e:
            logger.error("Folder suggestions error: %s", str(e))
        
        # Sort and limit suggestions
        suggestion_list = list(suggestions)
        suggestion_list.sort(key=lambda x: (
            not x.lower().startswith(q.lower()),
            len(x),
            x.lower()
        ))
        
        return APIResponse(
            success=True,
            data=suggestion_list[:limit]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suggestions error: {str(e)}")


# Export the router
__all__ = ["router"]