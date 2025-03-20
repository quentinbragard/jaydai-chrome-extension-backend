from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, save, stats, notifications, prompt, user

app = FastAPI()

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# Include all routers
app.include_router(auth.router)
app.include_router(save.router)
app.include_router(stats.router)
app.include_router(prompt.router)
app.include_router(notifications.router)
app.include_router(user.router)

@app.get("/")
async def root():
    return {"message": "Welcome to Archimind API", "status": "running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)