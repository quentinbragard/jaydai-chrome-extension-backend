# models/prompts/templates.py
from pydantic import BaseModel
from typing import Optional, List, Union, Dict
from models.prompts.blocks import BlockType
from enum import Enum

class MetadataType(str, Enum):
    ROLE = "role"
    TONE_STYLE = "tone_style"
    OUTPUT_FORMAT = "output_format"
    AUDIENCE = "audience"
    OUTPUT_LANGUAGE = "output_language"
    MAIN_CONTEXT = "main_context"
    MAIN_GOAL = "main_goal"

class TemplateMetadata(BaseModel):
    """Metadata references block IDs, 0 means empty/no value"""
    role: int = 0
    tone_style: Optional[int] = 0
    output_format: Optional[int] = 0
    audience: Optional[int] = 0
    output_language: Optional[int] = 0
    main_context: int = 0
    main_goal: int = 0

class TemplateBase(BaseModel):
    title: Union[str, Dict[str, str]]
    content: Union[str, Dict[str, str]]
    blocks: Optional[List[int]] = []
    metadata: Optional[TemplateMetadata] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    folder_id: Optional[int] = None
    tags: Optional[List[str]] = []
    locale: Optional[str] = "en"

class TemplateCreate(TemplateBase):
    type: str = "user"

class TemplateUpdate(BaseModel):
    title: Optional[Union[str, Dict[str, str]]] = None
    content: Optional[Union[str, Dict[str, str]]] = None
    blocks: Optional[List[int]] = None
    metadata: Optional[TemplateMetadata] = None
    description: Optional[Union[str, Dict[str, str]]] = None
    folder_id: Optional[int] = None
    tags: Optional[List[str]] = None

class TemplateResponse(BaseModel):
    id: int
    title: str
    content: Union[str, Dict[str, str]]
    blocks: List[int]
    metadata: Optional[TemplateMetadata] = None
    expanded_blocks: Optional[List] = None
    description: Optional[str] = None
    folder_id: Optional[int] = None
    type: str
    usage_count: Optional[int] = 0
    last_used_at: Optional[str] = None
    created_at: str
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    folder: Optional[str] = None