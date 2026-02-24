from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.user import User
from app.models.issue import Issue
from app.models.project import Project
from app.models.offer_redemption import OfferRedemption

# ==================== TEST KARMA SYSTEM ====================
# Fairness-System: Wer Issues für eigene Projekte empfangen will,
# muss auch Issues für andere Projekte schreiben.
# karma = issues_given (für fremde Projekte) - issues_received (auf eigene Projekte) - offer_penalties
# Bei karma < -5 werden empfangene Issues unsichtbar.
KARMA_LIMIT = -5

def calculate_test_karma(db: Session, user_id: int) -> dict:
    """Berechnet den Test-Karma-Score eines Users.
    
    System-Issues (source_platform='Xdest-System') werden NICHT gezählt.
    Offer penalties: -1 für jede überfällige, nicht erfüllte Offer-Obligation.
    Reversed penalties werden wieder ausgeglichen.
    
    Returns:
        dict mit: given, received, offer_penalties, karma, is_blocked, pending_obligations
    """
    # Issues die der User für FREMDE Projekte geschrieben hat (ohne System-Issues)
    issues_given = db.query(func.count(Issue.id)).join(
        Project, Issue.project_id == Project.id
    ).filter(
        Issue.user_id == user_id,
        Project.user_id != user_id,  # Nicht eigene Projekte
        Issue.source_platform != "Xdest-System"  # Keine automatischen Welcome-Issues
    ).scalar() or 0
    
    # Issues die ANDERE für die Projekte des Users geschrieben haben (ohne System-Issues)
    issues_received = db.query(func.count(Issue.id)).join(
        Project, Issue.project_id == Project.id
    ).filter(
        Project.user_id == user_id,
        Issue.user_id != user_id,  # Nicht selbst geschrieben
        Issue.source_platform != "Xdest-System"  # Keine automatischen Welcome-Issues
    ).scalar() or 0
    
    # Offer penalties: overdue + penalty applied + NOT reversed = -1 each
    offer_penalties = db.query(func.count(OfferRedemption.id)).filter(
        OfferRedemption.user_id == user_id,
        OfferRedemption.karma_penalty_applied == True,
        OfferRedemption.karma_penalty_reversed == False
    ).scalar() or 0
    
    # Count pending (unfulfilled) obligations
    pending_count = db.query(func.count(OfferRedemption.id)).filter(
        OfferRedemption.user_id == user_id,
        OfferRedemption.fulfilled == False
    ).scalar() or 0
    
    karma = issues_given - issues_received - offer_penalties
    
    return {
        "given": issues_given,
        "received": issues_received,
        "offer_penalties": offer_penalties,
        "pending_obligations": pending_count,
        "karma": karma,
        "is_blocked": karma < KARMA_LIMIT,
        "limit": KARMA_LIMIT
    }

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
