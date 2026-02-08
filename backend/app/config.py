import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # SQLite als Default (einfacher für lokale Entwicklung)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./devplatform.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8000")
    
    UPLOAD_DIR: str = "uploads"

settings = Settings()
