from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
import dotenv
import os
from supabase import create_client, Client
from typing import Dict, List, Optional, Any
from utils.supabase_helpers import get_user_from_session_token

# Initialize Supabase client
dotenv.load_dotenv()
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
    responses={404: {"description": "Not found"}},
)

# Energy cost constants (in joules per token)
ENERGY_COST_PER_INPUT_TOKEN = 0.0003  # Example value, adjust based on actual model efficiency
ENERGY_COST_PER_OUTPUT_TOKEN = 0.0006  # Output tokens typically cost more energy

@router.get("/user")
async def get_user_stats(user_id: str = Depends(get_user_from_session_token)):
    """Get all stats for the current user"""
    try:
        # Get current date and date 7 days ago
        current_date = datetime.now()
        last_week_date = current_date - timedelta(days=7)
        
        # Format dates for SQL queries
        current_date_str = current_date.strftime('%Y-%m-%d')
        last_week_date_str = last_week_date.strftime('%Y-%m-%d')
        
        # Get total conversations
        conversations_response = supabase.table("conversations").select("id").eq("user_id", user_id).execute()
        total_chats = len(conversations_response.data)
        
        # Get conversations from last 7 days
        recent_conversations_response = supabase.table("conversations") \
            .select("id, created_at") \
            .eq("user_id", user_id) \
            .gte("created_at", last_week_date_str) \
            .execute()
        recent_chats = len(recent_conversations_response.data)
        
        # Get all messages
        messages_response = supabase.table("messages").select("id, conversation_id, role, input_tokens, output_tokens, created_at") \
            .eq("user_id", user_id).execute()
        
        total_messages = len(messages_response.data)
        
        # Calculate messages per conversation
        conversation_message_counts = {}
        for message in messages_response.data:
            conv_id = message.get("conversation_id")
            if conv_id:
                conversation_message_counts[conv_id] = conversation_message_counts.get(conv_id, 0) + 1
        
        avg_messages_per_chat = round(total_messages / total_chats, 2) if total_chats > 0 else 0
        
        # Calculate recent token usage (last 7 days)
        recent_messages = [m for m in messages_response.data if m.get("created_at") and m.get("created_at") >= last_week_date_str]
        
        recent_input_tokens = sum(m.get("input_tokens", 0) for m in recent_messages) or 0
        recent_output_tokens = sum(m.get("output_tokens", 0) for m in recent_messages) or 0
        recent_total_tokens = recent_input_tokens + recent_output_tokens
        
        # Calculate all-time token usage
        all_time_input_tokens = sum(m.get("input_tokens", 0) for m in messages_response.data) or 0
        all_time_output_tokens = sum(m.get("output_tokens", 0) for m in messages_response.data) or 0
        all_time_total_tokens = all_time_input_tokens + all_time_output_tokens
        
        # Calculate energy usage (convert to kWh)
        recent_energy = (recent_input_tokens * ENERGY_COST_PER_INPUT_TOKEN + 
                        recent_output_tokens * ENERGY_COST_PER_OUTPUT_TOKEN) / 3_600_000  # convert J to kWh
        all_time_energy = (all_time_input_tokens * ENERGY_COST_PER_INPUT_TOKEN + 
                          all_time_output_tokens * ENERGY_COST_PER_OUTPUT_TOKEN) / 3_600_000
        
        # Calculate average response time
        thinking_times = []
        for msg in messages_response.data:
            if msg.get("thinking_time"):
                thinking_times.append(msg.get("thinking_time"))
        
        avg_thinking_time = sum(thinking_times) / len(thinking_times) if thinking_times else 0
        total_thinking_time = sum(thinking_times)
        
        # Calculate message counts per day for the last 7 days
        messages_per_day = {}
        for i in range(7):
            date = (current_date - timedelta(days=i)).strftime('%Y-%m-%d')
            messages_per_day[date] = 0
        
        for message in messages_response.data:
            created_at = message.get("created_at")
            if created_at:
                date = created_at.split('T')[0]  # Extract YYYY-MM-DD
                if date in messages_per_day:
                    messages_per_day[date] += 1
        
        # Calculate user efficiency score (combination of factors)
        # Higher score is better - based on:
        # 1. Optimal messages per conversation (not too few, not too many)
        # 2. Token efficiency (ratio of output to input)
        # 3. Response time optimization
        
        messages_per_chat_score = min(100, max(0, 100 - abs(avg_messages_per_chat - 5) * 10))  # Optimal is around 5 messages
        token_efficiency = (all_time_output_tokens / all_time_input_tokens * 50) if all_time_input_tokens else 50
        response_time_score = min(100, max(0, 100 - (avg_thinking_time / 3) * 10))  # Lower thinking time is better
        
        efficiency_score = int((messages_per_chat_score + token_efficiency + response_time_score) / 3)
        
        # Calculate model usage breakdown
        model_usage = {}
        for message in messages_response.data:
            model = message.get("model", "unknown")
            if model:
                if model not in model_usage:
                    model_usage[model] = {
                        "count": 0,
                        "input_tokens": 0,
                        "output_tokens": 0
                    }
                model_usage[model]["count"] += 1
                model_usage[model]["input_tokens"] += message.get("input_tokens", 0)
                model_usage[model]["output_tokens"] += message.get("output_tokens", 0)
        
        # Return compiled stats
        return {
            "total_chats": total_chats,
            "recent_chats": recent_chats,
            "total_messages": total_messages,
            "avg_messages_per_chat": avg_messages_per_chat,
            "messages_per_day": messages_per_day,
            "token_usage": {
                "recent": recent_total_tokens,
                "recent_input": recent_input_tokens,
                "recent_output": recent_output_tokens,
                "total": all_time_total_tokens,
                "total_input": all_time_input_tokens,
                "total_output": all_time_output_tokens
            },
            "energy_usage": {
                "recent": round(recent_energy, 6),
                "total": round(all_time_energy, 6),
                "per_message": round(all_time_energy / total_messages, 6) if total_messages else 0
            },
            "thinking_time": {
                "average": round(avg_thinking_time, 2),
                "total": round(total_thinking_time, 2)
            },
            "efficiency": efficiency_score,
            "model_usage": model_usage
        }
    except Exception as e:
        print(f"Error getting user stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting user stats: {str(e)}")

@router.get("/conversations/weekly")
async def get_weekly_conversation_stats(user_id: str = Depends(get_user_from_session_token)):
    """Get weekly conversation statistics"""
    try:
        # Get current date and date 28 days ago (4 weeks)
        current_date = datetime.now()
        four_weeks_ago = current_date - timedelta(days=28)
        
        # Format dates for SQL queries
        four_weeks_ago_str = four_weeks_ago.strftime('%Y-%m-%d')
        
        # Get conversations from last 4 weeks
        conversations_response = supabase.table("conversations") \
            .select("id, created_at") \
            .eq("user_id", user_id) \
            .gte("created_at", four_weeks_ago_str) \
            .execute()
        
        # Group conversations by week
        weekly_counts = [0, 0, 0, 0]  # 4 weeks
        
        for conv in conversations_response.data:
            created_at = datetime.fromisoformat(conv.get("created_at").replace('Z', '+00:00'))
            days_ago = (current_date - created_at).days
            week_index = min(3, days_ago // 7)  # Ensure it fits in our 4 weeks
            weekly_counts[week_index] += 1
        
        # Return weekly breakdown
        return {
            "weekly_conversations": list(reversed(weekly_counts)),  # Most recent week first
            "total": sum(weekly_counts)
        }
    except Exception as e:
        print(f"Error getting weekly conversation stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting weekly stats: {str(e)}")

@router.get("/messages/distribution")
async def get_message_distribution(user_id: str = Depends(get_user_from_session_token)):
    """Get distribution of messages by role (user vs AI)"""
    try:
        messages_response = supabase.table("messages") \
            .select("id, role") \
            .eq("user_id", user_id) \
            .execute()
        
        user_messages = 0
        ai_messages = 0
        
        for msg in messages_response.data:
            role = msg.get("role", "")
            if role == "user":
                user_messages += 1
            elif role == "assistant":
                ai_messages += 1
        
        total_messages = user_messages + ai_messages
        
        return {
            "user_messages": user_messages,
            "ai_messages": ai_messages,
            "total": total_messages,
            "user_percentage": round((user_messages / total_messages) * 100, 1) if total_messages else 0,
            "ai_percentage": round((ai_messages / total_messages) * 100, 1) if total_messages else 0
        }
    except Exception as e:
        print(f"Error getting message distribution: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting message distribution: {str(e)}")