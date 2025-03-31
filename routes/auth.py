from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import requests
from supabase import create_client, Client
import dotenv
import os
from utils.notification_service import create_first_notification
from typing import Optional
from datetime import datetime, timedelta
import uuid
import jwt


dotenv.load_dotenv()

# Initialize Supabase client

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

router = APIRouter(prefix="/auth", tags=["Authentication"])

class SignInData(BaseModel):
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    id_token: str

class RefreshTokenData(BaseModel):
    refresh_token: str
    
class SignUpData(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
    

# Data model for OTP verification
class VerifyOTPData(BaseModel):
    email: str
    token: str
    linkedin_id: Optional[str] = None
    name: Optional[str] = None
    
    

@router.get("/confirm")
async def confirm_email(token: str, type: str = "signup"):
    """
    Confirm email address and redirect to ChatGPT or app UI.
    """
    try:
        # Use Supabase's verify_otp method to confirm the email with the token
        response = supabase.auth.verify_otp({
            "token": token,
            "type": type,
        })

        if response.user:
            # You can choose to redirect to a specific page on your extension or app
            return RedirectResponse("https://chat.openai.com")
        else:
            raise HTTPException(status_code=400, detail="Invalid or expired confirmation token")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm email: {str(e)}")

    
    
@router.post("/sign_up")
async def sign_up(sign_up_data: SignUpData):
    """Sign up a new user."""
    #try:
    # Create the user in Supabase
    response = supabase.auth.sign_up({
        "email": sign_up_data.email,
        "password": sign_up_data.password,
        "options": {
            "data": {
                "name": sign_up_data.name
            }
        }
    })
    
    print("response", response)
    
    # Initialize user metadata with default pinned folders
    if response.user:
        # Create metadata with default pinned folder
        metadata_response = supabase.table("users_metadata").insert({
            "user_id": response.user.id,
            "pinned_official_folder_ids": [1],  # Default starter pack folder
            "pinned_organization_folder_ids": [],
            "name": sign_up_data.name,
            "additional_email": None,
            "phone_number": None,
            "additional_organization": None
        }).execute()
        
        print("metadata_response", metadata_response)
        
        metadata = metadata_response.data[0] if metadata_response.data else None
        user_with_metadata = {**response.user.__dict__, "metadata": metadata}
    
    return {
        "success": True,
        "message": "Sign up successful. Please check your email to verify your account.",
        "user": user_with_metadata,
        "session": {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "expires_at": response.session.expires_at
        }
    }
    #except Exception as e:
    #    raise HTTPException(status_code=500, detail=f"Error during sign up: {str(e)}")
    
@router.post("/sign_in")
async def sign_in(sign_in_data: SignInData):
    """Authenticate user via email & password."""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": sign_in_data.email,
            "password": sign_in_data.password
        })

        # Check for notifications after successful login
        await create_first_notification(response.user.id)

        # Get user metadata
        metadata_response = supabase.table("users_metadata") \
            .select("*") \
            .eq("user_id", response.user.id) \
            .single() \
            .execute()

        metadata = metadata_response.data if metadata_response.data else {
            "name": None,
            "additional_email": None,
            "phone_number": None,
            "additional_organization": None,
            "pinned_official_folder_ids": [],
            "pinned_organization_folder_ids": []
        }

        user_with_metadata = {**response.user.__dict__, "metadata": metadata}

        return {
            "success": True,
            "user": user_with_metadata,
            "session": {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/sign_in_with_google")
async def sign_in(google_sign_in_data: GoogleAuthRequest):
    """Authenticate user via Google OAuth."""
    print("google_sign_in_data", google_sign_in_data)
    #try:
        # Exchange ID token for user info with Supabase
    response = supabase.auth.sign_in_with_id_token({
        "provider": "google", 
        "token": google_sign_in_data.id_token,
    })
    
    print("===========================Supabase sign_in_with_id_token response:", response)
    
    if not response.user:
        raise HTTPException(status_code=400, detail="Invalid Google ID token")
    
    user_id = response.user.id
    
    # Check for notifications after successful login
    await create_first_notification(user_id)

    # Get user metadata
    metadata_response = supabase.table("users_metadata") \
        .select("*") \
        .eq("user_id", user_id) \
        .execute()
        
    print("\n\n===========metadata_response", metadata_response)

    # If no metadata exists for this user, create a new metadata record
    if not metadata_response.data:
        print("Creating new user metadata for Google user")
        user_email = response.user.email
        user_name = response.user.user_metadata.get("full_name", "")
        
        # Create default metadata for Google sign-in users
        metadata_response = supabase.table("users_metadata").insert({
            "user_id": user_id,
            "name": user_name,
            "email": user_email,
            "google_id": response.user.user_metadata.get("sub", ""),
            "pinned_official_folder_ids": [1],  # Default starter pack folder
            "pinned_organization_folder_ids": []
        }).execute()
        
        metadata = metadata_response.data[0] if metadata_response.data else {
            "name": user_name,
            "email": user_email,
            "pinned_official_folder_ids": [1],
            "pinned_organization_folder_ids": []
        }
    else:
        metadata = metadata_response.data

    # Ensure we have user data to return
    user_dict = response.user.__dict__ if hasattr(response.user, "__dict__") else {
        "id": response.user.id,
        "email": response.user.email,
        "app_metadata": response.user.app_metadata,
        "user_metadata": response.user.user_metadata,
    }
    
    user_with_metadata = {**user_dict, "metadata": metadata}

    return {
        "success": True,
        "user": user_with_metadata,
        "session": {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "expires_at": response.session.expires_at
        }
    }
   # except Exception as e:
        # Proper error handling
        #error_message = str(e)
        #print(f"Google Sign-In error: {error_message}")
        #raise HTTPException(status_code=500, detail=f"Google Sign-In error: {error_message}")


@router.post("/refresh_token")
async def refresh_token(refresh_data: RefreshTokenData):
    """Refresh an expired access token using the refresh token."""
    try:
        response = supabase.auth.refresh_session(refresh_data.refresh_token)

        return {
            "success": True,
            "session": {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.get("/me")
async def get_current_user(user_id: str = Depends(supabase.auth.get_user)):
    """Get the current authenticated user."""
    try:
        # Check for notifications on user session validation
        await create_first_notification(user_id)
        
        return {
            "success": True,
            "user_id": user_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")