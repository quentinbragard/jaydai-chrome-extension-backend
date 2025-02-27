from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import requests
from supabase import create_client, Client
import dotenv
import os

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

@router.post("/sign_in")
async def sign_in(sign_in_data: SignInData):
    """Authenticate user via email & password."""
    #try:
    response = supabase.auth.sign_in_with_password({
        "email": sign_in_data.email,
        "password": sign_in_data.password
    })

    from datetime import datetime, timedelta



    return {
        "success": True,
        "user": response.user,
        "session": {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,  # Include refresh token
            "expires_at": response.session.expires_at  # Add expiry timestamp
        }
    }
    #except Exception as e:
   #     raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

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
        
        return {
            "success": True,
            "user": response.user,
            "session": {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,  # Include refresh token
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
