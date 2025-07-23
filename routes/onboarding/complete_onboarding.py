from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Set
from utils import supabase_helpers
from supabase import create_client, Client
import os
import dotenv
import logging
import random

logger = logging.getLogger(__name__)

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter()

class OnboardingCompletionData(BaseModel):
    job_type: Optional[str] = None
    job_industry: Optional[str] = None
    job_seniority: Optional[str] = None
    job_other_details: Optional[str] = None
    interests: Optional[List[str]] = None
    other_interests: Optional[str] = None
    signup_source: Optional[str] = None
    other_source: Optional[str] = None

class ImprovedFolderRecommendationEngine:
    """Enhanced recommendation engine with prioritized folder assignment"""
    
    def __init__(self):
        # Default folders for users with no information
        self.default_folders = [1,2,3]  # Starter (2) and Startup (1)
        
        # Job type to folder mappings
        self.job_type_mappings = {
            'content_comm_specialists': [4],  # Marketing, Growth Hacker, Writing, Blog Writing, Storytelling, Email
            'analysts_researchers': [27],  # Research, Data Analysis, Academic Research, Science & Math
            'customer_client_facing': [32],  # Client Support, Customer Service, Sales, Communication, Conflict Resolution
            'product_dev_teams': [23],  # Product, Technical Lead's Toolkit, No-code, Cybersecurity
            'hr_training_professionals': [6],  # HR, Formation, Training, Continuing Education, Professional Certification, Pedagogy
            'entrepreneurs_business_owners': [1],  # Startup, Executive Decision Maker, Strategic Decision Maker, Strategy, Decision Making, Leadership
            'sales_marketing': [26],  # Sales, Marketing, Growth Hacker, SEO, LinkedIn
            'finance': [25, 5],  # Finance, Investment, Personal Budget, Savings & Investment, Insurance
            'freelance': [24],  # Freelance, Freelance and Independent Work, Career Change
            'other': [2, 3]  # Starter, Daily, Self Development, Personal Development
        }
        
        # Job industry to folder mappings
        self.job_industry_mappings = {
            'tech_software_dev': [16, 39],  # Technical Lead's Toolkit, No-code, Cybersecurity, Personal Technology, Digital Security
            'marketing_advertising': [4, 17],  # Marketing, Growth Hacker, SEO, LinkedIn, Personal Social Media
            'consulting_professional_services': [11],  # Executive Decision Maker, Strategic Decision Maker, Strategy, Decision Making, Leadership, Negotiation
            'finance_banking': [5, 25],  # Finance, Investment, Personal Budget, Savings & Investment, Insurance
            'healthcare_medical': [18, 97],  # Healthcare Compliance Navigator, Health & Wellness, Meditation, Nutrition, Mental Health, Health Prevention
            'legal_law': [13, 19],  # Law, Legal Research Assistant, Legal Assistant
            'manufacturing_production': [30],  # Manufacturing
            'media_entertainment': [28],  # Media, Video & Editing, Podcast, Movies & Series, Games & Entertainment
            'real_estate': [9],  # Real estate
            'ecommerce_retail': [29],  # E-commerce
            'education_training': [10, 33],  # Formation, Training, Continuing Education, Professional Certification, E-learning, Pedagogy, Science & Math
            'hr_recruitment': [6],  # HR, Find a job, Finding a Job
            'customer_service_support': [32],  # Client Support, Customer Service
            'other': [2, 3]  # Starter, Daily, Self Development, Personal Development
        }
        
        # Job seniority to folder mappings
        self.job_seniority_mappings = {
            'student': [35, 62],  # Student, Homework, Revisions, Language Learning, Academic Guidance, Study Methods, School Presentations, Academic Research, Thesis
            'junior_0_5': [20, 14],  # New Graduate's Professional Accelerator, Find a job, Finding a Job, Self Development, Personal Development
            'mid_5_10': [21, 141],  # Mid-Career Pivot Navigator, Career Change, Leadership, Negotiation, Team Management
            'senior_10_15': [11, 144],  # Executive Decision Maker, Strategic Decision Maker, Strategy, Decision Making, Leadership, Negotiation, Team Management
            'lead_15_plus': [11, 142],  # Executive Decision Maker, Strategic Decision Maker, Strategy, Decision Making, Leadership, Negotiation, Team Management
            'executive': [11, 142],  # Executive Decision Maker, Strategic Decision Maker, Strategy, Decision Making, Leadership, Negotiation, Team Management
            'other': [2]  # Starter, Daily, Self Development, Personal Development
        }
        
        # Interest to folder mappings (1 folder per interest)
        self.interest_mappings = {
            'writing': [47],  # Writing, Creative Writing, Writing a Speech, Blog Writing, Storytelling
            'coding': [16],  # Technical Lead's Toolkit, No-code, Cybersecurity
            'data_analysis': [31],  # Data Analysis, Research
            'research': [27],  # Research, Academic Research, Science & Math
            'creativity': [8, 110],  # Image, Creative Writing, Visual Arts, Graphic Design, Creative Innovation, Creativity in Business
            'learning': [10],  # Formation, Training, Language Learning, Continuing Education, Professional Certification, E-learning, Pedagogy
            'marketing': [4],  # Marketing, Growth Hacker, SEO, LinkedIn
            'email': [22],  # Email Generator
            'summarizing': [27, 31],  # Research, Data Analysis
            'critical_thinking': [11],  # Strategy, Decision Making, Research, Data Analysis
            'customer_support': [32],  # Client Support, Customer Service
            'decision_making': [11],  # Strategy, Decision Making, Executive Decision Maker, Strategic Decision Maker
            'language_learning': [33],  # Language Learning
            'other': [2, 3]  # Starter, Daily, Self Development, Personal Development
        }
    
    def get_prioritized_recommendations(self, job_type: str = None, job_industry: str = None, 
                                     job_seniority: str = None, interests: List[str] = None) -> List[int]:
        """
        Generate recommendations with new prioritization:
        - 1-3 folders from job/industry/seniority profile
        - 1 folder per interest
        """
        profile_folders = set()
        interest_folders = []
        
        # Step 1: Get profile-based folders (job, industry, seniority)
        if job_type and job_type in self.job_type_mappings:
            profile_folders.update(self.job_type_mappings[job_type])
        
        if job_industry and job_industry in self.job_industry_mappings:
            profile_folders.update(self.job_industry_mappings[job_industry])
        
        if job_seniority and job_seniority in self.job_seniority_mappings:
            profile_folders.update(self.job_seniority_mappings[job_seniority])
        
        # If no profile information, use default folders
        if not profile_folders:
            profile_folders.update(self.default_folders)
        
        # Select 1-3 folders from profile, prioritizing by overlap
        profile_folder_list = self._prioritize_profile_folders(
            list(profile_folders), job_type, job_industry, job_seniority
        )
        selected_profile_folders = profile_folder_list[:3]  # Max 3 folders
        
        # Step 2: Get 1 folder per interest (avoiding duplicates with profile folders)
        if interests:
            used_folders = set(selected_profile_folders)
            for interest in interests:
                if interest in self.interest_mappings:
                    # Find the best folder for this interest that's not already selected
                    available_folders = [f for f in self.interest_mappings[interest] if f not in used_folders]
                    if available_folders:
                        # Pick the first available folder for this interest
                        selected_folder = available_folders[0]
                        interest_folders.append(selected_folder)
                        used_folders.add(selected_folder)
        
        # Combine profile and interest folders
        final_recommendations = selected_profile_folders + interest_folders
        
        # Ensure we have at least 1 recommendation
        if not final_recommendations:
            return self.default_folders
        
        # Limit to maximum 5 folders total
        return final_recommendations[:5]
    
    def _prioritize_profile_folders(self, folders: List[int], job_type: str = None, 
                                  job_industry: str = None, job_seniority: str = None) -> List[int]:
        """Prioritize profile folders based on overlap across job dimensions"""
        if not folders:
            return []
        
        folder_scores = {}
        
        for folder_id in folders:
            score = 0
            
            # Score based on how many categories this folder appears in
            if job_type and job_type in self.job_type_mappings:
                if folder_id in self.job_type_mappings[job_type]:
                    score += 3
            
            if job_industry and job_industry in self.job_industry_mappings:
                if folder_id in self.job_industry_mappings[job_industry]:
                    score += 3
            
            if job_seniority and job_seniority in self.job_seniority_mappings:
                if folder_id in self.job_seniority_mappings[job_seniority]:
                    score += 2
            
            folder_scores[folder_id] = score
        
        # Sort by score (descending) and return folder IDs
        sorted_folders = sorted(folder_scores.items(), key=lambda x: x[1], reverse=True)
        return [folder_id for folder_id, score in sorted_folders]

class ImprovedFolderAssignmentService:
    """Service for assigning folders based on improved recommendations"""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.recommendation_engine = ImprovedFolderRecommendationEngine()
    
    async def process_onboarding_completion(self, user_id: str, job_type: str = None, 
                                         job_industry: str = None, job_seniority: str = None,
                                         interests: List[str] = None) -> Dict:
        """Process onboarding completion with improved folder recommendations"""
        try:
            # Get folder recommendations using new prioritization
            recommended_folder_ids = self.recommendation_engine.get_prioritized_recommendations(
                job_type=job_type,
                job_industry=job_industry, 
                job_seniority=job_seniority,
                interests=interests or []
            )
            
            return recommended_folder_ids
            
        except Exception as e:
            logger.error(f"Error in folder assignment for user {user_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "recommended_folder_ids": [],
                "new_folders": []
            }

@router.post("/complete")
async def complete_onboarding(
    request: Request,
    onboarding_data: OnboardingCompletionData,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """
    Complete user onboarding and assign personalized folders using improved recommendation system.
    
    New prioritization:
    - 1-3 folders from job/industry/seniority profile
    - 1 folder per interest
    """
    try:
        
        # Save onboarding data to user metadata
        update_data = {}
        
        # Process job information
        if onboarding_data.job_type:
            if onboarding_data.job_type == 'other' and onboarding_data.job_other_details:
                update_data["job_type"] = f"other:{onboarding_data.job_other_details}"
            else:
                update_data["job_type"] = onboarding_data.job_type
        
        if onboarding_data.job_industry:
            update_data["job_industry"] = onboarding_data.job_industry
            
        if onboarding_data.job_seniority:
            update_data["job_seniority"] = onboarding_data.job_seniority
        
        # Process interests
        interests_to_save = onboarding_data.interests or []
        if onboarding_data.other_interests:
            interests_to_save.append(f"other:{onboarding_data.other_interests}")
        update_data["interests"] = interests_to_save
        
        # Process signup source
        if onboarding_data.signup_source:
            if onboarding_data.signup_source == 'other' and onboarding_data.other_source:
                update_data["signup_source"] = f"other:{onboarding_data.other_source}"
            else:
                update_data["signup_source"] = onboarding_data.signup_source
        
        # Save onboarding data to database
        update_response = supabase.table("users_metadata") \
            .update(update_data) \
            .eq("user_id", user_id) \
            .execute()
        
        if not update_response.data:
            raise HTTPException(status_code=500, detail="Failed to save onboarding data")
        
        # Process folder recommendations with improved system
        folder_service = ImprovedFolderAssignmentService(supabase)
        folder_result = await folder_service.process_onboarding_completion(
            user_id=user_id,
            job_type=onboarding_data.job_type,
            job_industry=onboarding_data.job_industry,
            job_seniority=onboarding_data.job_seniority,
            interests=interests_to_save,
        )
        print("+++++++++++++++++++++++++++++\n")
        print(folder_result)
        # Update users_metadata with pinned_folder_ids
        update_pinned_folders_response = supabase.table("users_metadata") \
            .update({"pinned_folder_ids": folder_result}) \
            .eq("user_id", user_id) \
            .execute()
        
        if not update_pinned_folders_response.data:
            raise HTTPException(status_code=500, detail="Failed to update pinned folder IDs")
        
        
        return {
            "success": True,
            "pinned_folder_ids": folder_result
        }
        
    except Exception as e:
        logger.error(f"Error completing onboarding for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error completing onboarding: {str(e)}")
