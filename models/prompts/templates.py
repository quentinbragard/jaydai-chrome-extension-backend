# models/templates.py
from pydantic import BaseModel
from typing import Optional, List, Union, Dict
from models.prompts.blocks import BlockType

class TemplateBlock(BaseModel):
    id: int
    type: BlockType
    content: Dict[str, str]
    name: Optional[str] = None
    description: Optional[str] = None

class TemplateBase(BaseModel):
    title: Union[str, Dict[str, str]]
    content: Union[str, Dict[str, str]]
    blocks: Optional[List[int]] = []
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
    description: Optional[Union[str, Dict[str, str]]] = None
    folder_id: Optional[int] = None
    tags: Optional[List[str]] = None

class TemplateResponse(BaseModel):
    id: int
    title: str
    content: Union[str, Dict[str, str]]
    blocks: List[int]
    expanded_blocks: Optional[List[TemplateBlock]] = None
    description: Optional[str] = None
    folder_id: Optional[int] = None
    type: str
    usage_count: Optional[int] = 0
    last_used_at: Optional[str] = None
    created_at: str
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    folder: Optional[str] = None