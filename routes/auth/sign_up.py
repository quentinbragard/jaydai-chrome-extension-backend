# routes/auth/sign_up.py - Standard email sign up
from fastapi import HTTPException
from . import router
from .schemas import SignUpData
from utils.notification_service import NotificationService
import logging
from utils.onboarding.folder_mapping import FolderRecommendationEngine

logger = logging.getLogger(__name__)

JAYDAI_ORG_ID = "19864b30-936d-4a8d-996a-27d17f11f00f"

@router.post("/sign_up")
async def sign_up(sign_up_data: SignUpData):
    from . import supabase  # ensure patched supabase is used during tests
    """Sign up a new user with automatic confirmation and session creation."""
    try:
        # Step 1: Sign the user up via Supabase Auth
        user_response = supabase.auth.sign_up({
            "email": sign_up_data.email,
            "password": sign_up_data.password,
            "options": {"data": {"name": sign_up_data.name}},
            "email_confirm": True,
        })
        
        if not user_response.user:
            raise HTTPException(status_code=400, detail="Failed to create user account")
        
        logger.info(f"User created and confirmed: {user_response.user.id}")
        
        # Step 2: Create user metadata
        user_with_metadata = None
        try:
            metadata_insert_data = {
                "user_id": user_response.user.id,
                "pinned_folder_ids": [FolderRecommendationEngine.STARTER_PACK_FOLDER_ID],
                "name": sign_up_data.name,
                "organization_ids": [JAYDAI_ORG_ID],
                "email": sign_up_data.email,
                "additional_email": None,
                "phone_number": None,
                "additional_organization": None
            }
            
            metadata_response = supabase.table("users_metadata").insert(metadata_insert_data).execute()
            
            metadata = metadata_response.data[0] if metadata_response.data else metadata_insert_data
            user_with_metadata = {**user_response.user.__dict__, "metadata": metadata}
            
            logger.info(f"User metadata created for: {user_response.user.id}")
            
        except Exception as metadata_error:
            logger.error(f"Error creating user metadata: {str(metadata_error)}")
            # Provide default metadata if creation fails
            default_metadata = {
                "user_id": user_response.user.id,
                "name": sign_up_data.name,
                "pinned_folder_ids": [FolderRecommendationEngine.STARTER_PACK_FOLDER_ID],
                "organization_ids": [JAYDAI_ORG_ID],
            }
            user_with_metadata = {**user_response.user.__dict__, "metadata": default_metadata}
        
        # Step 3: Create welcome notification
        try:
            await NotificationService.create_welcome_notification(user_response.user.id, sign_up_data.name)
        except Exception as notification_error:
            logger.error(f"Error creating welcome notification: {str(notification_error)}")
        
        # Step 4: Use the session returned by sign_up or fall back to a sign in
        try:
            if user_response.session:
                session = user_response.session
            else:
                session_response = supabase.auth.sign_in_with_password({
                    "email": sign_up_data.email,
                    "password": sign_up_data.password,
                })
                session = session_response.session

            session_data = {
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
                "expires_at": session.expires_at,
            } if session else None

            logger.info(f"Session created for user: {user_response.user.id}")

        except Exception as session_error:
            logger.error(f"Error creating session: {str(session_error)}")
            # Return without session if sign-in fails
            session_data = None
        
        return {
            "success": True,
            "message": "Sign up successful. Account automatically confirmed.",
            "user": user_with_metadata,
            "session": session_data,
            "is_new_user": True
        }
        
    except Exception as e:
        logger.error(f"Error during sign up: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error during sign up: {str(e)}")
