from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
import dotenv
import os
from typing import List, Optional
from enum import Enum
from . import folders, templates

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

# Create a parent router for all prompts-related endpoints
router = APIRouter(prefix="/prompts", tags=["Prompts"])

# Include sub-routers
router.include_router(folders.router, prefix="/folders", tags=["Folders"])
router.include_router(templates.router, prefix="/templates", tags=["Templates"])

class Locale(str, Enum):
    fr = "fr"
    en = "en"
    
class PromptType(str, Enum):
    official = "official"
    user = "user"
    organization = "organization"


class PromptTemplateBase(BaseModel):
    id: int
    created_at: str
    type: PromptType
    folder_id: int
    tags: List[str]
    title: str
    content: str
    locale: Locale

class PromptTemplateCreate(PromptTemplateBase):
    pass

class PromptTemplateUpdate(PromptTemplateBase):
    pass


class PromptTemplatesFolder(BaseModel):
    id: int
    created_at: str
    type: str
    tags: List[str]
    path: str
    prompt_templates: Optional[List[PromptTemplateBase]] = None
    


@router.post("/template")
async def create_template(
    template_data: PromptTemplateCreate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Create a new template"""
    try:
        # Add user_id to the template data
        template_insert_data = template_data.dict()
        template_insert_data["user_id"] = user_id
        
        # Insert into database
        response = supabase.table("prompt_templates").insert(template_insert_data).execute()
        
        return {"success": True, "template": response.data[0] if response.data else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating template: {str(e)}")

@router.put("/template/{template_id}")
async def update_template(
    template_id: int,
    template_data: PromptTemplateUpdate,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Update an existing template"""
    try:
        # Check if template exists and belongs to the user
        template_check = supabase.table("prompt_templates").select("*") \
            .eq("id", template_id) \
            .eq("user_id", user_id) \
            .execute()
            
        if not template_check.data:
            raise HTTPException(status_code=404, detail="Template not found or not owned by user")
        
        # Update the template
        update_data = template_data.dict(exclude={"id", "user_id", "created_at"})
        response = supabase.table("prompt_templates").update(update_data) \
            .eq("id", template_id) \
            .execute()
        
        return {"success": True, "template": response.data[0] if response.data else None}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating template: {str(e)}")

@router.delete("/template/{template_id}")
async def delete_template(
    template_id: int,
    user_id: str = Depends(supabase_helpers.get_user_from_session_token)
):
    """Delete a template"""
    try:
        # Check if template exists and belongs to the user
        template_check = supabase.table("prompt_templates").select("*") \
            .eq("id", template_id) \
            .eq("user_id", user_id) \
            .execute()
            
        if not template_check.data:
            raise HTTPException(status_code=404, detail="Template not found or not owned by user")
        
        # Delete the template
        response = supabase.table("prompt_templates").delete() \
            .eq("id", template_id) \
            .execute()
        
        return {"success": True, "message": "Template deleted successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting template: {str(e)}")