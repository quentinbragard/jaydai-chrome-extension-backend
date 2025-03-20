# This file makes the prompts directory a Python package
from fastapi import APIRouter
from . import templates, folders

# Create a parent router for all prompts-related endpoints
router = APIRouter(prefix="/prompts", tags=["Prompts"])

# Include sub-routers
router.include_router(templates.router)
router.include_router(folders.router)