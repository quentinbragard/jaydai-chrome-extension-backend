# main.py - UPDATED with Share functionality

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, save, stats, notifications, prompts, user, organizations, onboarding, stripe, share
import time
import json
from supabase import create_client, Client
import os
import dotenv
import logging
import sentry_sdk
from utils.middleware import AccessControlMiddleware
from utils.logging import StructuredLogging

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO)

sentry_sdk.init(
    dsn="https://9536439a3ab8cc91748a9b3b04b1d441@o4509722413301760.ingest.de.sentry.io/4509722415726672",
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
    traces_sample_rate=1.0,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jayd.ai", "https://www.jayd.ai", "chrome-extension://enfcjmbdbldomiobfndablekgdkmcipd", "https://chatgpt.com", "https://claude.ai", "https://chat.mistral.ai", "https://copilot.microsoft.com"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

app.add_middleware(StructuredLogging)

# ADD THIS MIDDLEWARE REGISTRATION
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
# ADD THIS LINE - Include Share router
app.include_router(share.router)

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
    
    # Set appropriate status code based on overall health
    if health["status"] != "healthy":
        return Response(content=json.dumps(health), media_type="application/json", status_code=503)
    
    return health

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)