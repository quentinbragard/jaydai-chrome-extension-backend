from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from pydantic import BaseModel
from supabase import create_client, Client
from utils import supabase_helpers
import dotenv
import os
from typing import List, Optional




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
    model: str = "unknown"
    created_at: float = None

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

class BatchMessageData(BaseModel):
    message_id: str
    content: str
    role: str
    rank: int
    provider_chat_id: str
    model: str
    thinking_time: float

class BatchChatData(BaseModel):
    provider_chat_id: str
    title: str
    provider_name: str

class BatchSaveData(BaseModel):
    chats: List[BatchChatData] = []
    messages: List[BatchMessageData] = []
    
    
@router.post("/message")
async def save_message(message: MessageData, user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    print("Message----------------------------: ", message)
    """Save a chat message."""
    try:
        if message.created_at:
            try:
                # Convert Unix timestamp to ISO format
                created_at = datetime.fromtimestamp(message.created_at, tz=timezone.utc).isoformat()
            except Exception as e:
                print(f"Error converting timestamp {message.created_at}: {str(e)}")
                # Use current time as fallback
                created_at = datetime.now(tz=timezone.utc).isoformat()
        response = supabase.table("messages").insert({
        "user_id": user_id,
            "message_id": message.message_id,
            "content": message.content,
            "role": message.role,
            "rank": message.rank,
            "provider_chat_id": message.provider_chat_id,
            "model": message.model,
            "created_at": created_at
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
    

@router.post("/batch")
async def save_batch(batch_data: BatchSaveData, user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Save a batch of chats and messages."""
    try:
        results = {"chats": [], "messages": []}
        
        # Process chats in batch
        if batch_data.chats:
            # Extract existing chat IDs to differentiate updates vs inserts
            provider_chat_ids = [chat.provider_chat_id for chat in batch_data.chats]
            existing_chats = {}
            
            if provider_chat_ids:
                existing_query = supabase.table("chats").select("provider_chat_id") \
                    .eq("user_id", user_id) \
                    .in_("provider_chat_id", provider_chat_ids) \
                    .execute()
                
                if existing_query.data:
                    for chat in existing_query.data:
                        existing_chats[chat['provider_chat_id']] = True
            
            # Split into inserts and updates
            chats_to_insert = []
            for chat in batch_data.chats:
                if chat.provider_chat_id not in existing_chats:
                    chats_to_insert.append({
                        "user_id": user_id,
                        **chat.model_dump()
                    })
                else:
                    # Update existing chat
                    supabase.table("chats").update({
                        "title": chat.title,
                    }).eq("user_id", user_id) \
                      .eq("provider_chat_id", chat.provider_chat_id) \
                      .execute()
            
            # Insert new chats in batch
            if chats_to_insert:
                chat_response = supabase.table("chats").insert(chats_to_insert).execute()
                results["chats"] = chat_response.data
        
        # Process messages in batch
        if batch_data.messages:
            # Check which message IDs already exist to avoid duplicates
            message_ids = [msg.message_id for msg in batch_data.messages]
            existing_messages = {}
            
            if message_ids:
                existing_query = supabase.table("messages").select("message_id") \
                    .eq("user_id", user_id) \
                    .in_("message_id", message_ids) \
                    .execute()
                
                if existing_query.data:
                    for msg in existing_query.data:
                        existing_messages[msg['message_id']] = True
            
            # Filter out messages that already exist
            messages_to_insert = []
            for message in batch_data.messages:
                if message.message_id not in existing_messages:
                    messages_to_insert.append({
                        "user_id": user_id,
                        **message.model_dump()
                    })
            
            # Insert new messages in batch
            if messages_to_insert:
                message_response = supabase.table("messages").insert(messages_to_insert).execute()
                results["messages"] = message_response.data
        
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in batch save: {str(e)}")
    
class ChatListItem(BaseModel):
    provider_chat_id: str
    title: str
    provider_name: str

class ChatListBatchData(BaseModel):
    chats: List[ChatListItem]

@router.post("/chat-list-batch")
async def save_chat_list_batch(batch_data: ChatListBatchData, user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Save a batch of chats from the conversation list."""
    try:
        if not batch_data.chats:
            return {"success": True, "message": "No chats to save", "count": 0}
            
        print(f"Processing batch save of {len(batch_data.chats)} chats")
        
        # Extract provider_chat_ids for checking existing chats
        provider_chat_ids = [chat.provider_chat_id for chat in batch_data.chats]
        
        # Find which chats already exist
        existing_query = supabase.table("chats").select("provider_chat_id") \
            .eq("user_id", user_id) \
            .in_("provider_chat_id", provider_chat_ids) \
            .execute()
            
        existing_chats = {}
        if existing_query.data:
            for chat in existing_query.data:
                existing_chats[chat['provider_chat_id']] = True
        
        # Prepare updates and inserts
        chats_to_insert = []
        update_count = 0
        
        for chat in batch_data.chats:
            # For existing chats, update the title
            if chat.provider_chat_id in existing_chats:
                supabase.table("chats").update({
                    "title": chat.title,
                }).eq("user_id", user_id) \
                  .eq("provider_chat_id", chat.provider_chat_id) \
                  .execute()
                update_count += 1
            else:
                # For new chats, prepare for batch insert
                chats_to_insert.append({
                    "user_id": user_id,
                    "provider_chat_id": chat.provider_chat_id,
                    "title": chat.title,
                    "provider_name": chat.provider_name
                })
        
        # Insert new chats in batch
        insert_results = None
        if chats_to_insert:
            insert_results = supabase.table("chats").insert(chats_to_insert).execute()
        
        return {
            "success": True,
            "inserted": len(chats_to_insert),
            "updated": update_count,
            "total": len(batch_data.chats)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in chat list batch save: {str(e)}")
    
    
class ConversationMessage(BaseModel):
    message_id: str
    provider_chat_id: str
    content: str
    role: str
    rank: int
    model: str = "unknown"
    created_at: float = None

class MessageBatchRequest(BaseModel):
    messages: List[ConversationMessage]

@router.post("/batch/messages")
async def save_messages_batch(batch_data: MessageBatchRequest, user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Save multiple messages in one batch operation."""
    try:
        results = {"messages": [], "stats": {"inserted": 0, "skipped": 0}}
        
        if not batch_data.messages:
            return {"success": False, "message": "No messages provided"}
        
        # Group messages by conversation ID
        conversations = {}
        for msg in batch_data.messages:
            if msg.provider_chat_id not in conversations:
                conversations[msg.provider_chat_id] = []
            conversations[msg.provider_chat_id].append(msg)
        
        print(f"Processing batch save of {len(batch_data.messages)} messages across {len(conversations)} conversations")
        
        # Process each conversation
        for conversation_id, conversation_messages in conversations.items():
            title = f"Chat {conversation_id[:8]}"  # Generate simple title from ID
            
            existing_chat = supabase.table("chats").select("id") \
                .eq("user_id", user_id) \
                .eq("provider_chat_id", conversation_id) \
                .execute()
                
            if not existing_chat.data:
                # Create new chat
                supabase.table("chats").insert({
                    "user_id": user_id,
                    "provider_chat_id": conversation_id,
                    "title": title,
                    "provider_name": "ChatGPT"
                }).execute()
            
            # 2. Get all existing message IDs for this conversation
            existing_messages = supabase.table("messages").select("message_id") \
                .eq("user_id", user_id) \
                .eq("provider_chat_id", conversation_id) \
                .execute()
                
            existing_message_ids = set()
            if existing_messages.data:
                existing_message_ids = {msg["message_id"] for msg in existing_messages.data}
            
            # 3. Filter out messages that already exist
            messages_to_insert = []
            for msg in conversation_messages:
                if msg.message_id in existing_message_ids:
                    results["stats"]["skipped"] += 1
                    continue
                
                # Convert Unix timestamp to ISO format for PostgreSQL
                created_at = None
                if msg.created_at:
                    try:
                        # Convert Unix timestamp to ISO format
                        created_at = datetime.fromtimestamp(msg.created_at, tz=timezone.utc).isoformat()
                    except Exception as e:
                        print(f"Error converting timestamp {msg.created_at}: {str(e)}")
                        # Use current time as fallback
                        created_at = datetime.now(tz=timezone.utc).isoformat()
                
                messages_to_insert.append({
                    "user_id": user_id,
                    "message_id": msg.message_id,
                    "content": msg.content,
                    "role": msg.role,
                    "rank": msg.rank,
                    "provider_chat_id": msg.provider_chat_id,
                    "model": msg.model,
                    "created_at": created_at  # Now using ISO format timestamp
                })
            
            # 4. Insert new messages in batch if any exist
            if messages_to_insert:
                message_response = supabase.table("messages").insert(messages_to_insert).execute()
                if message_response.data:
                    results["messages"].extend(message_response.data)
                    results["stats"]["inserted"] += len(messages_to_insert)
        
        return {
            "success": True,
            "message": f"Saved {results['stats']['inserted']} new messages, {results['stats']['skipped']} skipped",
            "data": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in message batch save: {str(e)}")