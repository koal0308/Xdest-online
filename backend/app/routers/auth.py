from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.auth import oauth
from app.config import settings
from app.encryption import encrypt_token
import httpx

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/github")
async def github_login(request: Request):
    redirect_uri = f"{settings.APP_URL}/auth/github/callback"
    return await oauth.github.authorize_redirect(request, redirect_uri)

@router.get("/github/callback")
async def github_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.github.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")
    
    # Get user info from GitHub
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {token['access_token']}"}
        )
        github_user = resp.json()
        
        # Get email
        email_resp = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {token['access_token']}"}
        )
        emails = email_resp.json()
        primary_email = next((e['email'] for e in emails if e['primary']), None)
    
    # Check if user exists
    user = db.query(User).filter(
        User.provider == "github",
        User.provider_id == str(github_user['id'])
    ).first()
    
    if not user:
        # Create new user
        username = github_user.get('login', f"user_{github_user['id']}")
        # Ensure unique username
        base_username = username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}_{counter}"
            counter += 1
        
        user = User(
            username=username,
            email=primary_email or github_user.get('email', f"{github_user['id']}@github.local"),
            avatar=github_user.get('avatar_url'),
            github=github_user.get('html_url'),
            github_token=encrypt_token(token['access_token']),
            bio=github_user.get('bio'),
            provider="github",
            provider_id=str(github_user['id']),
            role="developer"  # GitHub users are developers
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update token for existing user
        user.github_token = encrypt_token(token['access_token'])
        db.commit()
    
    # Set session
    request.session['user_id'] = user.id
    request.session['username'] = user.username
    
    return RedirectResponse(url="/dashboard", status_code=302)

@router.get("/google")
async def google_login(request: Request):
    redirect_uri = f"{settings.APP_URL}/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")
    
    user_info = token.get('userinfo')
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")
    
    # Check if user exists by provider
    user = db.query(User).filter(
        User.provider == "google",
        User.provider_id == str(user_info['sub'])
    ).first()
    
    if not user:
        # Check if email already exists (user registered with different provider)
        existing_user = db.query(User).filter(User.email == user_info.get('email')).first()
        if existing_user:
            # Link this Google account to existing user by logging them in
            user = existing_user
        else:
            # Create new user
            username = user_info.get('name', '').replace(' ', '_').lower() or f"user_{user_info['sub'][:8]}"
            # Ensure unique username
            base_username = username
            counter = 1
            while db.query(User).filter(User.username == username).first():
                username = f"{base_username}_{counter}"
                counter += 1
            
            user = User(
                username=username,
                email=user_info.get('email'),
                avatar=user_info.get('picture'),
                provider="google",
                provider_id=str(user_info['sub']),
                role="tester"  # Google users are testers (cannot create projects)
            )
            db.add(user)
            db.commit()
            db.refresh(user)
    
    # Set session
    request.session['user_id'] = user.id
    request.session['username'] = user.username
    
    return RedirectResponse(url="/dashboard", status_code=302)

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)
