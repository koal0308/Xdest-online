from fastapi import APIRouter, Request, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.auth import oauth
from app.config import settings
from app.encryption import encrypt_token
from datetime import datetime
import httpx
import secrets
import hashlib
import hmac
from urllib.parse import urlencode, quote

router = APIRouter(prefix="/auth", tags=["auth"])

# Secret for signing link_user cookie
LINK_STATE_SECRET = settings.SECRET_KEY.encode()

def sign_user_id(user_id: int) -> str:
    """Create a signed token for user_id"""
    message = f"link:{user_id}".encode()
    signature = hmac.new(LINK_STATE_SECRET, message, hashlib.sha256).hexdigest()[:16]
    return f"link_{user_id}_{signature}"

def verify_user_id(signed_value: str) -> int | None:
    """Verify and extract user_id from signed value"""
    if not signed_value or not signed_value.startswith("link_"):
        return None
    try:
        parts = signed_value.split("_")
        if len(parts) != 3:
            return None
        user_id = int(parts[1])
        expected = sign_user_id(user_id)
        if hmac.compare_digest(signed_value, expected):
            return user_id
    except (ValueError, IndexError):
        pass
    return None

@router.get("/github/link")
async def github_link(request: Request):
    """Special endpoint for linking GitHub to existing account - sets cookie and goes to GitHub"""
    current_user_id = request.session.get('user_id')
    
    redirect_uri = f"{settings.APP_URL}/auth/github/callback"
    
    # Get the OAuth redirect response
    oauth_response = await oauth.github.authorize_redirect(request, redirect_uri)
    
    # If user is logged in, set the linking cookie on the OAuth response
    if current_user_id:
        signed_cookie = sign_user_id(current_user_id)
        oauth_response.set_cookie(
            key="github_link_user",
            value=signed_cookie,
            max_age=600,  # 10 minutes
            httponly=True,
            secure=True,
            samesite="lax"
        )
    
    return oauth_response

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
    
    # Check if we're linking GitHub to an existing account via signed cookie
    link_cookie = request.cookies.get('github_link_user', '')
    link_user_id = verify_user_id(link_cookie)
    logged_in_user = None
    if link_user_id:
        logged_in_user = db.query(User).filter(User.id == link_user_id).first()
    
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
    
    # Check if user exists by GitHub ID
    user = db.query(User).filter(
        User.provider == "github",
        User.provider_id == str(github_user['id'])
    ).first()
    
    email_to_use = primary_email or github_user.get('email', f"{github_user['id']}@github.local")
    is_new_user = False
    
    # Priority 1: If user is already logged in, link GitHub to their account
    if logged_in_user and not logged_in_user.github_token:
        # Link GitHub to currently logged-in user
        logged_in_user.github_token = encrypt_token(token['access_token'])
        logged_in_user.github = github_user.get('html_url')
        logged_in_user.role = "developer"  # Upgrade to developer when linking GitHub
        if not logged_in_user.avatar or logged_in_user.avatar == '/static/default-avatar.png':
            logged_in_user.avatar = github_user.get('avatar_url')
        db.commit()
        user = logged_in_user
    elif not user:
        # Check if email already exists (user registered with different provider)
        existing_user = db.query(User).filter(User.email == email_to_use).first()
        if existing_user:
            # User already registered with different provider - update their GitHub info and log them in
            existing_user.github_token = encrypt_token(token['access_token'])
            existing_user.github = github_user.get('html_url')
            existing_user.role = "developer"  # Upgrade to developer when linking GitHub
            if not existing_user.avatar:
                existing_user.avatar = github_user.get('avatar_url')
            db.commit()
            user = existing_user
        else:
            # Create new user
            is_new_user = True
            username = github_user.get('login', f"user_{github_user['id']}")
            # Ensure unique username
            base_username = username
            counter = 1
            while db.query(User).filter(User.username == username).first():
                username = f"{base_username}_{counter}"
                counter += 1
            
            user = User(
                username=username,
                email=email_to_use,
                avatar=github_user.get('avatar_url'),
                github=github_user.get('html_url'),
                github_token=encrypt_token(token['access_token']),
                bio=github_user.get('bio'),
                provider="github",
                provider_id=str(github_user['id']),
                role="developer",  # GitHub users are developers
                terms_accepted_at=None  # Will be set when user accepts terms in profile setup
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
    
    # Redirect new users or users who haven't accepted terms to profile setup
    if is_new_user or not user.terms_accepted_at:
        response = RedirectResponse(url="/profile/edit?setup=true", status_code=302)
    else:
        response = RedirectResponse(url="/dashboard", status_code=302)
    
    # Clear the link cookie
    response.delete_cookie("github_link_user")
    return response

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
            is_new_user = False
        else:
            # Create new user
            is_new_user = True
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
                role="tester",  # Google users are testers (cannot create projects)
                terms_accepted_at=None  # Will be set when user accepts terms in profile setup
            )
            db.add(user)
            db.commit()
            db.refresh(user)
    else:
        is_new_user = False
    
    # Set session
    request.session['user_id'] = user.id
    request.session['username'] = user.username
    
    # Redirect new users or users who haven't accepted terms to profile setup
    if is_new_user or not user.terms_accepted_at:
        return RedirectResponse(url="/profile/edit?setup=true", status_code=302)
    
    return RedirectResponse(url="/dashboard", status_code=302)

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


# ==================== AEraLogIn OAuth (Experimental) ====================
# Wallet/NFT based authentication using AEraLogIn OAuth 2.0

@router.get("/aera")
async def aera_login(request: Request):
    """Initiate AEraLogIn OAuth flow"""
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    request.session['aera_oauth_state'] = state
    
    redirect_uri = f"{settings.APP_URL}/auth/aera/callback"
    
    # Build authorization URL with proper encoding
    params = {
        "client_id": settings.AERA_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state
    }
    
    auth_url = f"https://aeralogin.com/oauth/authorize?{urlencode(params)}"
    
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/aera/callback")
async def aera_callback(request: Request, code: str = None, state: str = None, error: str = None, db: Session = Depends(get_db)):
    """Handle AEraLogIn OAuth callback"""
    
    # Check for OAuth errors
    if error:
        raise HTTPException(status_code=400, detail=f"AEra OAuth error: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received")
    
    # Validate state (CSRF protection)
    stored_state = request.session.get('aera_oauth_state')
    if not stored_state or state != stored_state:
        raise HTTPException(status_code=403, detail="Invalid state parameter - possible CSRF attack")
    
    # Clear the stored state
    del request.session['aera_oauth_state']
    
    redirect_uri = f"{settings.APP_URL}/auth/aera/callback"
    
    # Exchange authorization code for access token
    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post(
                "https://aeralogin.com/oauth/token",
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": settings.AERA_CLIENT_ID,
                    "client_secret": settings.AERA_CLIENT_SECRET
                },
                timeout=30.0
            )
            token_data = token_response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to exchange token: {str(e)}")
    
    # Check for token exchange errors
    if "error" in token_data:
        raise HTTPException(status_code=400, detail=f"Token error: {token_data.get('error_description', token_data['error'])}")
    
    # Extract user data from token response
    wallet_address = token_data.get("wallet")
    score = token_data.get("score", 0)
    has_nft = token_data.get("has_nft", False)
    access_token = token_data.get("access_token")
    
    if not wallet_address:
        raise HTTPException(status_code=400, detail="No wallet address in response")
    
    # Normalize wallet address (lowercase for consistency)
    wallet_address = wallet_address.lower()
    
    # Check if user exists by AEra wallet
    user = db.query(User).filter(
        User.provider == "aera",
        User.provider_id == wallet_address
    ).first()
    
    is_new_user = False
    
    if not user:
        is_new_user = True
        # Create username from wallet address
        short_wallet = wallet_address[:6] + "..." + wallet_address[-4:]
        username = f"aera_{wallet_address[:8]}"
        
        # Ensure unique username
        base_username = username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}_{counter}"
            counter += 1
        
        # Create new user
        # NFT holders get developer role, others get tester role
        user_role = "developer" if has_nft else "tester"
        
        # Create descriptive bio for AEra users
        if has_nft:
            bio = f"🌀 AEra Identity\nGenesis builder identity (experimental)\nResonance Score: {score}"
        else:
            bio = f"🌀 AEra User\nEarly builder identity (experimental)\nResonance Score: {score}"
        
        user = User(
            username=username,
            email=f"{wallet_address[:10]}@aera.local",  # Placeholder email
            avatar=None,  # AEra doesn't provide avatars
            bio=bio,
            provider="aera",
            provider_id=wallet_address,
            role=user_role,
            terms_accepted_at=None
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update score in bio for existing users
        if has_nft:
            user.bio = f"🌀 AEra Identity\nGenesis builder identity (experimental)\nResonance Score: {score}"
            user.role = "developer"  # Upgrade to developer if they now have NFT
        else:
            user.bio = f"🌀 AEra User\nEarly builder identity (experimental)\nResonance Score: {score}"
        db.commit()
    
    # Set session
    request.session['user_id'] = user.id
    request.session['username'] = user.username
    request.session['aera_token'] = access_token  # Store for potential API calls
    request.session['aera_wallet'] = wallet_address
    request.session['aera_score'] = score
    request.session['aera_has_nft'] = has_nft
    
    # Redirect new users to profile setup
    if is_new_user or not user.terms_accepted_at:
        return RedirectResponse(url="/profile/edit?setup=true", status_code=302)
    
    return RedirectResponse(url="/dashboard", status_code=302)
