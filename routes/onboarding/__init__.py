from fastapi import APIRouter

router = APIRouter(tags=["Onboarding"])

# Import all route modules to register them with the router
from .checklist import router as checklist_router
from .mark_action import router as mark_action_router
from .dismiss import router as dismiss_router
from .complete_onboarding import router as complete_onboarding_router
from .preview_folder_recommendations import router as preview_folder_recommendations_router
from .recommend_folders import router as recommend_folders_router

# Include all the routers
router.include_router(checklist_router)
router.include_router(mark_action_router)
router.include_router(dismiss_router)
router.include_router(complete_onboarding_router)
router.include_router(preview_folder_recommendations_router)
router.include_router(recommend_folders_router)

__all__ = [
    "router",
]