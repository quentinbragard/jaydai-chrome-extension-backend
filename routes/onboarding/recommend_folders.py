from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Set
from supabase import create_client, Client
from utils import supabase_helpers
import os
import dotenv
import random

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter()

class FolderRecommendationRequest(BaseModel):
    job_type: Optional[str] = None
    job_industry: Optional[str] = None
    job_seniority: Optional[str] = None
    interests: Optional[List[str]] = None

class FolderRecommendationEngine:
    """Advanced recommendation engine for folder suggestions"""
    
    def __init__(self):
        # Default folders for users with no information
        self.default_folders = [2, 1]  # Starter (2) and Startup (1)
        
        # Job type to folder mappings
        self.job_type_mappings = {
            'content_comm_specialists': [4, 17, 47, 119, 120, 22, 55],  # Marketing, Growth Hacker, Writing, Blog Writing, Storytelling, Email
            'analysts_researchers': [27, 31, 68, 76],  # Research, Data Analysis, Academic Research, Science & Math
            'customer_client_facing': [32, 148, 26, 128, 129],  # Client Support, Customer Service, Sales, Communication, Conflict Resolution
            'product_dev_teams': [23, 49, 16, 39, 40],  # Product, Technical Lead's Toolkit, No-code, Cybersecurity
            'hr_training_professionals': [6, 10, 59, 72, 73, 75],  # HR, Formation, Training, Continuing Education, Professional Certification, Pedagogy
            'entrepreneurs_business_owners': [1, 15, 56, 11, 60, 142],  # Startup, Executive Decision Maker, Strategic Decision Maker, Strategy, Decision Making, Leadership
            'sales_marketing': [26, 4, 17, 34, 54, 12],  # Sales, Marketing, Growth Hacker, SEO, LinkedIn
            'finance': [25, 5, 133, 134, 135],  # Finance, Investment, Personal Budget, Savings & Investment, Insurance
            'freelance': [24, 140, 141],  # Freelance, Freelance and Independent Work, Career Change
            'other': [2, 3, 7, 58]  # Starter, Daily, Self Development, Personal Development
        }
        
        # Job industry to folder mappings
        self.job_industry_mappings = {
            'tech_software_dev': [16, 39, 40, 90, 137],  # Technical Lead's Toolkit, No-code, Cybersecurity, Personal Technology, Digital Security
            'marketing_advertising': [4, 17, 34, 54, 12, 136],  # Marketing, Growth Hacker, SEO, LinkedIn, Personal Social Media
            'consulting_professional_services': [15, 56, 11, 60, 142, 143],  # Executive Decision Maker, Strategic Decision Maker, Strategy, Decision Making, Leadership, Negotiation
            'finance_banking': [25, 5, 133, 134, 135],  # Finance, Investment, Personal Budget, Savings & Investment, Insurance
            'healthcare_medical': [18, 97, 98, 99, 103, 105],  # Healthcare Compliance Navigator, Health & Wellness, Meditation, Nutrition, Mental Health, Health Prevention
            'legal_law': [13, 19, 51],  # Law, Legal Research Assistant, Legal Assistant
            'manufacturing_production': [30],  # Manufacturing
            'media_entertainment': [28, 52, 117, 118, 83, 84],  # Media, Video & Editing, Podcast, Movies & Series, Games & Entertainment
            'real_estate': [9],  # Real estate
            'ecommerce_retail': [29],  # E-commerce
            'education_training': [10, 59, 72, 73, 74, 75, 76],  # Formation, Training, Continuing Education, Professional Certification, E-learning, Pedagogy, Science & Math
            'hr_recruitment': [6, 14, 61],  # HR, Find a job, Finding a Job
            'customer_service_support': [32, 148],  # Client Support, Customer Service
            'other': [2, 3, 7, 58]  # Starter, Daily, Self Development, Personal Development
        }
        
        # Job seniority to folder mappings
        self.job_seniority_mappings = {
            'student': [35, 62, 63, 64, 65, 66, 67, 68, 69],  # Student, Homework, Revisions, Language Learning, Academic Guidance, Study Methods, School Presentations, Academic Research, Thesis
            'junior_0_5': [20, 14, 61, 7, 58],  # New Graduate's Professional Accelerator, Find a job, Finding a Job, Self Development, Personal Development
            'mid_5_10': [21, 141, 142, 143, 144],  # Mid-Career Pivot Navigator, Career Change, Leadership, Negotiation, Team Management
            'senior_10_15': [15, 56, 11, 60, 142, 143, 144],  # Executive Decision Maker, Strategic Decision Maker, Strategy, Decision Making, Leadership, Negotiation, Team Management
            'lead_15_plus': [15, 56, 11, 60, 142, 143, 144],  # Executive Decision Maker, Strategic Decision Maker, Strategy, Decision Making, Leadership, Negotiation, Team Management
            'executive': [15, 56, 11, 60, 142, 143, 144],  # Executive Decision Maker, Strategic Decision Maker, Strategy, Decision Making, Leadership, Negotiation, Team Management
            'other': [2, 3, 7, 58]  # Starter, Daily, Self Development, Personal Development
        }
        
        # Interest to folder mappings
        self.interest_mappings = {
            'writing': [47, 110, 109, 119, 120],  # Writing, Creative Writing, Writing a Speech, Blog Writing, Storytelling
            'coding': [16, 39, 40],  # Technical Lead's Toolkit, No-code, Cybersecurity
            'data_analysis': [31, 27],  # Data Analysis, Research
            'research': [27, 68, 76],  # Research, Academic Research, Science & Math
            'creativity': [8, 50, 110, 113, 116, 121, 123],  # Image, Creative Writing, Visual Arts, Graphic Design, Creative Innovation, Creativity in Business
            'learning': [10, 59, 64, 72, 73, 74, 75],  # Formation, Training, Language Learning, Continuing Education, Professional Certification, E-learning, Pedagogy
            'marketing': [4, 17, 34, 54, 12],  # Marketing, Growth Hacker, SEO, LinkedIn
            'email': [22, 55],  # Email Generator
            'summarizing': [27, 31],  # Research, Data Analysis
            'critical_thinking': [11, 60, 27, 31],  # Strategy, Decision Making, Research, Data Analysis
            'customer_support': [32, 148],  # Client Support, Customer Service
            'decision_making': [11, 60, 15, 56],  # Strategy, Decision Making, Executive Decision Maker, Strategic Decision Maker
            'language_learning': [33, 64],  # Language Learning
            'other': [2, 3, 7, 58]  # Starter, Daily, Self Development, Personal Development
        }
    
    def get_recommendations(self, request: FolderRecommendationRequest) -> List[int]:
        """Generate folder recommendations based on user profile"""
        recommended_folders: Set[int] = set()
        
        # If no information provided, return default folders
        if not any([request.job_type, request.job_industry, request.job_seniority, request.interests]):
            return self.default_folders
        
        # Add recommendations based on job type
        if request.job_type and request.job_type in self.job_type_mappings:
            recommended_folders.update(self.job_type_mappings[request.job_type])
        
        # Add recommendations based on job industry
        if request.job_industry and request.job_industry in self.job_industry_mappings:
            recommended_folders.update(self.job_industry_mappings[request.job_industry])
        
        # Add recommendations based on job seniority
        if request.job_seniority and request.job_seniority in self.job_seniority_mappings:
            recommended_folders.update(self.job_seniority_mappings[request.job_seniority])
        
        # Add recommendations based on interests
        if request.interests:
            for interest in request.interests:
                if interest in self.interest_mappings:
                    recommended_folders.update(self.interest_mappings[interest])
        
        # Convert to list and ensure we have recommendations
        folder_list = list(recommended_folders)
        
        # If still no recommendations, use default
        if not folder_list:
            return self.default_folders
        
        # Prioritize certain folders based on combinations
        prioritized_folders = self._prioritize_folders(folder_list, request)
        
        # Limit to 1-5 folders
        if len(prioritized_folders) > 5:
            # Keep most relevant folders, ensuring variety
            final_folders = self._select_diverse_folders(prioritized_folders, request)
        else:
            final_folders = prioritized_folders
        
        # Ensure at least 1 folder
        if not final_folders:
            return self.default_folders
        
        # Ensure maximum 5 folders
        return final_folders[:5]
    
    def _prioritize_folders(self, folders: List[int], request: FolderRecommendationRequest) -> List[int]:
        """Prioritize folders based on user profile strength"""
        folder_scores = {}
        
        for folder_id in folders:
            score = 0
            
            # Score based on job type match
            if request.job_type and request.job_type in self.job_type_mappings:
                if folder_id in self.job_type_mappings[request.job_type]:
                    score += 3
            
            # Score based on industry match
            if request.job_industry and request.job_industry in self.job_industry_mappings:
                if folder_id in self.job_industry_mappings[request.job_industry]:
                    score += 3
            
            # Score based on seniority match
            if request.job_seniority and request.job_seniority in self.job_seniority_mappings:
                if folder_id in self.job_seniority_mappings[request.job_seniority]:
                    score += 2
            
            # Score based on interests match
            if request.interests:
                for interest in request.interests:
                    if interest in self.interest_mappings and folder_id in self.interest_mappings[interest]:
                        score += 1
            
            folder_scores[folder_id] = score
        
        # Sort by score (descending) and return folder IDs
        sorted_folders = sorted(folder_scores.items(), key=lambda x: x[1], reverse=True)
        return [folder_id for folder_id, score in sorted_folders]
    
    def _select_diverse_folders(self, folders: List[int], request: FolderRecommendationRequest) -> List[int]:
        """Select diverse folders to avoid too much overlap"""
        selected = []
        categories_used = set()
        
        # Define folder categories for diversity
        folder_categories = {
            # Core professional folders
            'professional': [2, 1, 3, 15, 56, 11, 60],
            'technical': [16, 39, 40, 90, 137],
            'marketing': [4, 17, 34, 54, 12],
            'communication': [22, 55, 47, 119, 120],
            'development': [7, 58, 20, 21],
            'specialized': [25, 5, 6, 10, 13, 19, 18, 9, 29, 30, 28]
        }
        
        # Reverse mapping for quick lookup
        folder_to_category = {}
        for category, folder_list in folder_categories.items():
            for folder_id in folder_list:
                folder_to_category[folder_id] = category
        
        # Select folders ensuring diversity
        for folder_id in folders:
            if len(selected) >= 5:
                break
                
            category = folder_to_category.get(folder_id, 'other')
            
            # Always include high-priority folders or if category not used
            if len(selected) < 2 or category not in categories_used or len(categories_used) >= 4:
                selected.append(folder_id)
                categories_used.add(category)
        
        # If we don't have enough, add more from top folders
        remaining_folders = [f for f in folders if f not in selected]
        while len(selected) < min(5, len(folders)) and remaining_folders:
            selected.append(remaining_folders.pop(0))
        
        return selected

# Initialize the recommendation engine
recommendation_engine = FolderRecommendationEngine()

@router.post("/recommend-folders")
async def recommend_folders(
    request: FolderRecommendationRequest,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token),
):
    """Get folder recommendations based on user profile."""
    try:
        # Get recommendations using the advanced engine
        recommended_folder_ids = recommendation_engine.get_recommendations(request)
        
        # Log the recommendation for analytics (optional)
        recommendation_context = {
            "user_id": user_id,
            "job_type": request.job_type,
            "job_industry": request.job_industry,
            "job_seniority": request.job_seniority,
            "interests": request.interests,
            "recommended_folders": recommended_folder_ids
        }
        
        return {
            "success": True,
            "data": {
                "recommended_folder_ids": recommended_folder_ids,
                "recommendation_count": len(recommended_folder_ids),
                "context": recommendation_context
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating folder recommendations: {str(e)}")