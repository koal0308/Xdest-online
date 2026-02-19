from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import os

from app.config import settings
from app.database import engine, Base
from app.routers import auth, pages, api

# Create database tables
Base.metadata.create_all(bind=engine)

# Create upload directories
os.makedirs("uploads/projects", exist_ok=True)
os.makedirs("uploads/posts", exist_ok=True)
os.makedirs("uploads/avatars", exist_ok=True)
os.makedirs("static", exist_ok=True)

app = FastAPI(title="Xdest", version="1.0.0")

# Add session middleware with secure cookie settings for HTTPS
app.add_middleware(
    SessionMiddleware, 
    secret_key=settings.SECRET_KEY,
    https_only=True,
    same_site="lax"
)

# Mount static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(api.router)

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return RedirectResponse(url="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
