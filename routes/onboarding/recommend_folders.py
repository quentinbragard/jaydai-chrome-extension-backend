from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from supabase import create_client, Client
from utils import supabase_helpers
import os
import dotenv

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter()

class FolderRecommendationRequest(BaseModel):
    job_type: Optional[str] = None
    job_industry: Optional[str] = None
    job_seniority: Optional[str] = None
    interests: Optional[List[str]] = None

@router.post("/recommend-folders")
async def recommend_folders(
    request: FolderRecommendationRequest,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """Get folder recommendations based on user profile."""
    try:
        # This is a placeholder for folder recommendation logic
        # You can implement sophisticated recommendation logic here
        
        recommended_folder_ids = []
        
        # Simple recommendation logic based on job type and interests
        if request.job_type == "developer":
            # Recommend programming-related folders
            recommended_folder_ids.extend([1, 2, 3])  # Replace with actual folder IDs
        
        if request.job_industry == "marketing":
            # Recommend marketing-related folders
            recommended_folder_ids.extend([4, 5, 6])  # Replace with actual folder IDs
        
        if request.interests and "writing" in request.interests:
            # Recommend writing-related folders
            recommended_folder_ids.extend([7, 8, 9])  # Replace with actual folder IDs
        
        # Remove duplicates
        recommended_folder_ids = list(set(recommended_folder_ids))
        
        return {
            "success": True,
            "data": {
                "recommended_folder_ids": recommended_folder_ids
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating folder recommendations: {str(e)}") 