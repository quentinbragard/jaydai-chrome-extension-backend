from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
import dotenv
import os
from typing import List, Optional
from enum import Enum
from . import folders, templates, blocks, search
try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None
from fastapi import Request

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

# Create a parent router for all prompts-related endpoints
router = APIRouter(prefix="/prompts", tags=["Prompts"])


def monitor_prompts_folders(request: Request):
    if sentry_sdk is not None and sentry_sdk.Hub.current.client:
        sentry_sdk.set_tag("endpoint_group", "prompts_folders")

# Include sub-routers
router.include_router(
    folders.router,
    prefix="/folders",
    tags=["Folders"],
    dependencies=[Depends(monitor_prompts_folders)],
)
router.include_router(templates.router, prefix="/templates", tags=["Templates"])
router.include_router(blocks.router, prefix="/blocks", tags=["Blocks"])
router.include_router(search.router, prefix="/search", tags=["Search"])