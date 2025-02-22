from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
import requests

# Load environment variables
load_dotenv()

app = FastAPI()

# 🔹 Secure CORS Settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "chrome-extension://*",  
        "https://chatgpt.com",   
        "http://localhost",  
        "http://127.0.0.1:8000",  
        "https://your-frontend.com",  
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔹 Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# ---------------------------------------
# 🔹 Model for Email/Password Sign-in
# ---------------------------------------
class SignInData(BaseModel):
    email: str
    password: str

class GoogleAuthData(BaseModel):
    id_token: str

class MessageData(BaseModel):
    message_id: str
    content: str
    role: str
    rank: int
    provider_chat_id: str
    model: str
    thinking_time: float

class ChatData(BaseModel):
    provider_chat_id: str
    title: str
    provider_name: str

# ------------------------------------------------------------
# 🔹 Helper Function: Extract User ID from Bearer Token
# ------------------------------------------------------------

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

def get_user_from_session_token(authorization: str = Header(None)):
    """Extracts and verifies user ID from Supabase JWT token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Missing or invalid Authorization Header")
    
    token = authorization.split(" ")[1]  # Extract the token
    print("🔹 Token received:", token)

    try:
    # 🔹 Validate token using Supabase's `auth.get_user()` method
        user_info = supabase.auth.get_user(token)
        
        if not user_info or not user_info.user:
            raise HTTPException(status_code=403, detail="Invalid token")

        user_id = user_info.user.id
        print("🔹 Supabase user ID:", user_id)

        return user_id

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating token: {str(e)}")
# ---------------------------------------
# 🔹 Sign in with Email & Password
# ---------------------------------------
@app.post("/auth/sign_in")
async def sign_in(sign_in_data: SignInData):
    """Authenticates a user via email & password and returns an access token."""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": sign_in_data.email,
            "password": sign_in_data.password
        })
        supabase_user = response.user
        access_token = response.session.access_token
        return {
            "success": True,
            "user": {
                "id": supabase_user.id,
                "email": supabase_user.email
            },
            "session": {
                "access_token": access_token
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# ---------------------------------------
# 🔹 Google Sign-In
# ---------------------------------------
@app.post("/auth/google")
async def google_auth(auth_data: GoogleAuthData):
    """Verifies Google ID token and authenticates via Supabase."""
    try:
        # Validate Google ID Token
        response = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={auth_data.id_token}")
        if response.status_code != 200:
            raise HTTPException(status_code=403, detail="Invalid Google ID token")

        google_user = response.json()
        user_email = google_user.get("email")
        google_id = google_user.get("sub")  

        if not user_email or not google_id:
            raise HTTPException(status_code=400, detail="Invalid token payload")

        # Sign in or sign up with Supabase using ID token
        supabase_response = supabase.auth.sign_in_with_id_token({
            "provider": "google",
            "token": auth_data.id_token
        })

        if supabase_response.error:
            raise HTTPException(status_code=500, detail=f"Supabase error: {supabase_response.error.message}")

        supabase_user = supabase_response.user
        access_token = supabase_response.session.access_token

        return {
            "success": True,
            "user": {
                "id": supabase_user.id,
                "email": supabase_user.email
            },
            "session": {
                "access_token": access_token
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing Google authentication: {str(e)}")

# ---------------------------------------
# 🔹 Save Message Endpoint
# ---------------------------------------
@app.post("/save_message")
async def save_message(message: MessageData, user_id: str = Depends(get_user_from_session_token)):
    print("🔹 Saving message for user:", user_id)
    print("🔹 Message:", message)
    """Saves or updates a chat message in Supabase."""
    try:
        response = supabase.table("messages").select("*").eq("user_id", user_id).eq("message_id", message.message_id).execute()
        existing_messages = response.data

        if existing_messages:
            message_id = existing_messages[0]['id']
            supabase.table("messages").update({
                "content": message.content,
                "role": message.role,
                "rank": message.rank,
                "provider_chat_id": message.provider_chat_id,
                "model": message.model
            }).eq("id", message_id).execute()
            return {"success": True, "data": "Message updated successfully"}
        else:
            supabase.table("messages").insert({
                "user_id": user_id,
                "content": message.content,
                "role": message.role,
                "rank": message.rank,
                "message_id": message.message_id,
                "provider_chat_id": message.provider_chat_id,
                "model": message.model,
                "thinking_time": message.thinking_time,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            return {"success": True, "data": "Message saved successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# ---------------------------------------
# 🔹 Save Chat Endpoint
# ---------------------------------------
@app.post("/save_chat")
async def save_chat(chat: ChatData, user_id: str = Depends(get_user_from_session_token)):
    """Saves or updates a chat in Supabase."""
    try:
        response = supabase.table("chats").select("*").eq("provider_chat_id", chat.provider_chat_id).eq("user_id", user_id).execute()
        existing_chats = response.data

        if existing_chats:
            existing_chat = existing_chats[0]
            if existing_chat["title"] != chat.title:
                supabase.table("chats").update({"title": chat.title}).eq("id", existing_chat['id']).execute()
                return {"success": True, "data": "Chat updated successfully"}
            return {"success": True, "data": "Chat already exists with same title"}
        else:
            supabase.table("chats").insert({
                "user_id": user_id,
                "provider_chat_id": chat.provider_chat_id,
                "title": chat.title,
                "provider_name": chat.provider_name,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            return {"success": True, "data": "Chat saved successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
