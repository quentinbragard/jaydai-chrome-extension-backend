# routes/organizations/__init__.py
from fastapi import APIRouter

router = APIRouter(tags=["Organizations"])

# Import route modules to register them with the router
from . import get_organizations
from . import get_organization_by_id

__all__ = [
    "router",
    "get_organizations", 
    "get_organization_by_id"
]