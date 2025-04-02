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
