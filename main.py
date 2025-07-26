# main.py - UPDATED with analytics route

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, save, stats, notifications, prompts, user, organizations, onboarding, stripe, share, analytics
import time
import json
from supabase import create_client, Client
import os
import dotenv
import logging
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
except ImportError:  # Sentry is optional for tests
    sentry_sdk = None
from utils.middleware import AccessControlMiddleware
from utils.logging import StructuredLogging
from utils.amplitude_init import init_amplitude

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if sentry_sdk is not None:
    dsn = os.getenv("SENTRY_DSN")
    if dsn:
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FastApiIntegration()],
            send_default_pii=True,
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0")),
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle application lifespan events.
    This replaces the deprecated @app.on_event decorators.
    """
    # Startup events
    logger.info("Starting up Jaydai API...")
    
    # Initialize Amplitude
    if not init_amplitude():
        logger.warning("Amplitude initialization failed - analytics will not work")
    else:
        logger.info("Amplitude successfully initialized")
    
    # You can add other startup tasks here
    # For example: database connections, cache warming, etc.
    try:
        # Test database connection
        supabase_client = create_client(
            os.getenv("SUPABASE_URL"), 
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        )
        supabase_client.storage.list_buckets()
        logger.info("Database connection verified")
 
        
    except Exception as e:
        logger.error(f"Startup verification failed: {str(e)}")
    
    logger.info("Jaydai API startup completed successfully")
    
    # Application is running - yield control to FastAPI
    yield
    
    # Shutdown events
    logger.info("Shutting down Jaydai API...")
    
    
    # Add any cleanup tasks here
    # For example: close database connections, save state, etc.
    
    logger.info("Jaydai API shutdown completed")

# Create FastAPI app with lifespan handler
app = FastAPI(lifespan=lifespan)

if sentry_sdk is not None and sentry_sdk.Hub.current.client:
    app.add_middleware(SentryAsgiMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jayd.ai", "https://www.jayd.ai", "chrome-extension://enfcjmbdbldomiobfndablekgdkmcipd", "https://chatgpt.com", "https://claude.ai", "https://chat.mistral.ai", "https://copilot.microsoft.com"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

app.add_middleware(StructuredLogging)
app.add_middleware(AccessControlMiddleware)

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
app.include_router(analytics.router)  # Add the new analytics router

@app.get("/")
async def root():
    return {"message": "Welcome to Jaydai API", "status": "running"}

@app.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1 / 0

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring - no auth required."""
    start_time = time.time()
    health = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "components": {}
    }
    
    # Check API
    health["components"]["api"] = {"status": "healthy"}
    
    # Check Supabase connection
    try:
        # Create a fresh client for the health check
        supabase_client = create_client(
            os.getenv("SUPABASE_URL"), 
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        )
        
        # Try listing buckets - this is a lightweight operation
        # that doesn't depend on application-specific tables
        supabase_client.storage.list_buckets()
        
        health["components"]["database"] = {
            "status": "healthy",
            "responseTime": f"{(time.time() - start_time) * 1000:.2f}ms"
        }
    except Exception as e:
        health["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health["status"] = "degraded"
    
    # Check Amplitude connection (optional)
    try:
        from utils.amplitude import amplitude_service
        if amplitude_service._client:
            health["components"]["amplitude"] = {"status": "healthy"}
        else:
            health["components"]["amplitude"] = {"status": "not_configured"}
    except Exception as e:
        health["components"]["amplitude"] = {
            "status": "unhealthy", 
            "error": str(e)
        }
    
    # Set appropriate status code based on overall health
    if health["status"] != "healthy":
        return Response(content=json.dumps(health), media_type="application/json", status_code=503)
    
    return health

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)