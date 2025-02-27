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
        response = supabase.table("chats").insert({
            "user_id": user_id,
            **chat.model_dump(),
        }).execute()
        return {"success": True, "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
