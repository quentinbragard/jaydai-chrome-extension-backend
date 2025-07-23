# utils/database/query_optimizer.py
import time
import logging
from functools import wraps
from typing import List, Dict, Any, Optional
from supabase import Client
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("db_performance")

class QueryOptimizer:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.query_cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    def log_slow_query(self, query_info: Dict[str, Any], duration_ms: float):
        """Log slow database queries for analysis"""
        if duration_ms > 1000:  # Log queries > 1 second
            logger.warning(f"Slow query detected: {query_info['table']} - {duration_ms:.2f}ms")
            logger.warning(f"Query details: {query_info}")

def time_query(func):
    """Decorator to time database queries"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        duration_ms = (time.time() - start_time) * 1000
        
        # Extract query info from function name and args
        query_info = {
            'function': func.__name__,
            'args': str(args)[:100],  # Truncate for logging
            'duration_ms': duration_ms
        }
        
        if duration_ms > 500:  # Log queries > 500ms
            logger.warning(f"Slow query: {func.__name__} took {duration_ms:.2f}ms")
        
        return result
    return wrapper

# Optimized batch operations
class BatchOperations:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
    
    async def batch_fetch_templates_with_folders(self, user_id: str, locale: str = "en") -> Dict[str, Any]:
        """
        Optimized batch fetch of templates with folders in parallel
        """
        async def fetch_user_metadata():
            return self.supabase.table("users_metadata") \
                .select("pinned_folder_ids, organization_ids, company_id") \
                .eq("user_id", user_id) \
                .single() \
                .execute()
        
        async def fetch_folders():
            return self.supabase.table("prompt_folders") \
                .select("*") \
                .execute()
        
        async def fetch_templates():
            return self.supabase.table("prompt_templates") \
                .select("*") \
                .execute()
        
        # Execute all queries in parallel
        metadata_task, folders_task, templates_task = await asyncio.gather(
            asyncio.to_thread(fetch_user_metadata),
            asyncio.to_thread(fetch_folders),
            asyncio.to_thread(fetch_templates)
        )
        
        return {
            'metadata': metadata_task.data,
            'folders': folders_task.data,
            'templates': templates_task.data
        }
    
    async def optimized_get_folders_with_templates(self, user_id: str, locale: str = "en"):
        """
        Single optimized query instead of multiple round trips
        """
        # Use PostgreSQL JSON functions for better performance
        query = f"""
        SELECT 
            f.*,
            COALESCE(
                json_agg(
                    json_build_object(
                        'id', t.id,
                        'title', t.title,
                        'content', t.content,
                        'description', t.description,
                        'type', t.type,
                        'usage_count', t.usage_count,
                        'created_at', t.created_at
                    )
                ) FILTER (WHERE t.id IS NOT NULL), 
                '[]'::json
            ) as templates
        FROM prompt_folders f
        LEFT JOIN prompt_templates t ON f.id = t.folder_id
        WHERE f.user_id = '{user_id}' OR f.user_id IS NULL
        GROUP BY f.id, f.title, f.description, f.type, f.created_at, f.user_id, f.organization_id, f.company_id
        ORDER BY f.created_at DESC
        """
        
        # Execute raw SQL for better performance
        try:
            result = self.supabase.rpc('execute_raw_sql', {'query': query}).execute()
            return result.data
        except Exception as e:
            logger.error(f"Optimized query failed, falling back to multiple queries: {str(e)}")
            # Fallback to original method
            return await self.batch_fetch_templates_with_folders(user_id, locale)

# Connection pooling and caching
class CachedSupabaseClient:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.cache = {}
        self.cache_ttl = {}
        self.default_ttl = 300  # 5 minutes
    
    def _get_cache_key(self, table: str, query_params: Dict) -> str:
        """Generate cache key from table and params"""
        import hashlib
        key_string = f"{table}_{str(sorted(query_params.items()))}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid"""
        if cache_key not in self.cache_ttl:
            return False
        return time.time() < self.cache_ttl[cache_key]
    
    async def cached_select(self, table: str, select_fields: str, filters: Dict, ttl: int = None) -> Any:
        """Cached select query"""
        cache_key = self._get_cache_key(table, {'select': select_fields, **filters})
        
        # Check cache first
        if cache_key in self.cache and self._is_cache_valid(cache_key):
            logger.debug(f"Cache hit for {table}")
            return self.cache[cache_key]
        
        # Execute query
        start_time = time.time()
        query = self.supabase.table(table).select(select_fields)
        
        # Apply filters
        for key, value in filters.items():
            if key.startswith('eq_'):
                field = key[3:]  # Remove 'eq_' prefix
                query = query.eq(field, value)
            elif key.startswith('in_'):
                field = key[3:]  # Remove 'in_' prefix
                query = query.in_(field, value)
        
        result = query.execute()
        duration_ms = (time.time() - start_time) * 1000
        
        # Log slow queries
        if duration_ms > 500:
            logger.warning(f"Slow query on {table}: {duration_ms:.2f}ms")
        
        # Cache result
        ttl = ttl or self.default_ttl
        self.cache[cache_key] = result
        self.cache_ttl[cache_key] = time.time() + ttl
        
        return result
    
    def invalidate_cache(self, table: str = None):
        """Invalidate cache for specific table or all"""
        if table:
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(table)]
            for key in keys_to_remove:
                del self.cache[key]
                del self.cache_ttl[key]
        else:
            self.cache.clear()
            self.cache_ttl.clear()

# Optimized access control queries
async def get_user_accessible_items_batch(supabase: Client, user_id: str, item_type: str) -> List[Dict]:
    """
    Get all accessible items for a user in a single optimized query
    """
    # Get user metadata first
    metadata_resp = supabase.table("users_metadata") \
        .select("organization_ids, company_id") \
        .eq("user_id", user_id) \
        .single() \
        .execute()
    
    metadata = metadata_resp.data or {}
    org_ids = metadata.get("organization_ids", [])
    company_id = metadata.get("company_id")
    
    # Build WHERE conditions for a single query
    conditions = [f"user_id = '{user_id}'"]
    
    if company_id:
        conditions.append(f"company_id = '{company_id}'")
    
    if org_ids:
        org_list = "', '".join(org_ids)
        conditions.append(f"organization_id IN ('{org_list}')")
    
    # Add global items (no ownership)
    conditions.append("(user_id IS NULL AND company_id IS NULL AND organization_id IS NULL)")
    
    where_clause = " OR ".join(f"({cond})" for cond in conditions)
    
    # Execute single query
    table_name = f"prompt_{item_type}s"  # templates, folders, blocks
    query = f"SELECT * FROM {table_name} WHERE {where_clause} ORDER BY created_at DESC"
    
    try:
        result = supabase.rpc('execute_raw_sql', {'query': query}).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Batch access query failed: {str(e)}")
        return []