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
    
    # AEraLogIn OAuth (Experimental - Wallet/NFT based auth)
    AERA_CLIENT_ID: str = os.getenv("AERA_CLIENT_ID", "aera_4042836bd8852b520f9f2b5448446627")
    AERA_CLIENT_SECRET: str = os.getenv("AERA_CLIENT_SECRET", "ke5v3GF9CA1-KBWlvG9l8qyudAnuXeHb0SqH3T5RdqQ")
    
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8000")
    
    UPLOAD_DIR: str = "uploads"

settings = Settings()
