# main.py - Optimized version
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from routes import auth, save, stats, notifications, prompts, user, organizations, onboarding, stripe, share
import time
import json
import logging
import os
import asyncio
from contextlib import asynccontextmanager
from supabase import create_client, Client
import dotenv

# Import optimization middleware
from utils.middleware.performance_monitoring import PerformanceMonitoringMiddleware, get_performance_metrics
from utils.cache.redis_cache import cache, CacheWarmer
from utils.database.query_optimizer import BatchOperations
from utils.monitoring.prometheus_metrics import PrometheusMiddleware, add_metrics_endpoint


dotenv.load_dotenv()

# Configure logging for performance monitoring
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables for optimization
supabase_client = None
batch_operations = None
cache_warmer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management with initialization"""
    global supabase_client, batch_operations, cache_warmer
    
    # Startup
    logger.info("Starting application with optimizations...")
    
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if supabase_url and supabase_key:
        supabase_client = create_client(supabase_url, supabase_key)
        batch_operations = BatchOperations(supabase_client)
        cache_warmer = CacheWarmer(supabase_client)
        logger.info("Database connections initialized")
    
    # Warm up critical connections
    try:
        if supabase_client:
            # Test database connection
            supabase_client.storage.list_buckets()
            logger.info("Database connection validated")
        
        # Test cache connection
        await cache.set("health_check", "ok", ttl=60)
        cached_value = await cache.get("health_check")
        if cached_value == "ok":
            logger.info("Cache connection validated")
    except Exception as e:
        logger.warning(f"Startup validation failed: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Jaydai API - Optimized",
    description="High-performance AI prompt management API",
    version="2.0.0",
    lifespan=lifespan
)


# Add optimization middleware (order matters!)
app.add_middleware(GZipMiddleware, minimum_size=1000)  # Compress responses > 1KB
app.add_middleware(PerformanceMonitoringMiddleware, threshold_ms=1000)

# Add Prometheus middleware
app.add_middleware(PrometheusMiddleware, app_name="jaydai_api")

# Add metrics endpoint
add_metrics_endpoint(app)

app.add_middleware(
    CORSMiddleware, 
    allow_origins=[
        "https://jayd.ai", 
        "https://www.jayd.ai", 
        "chrome-extension://enfcjmbdbldomiobfndablekgdkmcipd", 
        "https://chatgpt.com", 
        "https://claude.ai", 
        "https://chat.mistral.ai", 
        "https://copilot.microsoft.com"
    ], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# Include all routers
app.include_router(auth.router)
app.include_router(save.router)
app.include_router(stats.router)
app.include_router(notifications.router)
app.include_router(user.router)
app.include_router(prompts.router)
app.include_router(organizations.router, prefix="/organizations")
app.include_router(onboarding.router, prefix="/onboarding")
app.include_router(stripe.router)
app.include_router(share.router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to Jaydai API - Optimized", 
        "status": "running",
        "version": "1.1.1",
        "optimizations": ["caching", "batch_queries", "monitoring", "compression"]
    }

@app.get("/health")
async def health_check():
    """Enhanced health check with performance metrics."""
    start_time = time.time()
    health = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.1.1",
        "components": {},
        "performance": {}
    }
    
    # Check API
    health["components"]["api"] = {"status": "healthy"}
    
    # Check Supabase connection
    try:
        if supabase_client:
            supabase_client.storage.list_buckets()
            db_response_time = (time.time() - start_time) * 1000
            health["components"]["database"] = {
                "status": "healthy",
                "responseTime": f"{db_response_time:.2f}ms"
            }
        else:
            health["components"]["database"] = {"status": "not_configured"}
    except Exception as e:
        health["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health["status"] = "degraded"
    
    # Check cache
    try:
        cache_start = time.time()
        await cache.set("health_check", "test", ttl=10)
        cached_value = await cache.get("health_check")
        cache_response_time = (time.time() - cache_start) * 1000
        
        if cached_value == "test":
            health["components"]["cache"] = {
                "status": "healthy",
                "responseTime": f"{cache_response_time:.2f}ms"
            }
        else:
            health["components"]["cache"] = {"status": "unhealthy"}
    except Exception as e:
        health["components"]["cache"] = {
            "status": "degraded",
            "error": str(e)
        }
    
    # Add basic performance metrics
    health["performance"]["total_response_time"] = f"{(time.time() - start_time) * 1000:.2f}ms"
    
    # Set appropriate status code
    if health["status"] != "healthy":
        return Response(
            content=json.dumps(health), 
            media_type="application/json", 
            status_code=503
        )
    
    return health

@app.get("/metrics")
async def get_metrics():
    """Performance metrics endpoint for monitoring"""
    try:
        metrics = await get_performance_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

@app.post("/cache/invalidate/{user_id}")
async def invalidate_user_cache(user_id: str):
    """Manual cache invalidation endpoint (admin only in production)"""
    try:
        from utils.cache.redis_cache import CacheInvalidator
        deleted_count = await CacheInvalidator.invalidate_user_cache(user_id)
        return {
            "success": True,
            "message": f"Invalidated {deleted_count} cache entries for user {user_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache invalidation failed: {str(e)}")

@app.post("/cache/warm/{user_id}")
async def warm_user_cache(user_id: str):
    """Cache warming endpoint for important users"""
    try:
        if cache_warmer:
            await cache_warmer.warm_user_cache(user_id)
            return {"success": True, "message": f"Cache warmed for user {user_id}"}
        else:
            return {"success": False, "message": "Cache warmer not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache warming failed: {str(e)}")

# Error handling middleware
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with performance logging"""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}")
    
    return Response(
        content=json.dumps({
            "error": "Internal server error",
            "path": request.url.path,
            "method": request.method
        }),
        status_code=500,
        media_type="application/json"
    )

if __name__ == "__main__":
    import uvicorn
    
    # Optimized uvicorn settings for local development
    uvicorn.run(
        "main:app",
        host="0.0.0.0", 
        port=8000,
        reload=False,  # Disable reload for better performance
        workers=1,  # Single worker for development
        access_log=True,
        log_level="info"
    )