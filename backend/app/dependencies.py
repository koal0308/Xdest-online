from fastapi import Request
from fastapi.responses import RedirectResponse
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

async def require_terms_accepted(request: Request, db: Session) -> User | RedirectResponse:
    """Get current user and ensure terms are accepted, redirects to profile setup if not"""
    user = await get_current_user_optional(request, db)
    if not user:
        return None
    if not user.terms_accepted_at:
        # User hasn't accepted terms yet, redirect to profile setup
        return RedirectResponse(url="/profile/edit?setup=true", status_code=302)
    return user
