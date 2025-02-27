from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, save, stats, prompt_generator, notifications

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
app.include_router(prompt_generator.router)
app.include_router(notifications.router)

@app.get("/")
async def root():
    return {"message": "Welcome to Archimind API", "status": "running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)