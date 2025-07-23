# utils/cache/redis_cache.py
import json
import redis
import logging
import hashlib
from typing import Any, Optional, Dict, List
from datetime import timedelta
import os
import asyncio
from functools import wraps

logger = logging.getLogger("cache")

class RedisCache:
    def __init__(self):
        # For Cloud Run, use Redis Cloud or Memorystore
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()  # Test connection
            self.enabled = True
            logger.info("Redis cache initialized successfully")
        except Exception as e:
            logger.warning(f"Redis not available, caching disabled: {str(e)}")
            self.enabled = False
            self.redis_client = None
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from prefix and parameters"""
        key_data = f"{prefix}:{str(args)}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.enabled:
            return None
        
        try:
            value = await asyncio.to_thread(self.redis_client.get, key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get error: {str(e)}")
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL"""
        if not self.enabled:
            return False
        
        try:
            serialized = json.dumps(value, default=str)
            await asyncio.to_thread(
                self.redis_client.setex, 
                key, 
                ttl, 
                serialized
            )
            return True
        except Exception as e:
            logger.error(f"Cache set error: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.enabled:
            return False
        
        try:
            await asyncio.to_thread(self.redis_client.delete, key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {str(e)}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.enabled:
            return 0
        
        try:
            keys = await asyncio.to_thread(self.redis_client.keys, pattern)
            if keys:
                return await asyncio.to_thread(self.redis_client.delete, *keys)
        except Exception as e:
            logger.error(f"Cache delete pattern error: {str(e)}")
        return 0

# Global cache instance
cache = RedisCache()

def cached(ttl: int = 300, key_prefix: str = "default"):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user_id if it's the first argument
            cache_key_parts = [key_prefix, func.__name__]
            if args:
                cache_key_parts.append(str(args[0]))  # Usually user_id
            
            cache_key = "_".join(cache_key_parts)
            
            # Try to get from cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache.set(cache_key, result, ttl)
            logger.debug(f"Cached result for {cache_key}")
            
            return result
        return wrapper
    return decorator

# Cache invalidation helpers
class CacheInvalidator:
    @staticmethod
    async def invalidate_user_cache(user_id: str):
        """Invalidate all cache entries for a user"""
        patterns = [
            f"folders_{user_id}_*",
            f"templates_{user_id}_*",
            f"blocks_{user_id}_*",
            f"user_metadata_{user_id}*",
            f"stats_{user_id}*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            deleted = await cache.delete_pattern(pattern)
            total_deleted += deleted
        
        logger.info(f"Invalidated {total_deleted} cache entries for user {user_id}")
        return total_deleted
    
    @staticmethod
    async def invalidate_template_cache(template_id: int):
        """Invalidate cache when template is modified"""
        await cache.delete_pattern(f"templates_*")
        await cache.delete_pattern(f"folders_*")  # Templates affect folder contents
    
    @staticmethod
    async def invalidate_folder_cache(folder_id: int):
        """Invalidate cache when folder is modified"""
        await cache.delete_pattern(f"folders_*")

# Pre-warming cache for common queries
class CacheWarmer:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
    
    async def warm_user_cache(self, user_id: str):
        """Pre-load common user data into cache"""
        try:
            # Pre-load user metadata
            metadata_key = f"user_metadata_{user_id}"
            if not await cache.get(metadata_key):
                metadata = self.supabase.table("users_metadata") \
                    .select("*") \
                    .eq("user_id", user_id) \
                    .single() \
                    .execute()
                await cache.set(metadata_key, metadata.data, ttl=600)
            
            # Pre-load pinned folders
            folders_key = f"folders_{user_id}_pinned"
            if not await cache.get(folders_key):
                # This would call your optimized folder query
                pass
                
        except Exception as e:
            logger.error(f"Cache warming failed for user {user_id}: {str(e)}")

# Usage examples for your routes
@cached(ttl=300, key_prefix="user_folders")
async def cached_get_user_folders(user_id: str, locale: str = "en"):
    """Cached version of get user folders"""
    # Your existing folder fetching logic here
    pass

@cached(ttl=600, key_prefix="user_stats") 
async def cached_get_user_stats(user_id: str):
    """Cached version of user stats"""
    # Your existing stats logic here
    pass