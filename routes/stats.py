from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client, Client
from utils import supabase_helpers
import dotenv
import os
import pandas as pd
from datetime import datetime, timedelta

dotenv.load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_API_KEY"))

router = APIRouter(prefix="/stats", tags=["Stats"])

@router.get("/user")
async def get_user_stats(user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Get user statistics for today's ChatGPT usage."""
    try:
        # Get today's date range
        today = datetime.now().date()
        start_datetime = datetime.combine(today, datetime.min.time())
        end_datetime = datetime.combine(today, datetime.max.time())
        
        # Query messages for today
        response = supabase.table("messages").select("*").eq("user_id", user_id).gte("created_at", start_datetime.isoformat()).lte("created_at", end_datetime.isoformat()).execute()
        
        if not response.data:
            return {
                "total_prompts": 0,
                "average_score": None,  # Will be calculated in future implementation
                "energy_usage": 0.0,    # Placeholder for energy calculation
                "messages_by_model": {}
            }
        
        # Convert to DataFrame for easier analysis
        messages_df = pd.DataFrame(response.data)
        
        # Count user messages (prompts)
        user_messages = messages_df[messages_df["role"] == "user"]
        total_prompts = len(user_messages)
        
        # Calculate average thinking time (as a proxy for complexity)
        thinking_times = messages_df[messages_df["role"] == "assistant"]["thinking_time"].dropna()
        avg_thinking_time = thinking_times.mean() if not thinking_times.empty else 0
        
        # Calculate rough energy usage based on model and response length
        # This is a simplified placeholder - you'll want to refine this algorithm
        energy_usage = calculate_energy_usage(messages_df)
        
        # Group messages by model
        if "model" in messages_df.columns:
            models_count = messages_df.groupby("model").size().to_dict()
        else:
            models_count = {}
        
        # Placeholder for efficiency score (to be implemented)
        # In a real implementation, you'd have a scoring algorithm
        avg_score = 15.0  # Placeholder score out of 20
        
        return {
            "total_prompts": total_prompts,
            "average_score": avg_score,
            "energy_usage": energy_usage,
            "messages_by_model": models_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")

def calculate_energy_usage(messages_df):
    """
    Calculate estimated energy usage based on message count, model, and thinking time.
    This is a simplified placeholder - real implementation would use more sophisticated calculations.
    """
    # Constants for energy calculation (these would be based on research/measurements)
    BASE_COST_PER_MESSAGE = 0.001  # kWh
    THINKING_TIME_FACTOR = 0.0005  # kWh per second of thinking
    
    # Start with base cost for all messages
    total_energy = len(messages_df) * BASE_COST_PER_MESSAGE
    
    # Add cost based on thinking time
    assistant_messages = messages_df[messages_df["role"] == "assistant"]
    if "thinking_time" in assistant_messages.columns:
        thinking_time_sum = assistant_messages["thinking_time"].sum()
        thinking_energy = thinking_time_sum * THINKING_TIME_FACTOR
        total_energy += thinking_energy
    
    # In a real implementation, you would add model-specific factors
    # For example, GPT-4 might use more energy than GPT-3.5
    
    return round(total_energy, 3)

@router.get("/templates")
async def get_prompt_templates(user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Get user's saved prompt templates."""
    try:
        response = supabase.table("prompt_templates").select("*").eq("user_id", user_id).limit(10).execute()
        
        return {
            "success": True,
            "templates": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving templates: {str(e)}")

@router.get("/notifications")
async def get_notifications(user_id: str = Depends(supabase_helpers.get_user_from_session_token)):
    """Get user notifications."""
    try:
        response = supabase.table("notifications").select("*").eq("user_id", user_id).eq("read_at", None).order("created_at", desc=True).limit(5).execute()
        
        return {
            "success": True,
            "notifications": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving notifications: {str(e)}")