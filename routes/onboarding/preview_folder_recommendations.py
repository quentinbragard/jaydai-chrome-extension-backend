# routes/onboarding/preview_recommendations.py

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
from utils import supabase_helpers
from utils.onboarding.folder_assignment_service import FolderAssignmentService
import dotenv
import logging
from utils.middleware.localization import extract_locale_from_request
from supabase import create_client, Client
import os

logger = logging.getLogger(__name__)

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter()

class FolderRecommendationRequest(BaseModel):
    job_type: Optional[str] = None
    job_industry: Optional[str] = None
    job_seniority: Optional[str] = None
    interests: Optional[List[str]] = None

@router.post("/preview-folder-recommendations")
async def preview_folder_recommendations(
    request: Request,
    recommendation_request: FolderRecommendationRequest,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """
    Preview folder recommendations based on partial onboarding data.
    Useful for showing users what folders they'll get as they fill out the form.
    """
    try:
        # Extract locale from request
        locale = extract_locale_from_request(request)
        
        folder_service = FolderAssignmentService(supabase)
        preview_result = await folder_service.get_folder_recommendations_preview(
            job_type=recommendation_request.job_type,
            job_industry=recommendation_request.job_industry,
            job_seniority=recommendation_request.job_seniority,
            interests=recommendation_request.interests,
            locale=locale  # Pass locale for proper localization
        )
        
        return {
            "success": True,
            "preview": preview_result,
            "message": f"Found {preview_result.get('total_count', 0)} recommended folders"
        }
        
    except Exception as e:
        logger.error(f"Error generating folder recommendations preview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating preview: {str(e)}")
