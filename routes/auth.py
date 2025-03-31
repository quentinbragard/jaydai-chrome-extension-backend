from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import requests
from supabase import create_client, Client
import dotenv
import os
from utils.notification_service import check_user_notifications
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
        await check_user_notifications(response.user.id)

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
    # Exchange authorization code for tokens
    response = supabase.auth.sign_in_with_id_token(
    {
        "provider": "google", 
        "token": google_sign_in_data.id_token,
    }
)
    
    print("response", response)
    
   

    # Check for notifications after successful login
    await check_user_notifications(response.user.id)

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
    #except Exception as e:
    #    # Uncomment the error handling if needed
    #    raise HTTPException(status_code=500, detail=f"Google Sign-In error: {str(e)}")
    

# LinkedIn auth request model
class LinkedInAuthRequest(BaseModel):
    code: str
    redirect_uri: str

# LinkedIn API constants
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USER_INFO_URL = "https://api.linkedin.com/v2/me"
LINKEDIN_EMAIL_URL = "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))"

@router.post("/sign_in_with_linkedin")
async def sign_in_with_linkedin(linkedin_auth_data: LinkedInAuthRequest):
    """Authenticate user via LinkedIn OAuth."""
    print("linkedin_auth_data", linkedin_auth_data)
    try:
        # Step 1: Exchange authorization code for access token
        token_data = {
            "grant_type": "authorization_code",
            "code": linkedin_auth_data.code,
            "redirect_uri": linkedin_auth_data.redirect_uri,
            "client_id": LINKEDIN_CLIENT_ID,
            "client_secret": LINKEDIN_CLIENT_SECRET
        }
        
        token_response = requests.post(LINKEDIN_TOKEN_URL, data=token_data)
        token_result = token_response.json()
        print("token_result", token_result)
        
        if "access_token" not in token_result:
            raise HTTPException(status_code=400, detail="Invalid LinkedIn code")
        
        access_token = token_result["access_token"]
        id_token = token_result.get("id_token")
        
        decoded_token = jwt.decode(id_token, options={"verify_signature": False})
        
        # Extract user details from decoded token
        email = decoded_token.get("email")
        first_name = decoded_token.get("given_name", "")
        last_name = decoded_token.get("family_name", "")
        name = f"{first_name} {last_name}".strip()
        user_id = decoded_token.get("sub")
        
        print("email", email)
        print("name", name)
        print("user_id", user_id)
        
        if not email:
            raise HTTPException(status_code=400, detail="Could not retrieve email from LinkedIn")
        
        
        # Check if user already exists in Supabase
        existing_user = None
        try:
            # Search by LinkedIn ID first in user metadata
            metadata_response = supabase.table("users_metadata").select("user_id").eq("linkedin_id", user_id).execute()
            
            if metadata_response.data:
                # If found, get the user
                user_id = metadata_response.data[0]["user_id"]
                existing_user = supabase.auth.get_user(user_id)
            else:
                # Try finding by email
                existing_user = supabase.table("users_metadata").select("user_id").eq("email", email).execute()
        except Exception as e:
            # User not found, will create new user
            pass
        
        # If user exists, sign them in
        if existing_user and hasattr(existing_user, 'id'):
            print("EXISTING USER ==================")
            # Generate a sign-in link
            sign_in_response = supabase.auth.sign_in_with_email_and_password(email, "<secure-random-password>")
            
            # Return the session and user info
            user_with_metadata = get_user_with_metadata(sign_in_response.user.id)
            
            # Check for notifications after successful login
            await check_user_notifications(sign_in_response.user.id)
            
            return {
                "success": True,
                "user": user_with_metadata,
                "session": {
                    "access_token": sign_in_response.session.access_token,
                    "refresh_token": sign_in_response.session.refresh_token,
                    "expires_at": sign_in_response.session.expires_at
                }
            }
        
        # Create new user with random password
        import secrets
        import string
        
        print("NOT EXISTING USER ==================")
        
        # Generate a secure random password
        random_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20))

        print("random_password", random_password)
        # Create user in Supabase Auth
        sign_up_response = supabase.auth.sign_up({
            "email": email,
            "password": random_password,
            "options": {
                "data": {
                    "name": name
                }
            }
        })
        
        print("sign_up_response", sign_up_response)
        
        if not sign_up_response.user:
            raise HTTPException(status_code=500, detail="Failed to create user account")
        
        # Create metadata with LinkedIn info
        metadata_response = supabase.table("users_metadata").insert({
            "user_id": sign_up_response.user.id,
            "name": name,
            "additional_email": email,
            "linkedin_id": user_id,
            "pinned_official_folder_ids": [1],  # Default starter pack folder
            "pinned_organization_folder_ids": []
        }).execute()
        
        metadata = metadata_response.data[0] if metadata_response.data else None
        user_with_metadata = {**sign_up_response.user.__dict__, "metadata": metadata}
        
        return {
            "success": True,
            "message": "Account created with LinkedIn",
            "user": user_with_metadata,
            "session": {
                "access_token": sign_up_response.session.access_token,
                "refresh_token": sign_up_response.session.refresh_token,
                "expires_at": sign_up_response.session.expires_at
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"LinkedIn Sign-In error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LinkedIn Sign-In error: {str(e)}")

# Helper function to get user with metadata
def get_user_with_metadata(user_id):
    user = supabase.auth.get_user(user_id)
    
    # Get user metadata
    metadata_response = supabase.table("users_metadata") \
        .select("*") \
        .eq("user_id", user_id) \
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

    return {**user.__dict__, "metadata": metadata}


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