from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, save
app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)
app.include_router(save.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
