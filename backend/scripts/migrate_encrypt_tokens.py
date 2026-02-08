#!/usr/bin/env python3
"""
Migration script to encrypt existing tokens in the database.
Run this once after deploying the encryption feature.

Usage:
    cd /home/karlheinz/dest/backend
    source venv/bin/activate
    python scripts/migrate_encrypt_tokens.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user import User
from app.models.project import Project
from app.encryption import encrypt_token, is_encrypted

def migrate_tokens():
    db = SessionLocal()
    
    try:
        # Migrate user GitHub tokens
        users = db.query(User).filter(User.github_token.isnot(None)).all()
        user_count = 0
        for user in users:
            if user.github_token and not is_encrypted(user.github_token):
                print(f"Encrypting GitHub token for user: {user.username}")
                user.github_token = encrypt_token(user.github_token)
                user_count += 1
        
        # Migrate project Plausible API keys
        projects = db.query(Project).filter(Project.plausible_api_key.isnot(None)).all()
        project_count = 0
        for project in projects:
            if project.plausible_api_key and not is_encrypted(project.plausible_api_key):
                print(f"Encrypting Plausible API key for project: {project.name}")
                project.plausible_api_key = encrypt_token(project.plausible_api_key)
                project_count += 1
        
        db.commit()
        
        print(f"\n✅ Migration complete!")
        print(f"   - Encrypted {user_count} GitHub tokens")
        print(f"   - Encrypted {project_count} Plausible API keys")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("🔐 Token Encryption Migration")
    print("=" * 40)
    migrate_tokens()
