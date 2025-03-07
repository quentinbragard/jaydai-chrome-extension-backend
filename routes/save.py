from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
import dotenv
import os

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_API_KEY"))

router = APIRouter(prefix="/save", tags=["Save"])

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

class UserMetadataData(BaseModel):
    id: str
    email: str
    name: str
    picture: str = None
    phone_number: str = None
    org_name: str = None

@router.post("/message")
async def save_message(message: MessageData, user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Save a chat message."""
    try:
        response = supabase.table("messages").insert({
            "user_id": user_id,
            **message.model_dump(),
        }).execute()
        return {"success": True, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/chat")
async def save_chat(chat: ChatData, user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Save a chat session."""
    try:
        # Check if chat already exists
        existing = supabase.table("chats").select("id") \
            .eq("user_id", user_id) \
            .eq("provider_chat_id", chat.provider_chat_id) \
            .execute()
            
        if existing.data:
            # Update existing chat
            response = supabase.table("chats").update({
                "title": chat.title,
            }).eq("user_id", user_id) \
              .eq("provider_chat_id", chat.provider_chat_id) \
              .execute()
        else:
            # Create new chat
            response = supabase.table("chats").insert({
                "user_id": user_id,
                **chat.model_dump(),
            }).execute()
            
        return {"success": True, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.post("/user_metadata")
async def save_user_metadata(metadata: UserMetadataData, user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    print("Metadata: ", metadata)
    print("User ID: ", user_id)
    """Save user metadata."""
    try:
        # Check if metadata already exists
        existing = supabase.table("users_metadata").select("id") \
            .eq("user_id", user_id) \
            .execute()
            
        if existing.data:
            # Update existing metadata
            response = supabase.table("users_metadata").update({
                "email": metadata.email,
                "name": metadata.name,
                "phone_number": metadata.phone_number,
                "org_name": metadata.org_name,
            }).eq("user_id", user_id) \
              .execute()
        else:
            # Create new metadata
            response = supabase.table("users_metadata").insert({
                "user_id": user_id,
                "email": metadata.email,
                "name": metadata.name,
                "phone_number": metadata.phone_number,
                "org_name": metadata.org_name,
            }).execute()
            
        return {"success": True, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")