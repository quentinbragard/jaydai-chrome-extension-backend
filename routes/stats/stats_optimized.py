# routes/stats/stats_optimized.py
"""
Optimized stats endpoint with caching and parallel processing
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from utils.supabase_helpers import get_user_from_session_token
from utils.cache.redis_cache import cached
from utils.database.query_optimizer import time_query
import asyncio
import logging
import time

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/user/optimized")
@cached(ttl=300, key_prefix="user_stats")  # Cache for 5 minutes
async def get_user_stats_optimized(user_id: str = Depends(get_user_from_session_token)):
    """
    Optimized user stats with parallel queries and caching
    """
    try:
        start_time = time.time()
        current_date = datetime.now()
        last_week_date = current_date - timedelta(days=7)
        
        # Define all queries as async tasks
        async def get_chats():
            return await asyncio.to_thread(
                lambda: supabase.table("chats")
                .select("id, created_at")
                .eq("user_id", user_id)
                .execute()
            )
        
        async def get_messages():
            return await asyncio.to_thread(
                lambda: supabase.table("messages")
                .select("id, chat_provider_id, role, content, created_at, model")
                .eq("user_id", user_id)
                .execute()
            )
        
        # Execute all queries in parallel
        chats_task, messages_task = await asyncio.gather(
            get_chats(),
            get_messages()
        )
        
        # Process results
        chats = chats_task.data or []
        messages = messages_task.data or []
        
        query_time = (time.time() - start_time) * 1000
        logger.info(f"Parallel stats queries took {query_time:.2f}ms")
        
        # Fast processing (same logic as original but optimized)
        total_chats = len(chats)
        total_messages = len(messages)
        
        # Calculate message counts per chat using dict comprehension
        conv_msg_counts = {}
        for msg in messages:
            chat_id = msg.get("chat_provider_id")
            if chat_id:
                conv_msg_counts[chat_id] = conv_msg_counts.get(chat_id, 0) + 1
        
        avg_messages_per_chat = round(total_messages / total_chats, 2) if total_chats else 0
        
        # Token calculation with vectorized operations
        from utils.stats.estimate_tokens import estimate_tokens
        
        recent_cutoff = last_week_date.strftime('%Y-%m-%d')
        token_stats = calculate_token_stats_fast(messages, recent_cutoff)
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Total optimized stats calculation took {total_time:.2f}ms")
        
        return {
            "total_chats": total_chats,
            "total_messages": total_messages,
            "avg_messages_per_chat": avg_messages_per_chat,
            "token_usage": token_stats,
            "processing_time_ms": round(total_time, 2)
        }
        
    except Exception as e:
        logger.error(f"Error in optimized stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting optimized stats: {str(e)}")

def calculate_token_stats_fast(messages: List[Dict], recent_cutoff: str) -> Dict:
    """Fast token calculation using list comprehensions"""
    from utils.stats.estimate_tokens import estimate_tokens
    
    # Separate user and AI messages with single pass
    user_messages = []
    ai_messages = []
    recent_user_messages = []
    recent_ai_messages = []
    
    for msg in messages:
        content = msg.get("content", "")
        model = msg.get("model", "default")
        is_recent = msg.get("created_at", "") >= recent_cutoff
        
        if msg.get("role") == "user":
            tokens = estimate_tokens(content, model)
            user_messages.append(tokens)
            if is_recent:
                recent_user_messages.append(tokens)
        else:
            tokens = estimate_tokens(content, model)
            ai_messages.append(tokens)
            if is_recent:
                recent_ai_messages.append(tokens)
    
    # Calculate totals
    total_input = sum(user_messages)
    total_output = sum(ai_messages)
    recent_input = sum(recent_user_messages)
    recent_output = sum(recent_ai_messages)
    
    return {
        "total": total_input + total_output,
        "total_input": total_input,
        "total_output": total_output,
        "recent": recent_input + recent_output,
        "recent_input": recent_input,
        "recent_output": recent_output
    }