from fastapi import Request
from sqlalchemy.orm import Session
from app.models.user import User

async def get_current_user_optional(request: Request, db: Session) -> User | None:
    """Get current user from session, returns None if not logged in"""
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()

async def get_current_user(request: Request, db: Session) -> User | None:
    """Get current user, raises redirect if not logged in"""
    return await get_current_user_optional(request, db)
