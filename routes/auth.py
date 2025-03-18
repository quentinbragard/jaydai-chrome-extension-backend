from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import requests
from supabase import create_client, Client
import dotenv
import os
from utils.notification_service import check_user_notifications
from typing import Optional
from datetime import datetime, timezone
dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_API_KEY"))

router = APIRouter(prefix="/auth", tags=["Authentication"])

class SignInData(BaseModel):
    email: str
    password: str

class GoogleAuthData(BaseModel):
    id_token: str

class RefreshTokenData(BaseModel):
    refresh_token: str
    
class SignUpData(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
    

async def initialize_user_metadata(user_id: str):
    """Initialize a new user's metadata with default pinned folders."""
    try:
        # Check if metadata already exists
        existing = supabase.table("users_metadata").select("id") \
            .eq("user_id", user_id) \
            .execute()
            
        if not existing.data:
            # Create new metadata with folder ID 1 pinned by default
            supabase.table("users_metadata").insert({
                "user_id": user_id,
                "pinned_official_folder_ids": [1],  # Starter pack folder
                "preferences_metadata": {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "onboarding_completed": False
                }
            }).execute()
            
        return True
    except Exception as e:
        print(f"Error initializing user metadata: {str(e)}")
        return False
    
    
@router.post("/sign_up")
async def sign_up(sign_up_data: SignUpData):
    """Sign up a new user."""
    try:
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
        
        # Initialize user metadata with default pinned folders
        if response.user:
            await initialize_user_metadata(response.user.id)
        
        return {
            "success": True,
            "message": "Sign up successful. Please check your email to verify your account."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during sign up: {str(e)}")
@router.post("/sign_in")
async def sign_in(sign_in_data: SignInData):
    """Authenticate user via email & password."""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": sign_in_data.email,
            "password": sign_in_data.password
        })

        # Check for notifications after successful login
        await check_user_notifications(response.user.id)

        return {
            "success": True,
            "user": response.user,
            "session": {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/google")
async def google_auth(auth_data: GoogleAuthData):
    """Authenticate via Google."""
    try:
        google_user = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={auth_data.id_token}").json()
        if "email" not in google_user:
            raise HTTPException(status_code=403, detail="Invalid Google ID token")

        response = supabase.auth.sign_in_with_id_token({
            "provider": "google",
            "token": auth_data.id_token
        })
        
        # Check for notifications after successful login
        await check_user_notifications(response.user.id)
        
        return {
            "success": True,
            "user": response.user,
            "session": {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "expires_at": response.session.expires_at
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing Google authentication: {str(e)}")

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
        await check_user_notifications(user_id)
        
        return {
            "success": True,
            "user_id": user_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")