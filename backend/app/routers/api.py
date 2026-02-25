from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import User, Project, Post, Comment, Issue, IssueResponse, ResponseVote, Offer, OfferRedemption, Message, MessageReply, UserRating
from app.dependencies import get_current_user, get_current_user_optional, calculate_test_karma
from app.config import settings
from app.encryption import decrypt_token, encrypt_token
import os
import uuid
from pathlib import Path
from datetime import datetime
import httpx
import re
import json

router = APIRouter(prefix="/api", tags=["api"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}


def _fulfill_offer_obligation(db: Session, user_id: int, project_id: int):
    """Check if user has pending offer obligations for this project and fulfill them.
    Also reverses karma penalty if it was already applied."""
    pending = db.query(OfferRedemption).filter(
        OfferRedemption.user_id == user_id,
        OfferRedemption.project_id == project_id,
        OfferRedemption.fulfilled == False
    ).all()
    
    for redemption in pending:
        redemption.fulfilled = True
        redemption.fulfilled_at = datetime.utcnow()
        
        # If karma penalty was already applied, reverse it
        if redemption.karma_penalty_applied and not redemption.karma_penalty_reversed:
            redemption.karma_penalty_reversed = True
    
    if pending:
        db.commit()


def check_and_apply_karma_penalties(db: Session):
    """Check all overdue obligations and apply karma penalties.
    Called periodically or on relevant page loads."""
    overdue = db.query(OfferRedemption).filter(
        OfferRedemption.fulfilled == False,
        OfferRedemption.karma_penalty_applied == False,
        OfferRedemption.deadline < datetime.utcnow()
    ).all()
    
    for redemption in overdue:
        redemption.karma_penalty_applied = True
    
    if overdue:
        db.commit()
    
    return len(overdue)

# GitHub Issue Type Labels Mapping with colors
GITHUB_LABELS = {
    "bug": {"name": "bug", "color": "d73a4a", "description": "Something isn't working"},
    "feature": {"name": "enhancement", "color": "a2eeef", "description": "New feature or request"},
    "question": {"name": "question", "color": "d876e3", "description": "Further information is requested"},
    "security": {"name": "security", "color": "ff9800", "description": "Security related issue"},
    "docs": {"name": "documentation", "color": "0075ca", "description": "Improvements or additions to documentation"},
    "feedback": {"name": "feedback", "color": "9333ea", "description": "General feedback"}
}

async def ensure_label_exists(
    github_token: str,
    repo_owner: str,
    repo_name: str,
    label_info: dict
) -> bool:
    """Erstellt ein Label im Repository falls es nicht existiert"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/labels"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=label_info)
        # 201 = erstellt, 422 = existiert bereits (beides okay)
        return response.status_code in [201, 422]

async def create_github_issue(
    github_token: str,
    repo_owner: str,
    repo_name: str,
    title: str,
    body: str,
    labels: list = None
) -> dict:
    """Erstellt ein Issue auf GitHub und gibt die Issue-Daten zurück"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    data = {
        "title": title,
        "body": body
    }
    if labels:
        data["labels"] = labels
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code == 201:
            return response.json()
        return None

def parse_github_url(github_url: str) -> tuple:
    """Extrahiert owner und repo name aus einer GitHub URL"""
    if not github_url:
        return None, None
    # Unterstützt: https://github.com/owner/repo oder github.com/owner/repo
    match = re.search(r'github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/.*)?$', github_url)
    if match:
        return match.group(1), match.group(2)
    return None, None

def get_decrypted_github_token(user) -> str:
    """Entschlüsselt den GitHub Token eines Users"""
    if not user or not user.github_token:
        return ""
    return decrypt_token(user.github_token)

def get_decrypted_plausible_key(project) -> str:
    """Entschlüsselt den Plausible API Key eines Projekts"""
    if not project or not project.plausible_api_key:
        return ""
    return decrypt_token(project.plausible_api_key)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}

def save_upload(file: UploadFile, subfolder: str) -> str:
    """Save uploaded file and return the URL path"""
    upload_dir = os.path.join(settings.UPLOAD_DIR, subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    
    ext = os.path.splitext(file.filename)[1] if file.filename else ".bin"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(upload_dir, filename)
    
    with open(filepath, "wb") as f:
        content = file.file.read()
        f.write(content)
    
    return f"/uploads/{subfolder}/{filename}"

@router.post("/project/create")
async def create_project(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    project_url: str = Form(""),
    github_url: str = Form(""),
    tags: str = Form(""),
    google_analytics_id: str = Form(""),
    plausible_domain: str = Form(""),
    plausible_api_key: str = Form(""),
    twitter_handle: str = Form(""),
    farcaster_handle: str = Form(""),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Check if user is a tester (Google auth) - they cannot create projects
    if user.role == "tester":
        raise HTTPException(status_code=403, detail="Testers cannot create projects. Sign in with GitHub to become a developer.")
    
    image_url = None
    if image and image.filename:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Invalid image type")
        image_url = save_upload(image, "projects")
    
    # Clean up handles - remove @ if user included it
    clean_twitter = twitter_handle.lstrip('@') if twitter_handle else None
    clean_farcaster = farcaster_handle.lstrip('@') if farcaster_handle else None
    
    project = Project(
        user_id=user.id,
        name=name,
        description=description,
        project_url=project_url if project_url else None,
        github_url=github_url if github_url else None,
        tags=tags if tags else None,
        google_analytics_id=google_analytics_id if google_analytics_id else None,
        plausible_domain=plausible_domain if plausible_domain else None,
        plausible_api_key=encrypt_token(plausible_api_key) if plausible_api_key else None,
        twitter_handle=clean_twitter if clean_twitter else None,
        farcaster_handle=clean_farcaster if clean_farcaster else None,
        image=image_url
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Check if this is the user's first project - if so, create a welcome issue
    user_project_count = db.query(func.count(Project.id)).filter(Project.user_id == user.id).scalar()
    if user_project_count == 1:  # This is their first project
        welcome_issue = Issue(
            project_id=project.id,
            user_id=2,  # koal0308 - Xdest founder
            title="👋 Welcome to Xdest – First Issue (Demo)",
            description="""Hi and welcome to Xdest!

This is a small demo issue so you can see how the issue system works in practice.

**Here's what you can try:**
• Reply to this issue
• Mark something as helpful
• Change the status (you're the project owner!)
• Add feedback or suggestions

**The goal of Xdest is simple:**
Real projects → real feedback → real iteration.

If anything feels unclear or broken, please reply here.
We'll improve the flow as fast as possible.

Thanks for being here and building with us! 🚀""",
            issue_type="docs",
            status="open",
            source_platform="Xdest-System"  # System-Issue: zählt nicht ins Test Karma
        )
        db.add(welcome_issue)
        db.commit()
    
    return RedirectResponse(url=f"/project/{project.id}", status_code=302)

@router.post("/project/{project_id}/edit")
async def edit_project(
    project_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    project_url: str = Form(""),
    github_url: str = Form(""),
    tags: str = Form(""),
    google_analytics_id: str = Form(""),
    plausible_domain: str = Form(""),
    plausible_api_key: str = Form(""),
    twitter_handle: str = Form(""),
    farcaster_handle: str = Form(""),
    image: UploadFile = File(None),
    remove_image: str = Form(""),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Clean up handles - remove @ if user included it
    clean_twitter = twitter_handle.lstrip('@') if twitter_handle else None
    clean_farcaster = farcaster_handle.lstrip('@') if farcaster_handle else None
    
    # Update fields
    project.name = name
    project.description = description if description else None
    project.project_url = project_url if project_url else None
    project.github_url = github_url if github_url else None
    project.tags = tags if tags else None
    project.google_analytics_id = google_analytics_id if google_analytics_id else None
    project.plausible_domain = plausible_domain if plausible_domain else None
    project.twitter_handle = clean_twitter if clean_twitter else None
    project.farcaster_handle = clean_farcaster if clean_farcaster else None
    # Only update API key if provided (don't overwrite with empty) - encrypt it
    if plausible_api_key:
        project.plausible_api_key = encrypt_token(plausible_api_key)
    
    # Handle image
    if remove_image == "1":
        # Remove current image
        if project.image:
            # Optional: Delete the file from disk
            old_path = os.path.join(settings.UPLOAD_DIR, project.image.lstrip("/uploads/"))
            if os.path.exists(old_path):
                os.remove(old_path)
        project.image = None
    
    if image and image.filename:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Invalid image type")
        # Save new image
        project.image = save_upload(image, "projects")
    
    # Update timestamp for cache-busting on social media
    from datetime import datetime
    project.updated_at = datetime.utcnow()
    
    db.commit()
    
    return RedirectResponse(url=f"/project/{project.id}", status_code=302)

@router.post("/project/{project_id}/post")
async def create_post(
    project_id: int,
    request: Request,
    content: str = Form(...),
    media: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    media_url = None
    media_type = None
    
    if media and media.filename:
        if media.content_type in ALLOWED_IMAGE_TYPES:
            media_url = save_upload(media, "posts")
            media_type = "image"
        elif media.content_type in ALLOWED_VIDEO_TYPES:
            media_url = save_upload(media, "posts")
            media_type = "video"
        else:
            raise HTTPException(status_code=400, detail="Invalid media type")
    
    post = Post(
        project_id=project_id,
        user_id=user.id,
        content=content,
        media_url=media_url,
        media_type=media_type
    )
    db.add(post)
    db.commit()
    
    return RedirectResponse(url=f"/project/{project_id}", status_code=302)

@router.post("/post/{post_id}/edit")
async def edit_post(
    post_id: int,
    request: Request,
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Nur der Autor des Posts kann ihn bearbeiten
    if post.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized - you can only edit your own posts")
    
    post.content = content
    db.commit()
    
    return RedirectResponse(url=f"/project/{post.project_id}", status_code=302)

@router.post("/post/{post_id}/delete")
async def delete_post(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Nur der Autor des Posts kann ihn löschen
    if post.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized - you can only delete your own posts")
    
    project_id = post.project_id
    db.delete(post)
    db.commit()
    
    return RedirectResponse(url=f"/project/{project_id}", status_code=302)

@router.post("/post/{post_id}/comment")
async def create_comment(
    post_id: int,
    request: Request,
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    comment = Comment(
        post_id=post_id,
        user_id=user.id,
        content=content
    )
    db.add(comment)
    db.commit()
    
    # Check and fulfill any pending offer obligations for this project
    _fulfill_offer_obligation(db, user.id, post.project_id)
    
    return RedirectResponse(url=f"/project/{post.project_id}", status_code=302)


# ==================== POST & COMMENT VOTE SYSTEM ====================

@router.post("/post/{post_id}/vote")
async def vote_post(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Up- oder Downvote für einen Post"""
    from app.models import PostVote
    
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post.user_id == user.id:
        return JSONResponse({"error": "Cannot vote for own post"}, status_code=400)
    
    try:
        body = await request.json()
        vote_type = body.get("vote_type", "upvote")
    except:
        vote_type = "upvote"
    
    if vote_type not in ("upvote", "downvote"):
        return JSONResponse({"error": "Invalid vote type"}, status_code=400)
    
    existing_vote = db.query(PostVote).filter(
        PostVote.post_id == post_id,
        PostVote.user_id == user.id
    ).first()
    
    if existing_vote:
        if existing_vote.vote_type == vote_type:
            # Toggle off
            if vote_type == "upvote":
                post.upvote_count = max(0, post.upvote_count - 1)
            else:
                post.downvote_count = max(0, post.downvote_count - 1)
            db.delete(existing_vote)
            db.commit()
            return JSONResponse({"voted": None, "upvotes": post.upvote_count, "downvotes": post.downvote_count})
        else:
            # Switch vote
            if existing_vote.vote_type == "upvote":
                post.upvote_count = max(0, post.upvote_count - 1)
                post.downvote_count = post.downvote_count + 1
            else:
                post.downvote_count = max(0, post.downvote_count - 1)
                post.upvote_count = post.upvote_count + 1
            existing_vote.vote_type = vote_type
            db.commit()
            return JSONResponse({"voted": vote_type, "upvotes": post.upvote_count, "downvotes": post.downvote_count})
    else:
        vote = PostVote(post_id=post_id, user_id=user.id, vote_type=vote_type)
        db.add(vote)
        if vote_type == "upvote":
            post.upvote_count = post.upvote_count + 1
        else:
            post.downvote_count = post.downvote_count + 1
        db.commit()
        return JSONResponse({"voted": vote_type, "upvotes": post.upvote_count, "downvotes": post.downvote_count})


@router.post("/comment/{comment_id}/vote")
async def vote_comment(
    comment_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Up- oder Downvote für einen Comment"""
    from app.models import CommentVote
    
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    if comment.user_id == user.id:
        return JSONResponse({"error": "Cannot vote for own comment"}, status_code=400)
    
    try:
        body = await request.json()
        vote_type = body.get("vote_type", "upvote")
    except:
        vote_type = "upvote"
    
    if vote_type not in ("upvote", "downvote"):
        return JSONResponse({"error": "Invalid vote type"}, status_code=400)
    
    existing_vote = db.query(CommentVote).filter(
        CommentVote.comment_id == comment_id,
        CommentVote.user_id == user.id
    ).first()
    
    if existing_vote:
        if existing_vote.vote_type == vote_type:
            if vote_type == "upvote":
                comment.upvote_count = max(0, comment.upvote_count - 1)
            else:
                comment.downvote_count = max(0, comment.downvote_count - 1)
            db.delete(existing_vote)
            db.commit()
            return JSONResponse({"voted": None, "upvotes": comment.upvote_count, "downvotes": comment.downvote_count})
        else:
            if existing_vote.vote_type == "upvote":
                comment.upvote_count = max(0, comment.upvote_count - 1)
                comment.downvote_count = comment.downvote_count + 1
            else:
                comment.downvote_count = max(0, comment.downvote_count - 1)
                comment.upvote_count = comment.upvote_count + 1
            existing_vote.vote_type = vote_type
            db.commit()
            return JSONResponse({"voted": vote_type, "upvotes": comment.upvote_count, "downvotes": comment.downvote_count})
    else:
        vote = CommentVote(comment_id=comment_id, user_id=user.id, vote_type=vote_type)
        db.add(vote)
        if vote_type == "upvote":
            comment.upvote_count = comment.upvote_count + 1
        else:
            comment.downvote_count = comment.downvote_count + 1
        db.commit()
        return JSONResponse({"voted": vote_type, "upvotes": comment.upvote_count, "downvotes": comment.downvote_count})


@router.post("/profile/update")
async def update_profile(
    request: Request,
    username: str = Form(""),
    bio: str = Form(""),
    github: str = Form(""),
    twitter: str = Form(""),
    linkedin: str = Form(""),
    website: str = Form(""),
    email_visible: str = Form(""),
    accept_terms: str = Form(""),
    avatar: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Check if terms need to be accepted (new user or terms not yet accepted)
    if not user.terms_accepted_at:
        if accept_terms != "on":
            raise HTTPException(status_code=400, detail="You must accept the Terms of Service and Privacy Policy")
        from datetime import datetime
        user.terms_accepted_at = datetime.utcnow()
    
    # Username Update (nur wenn geändert und verfügbar)
    if username and username != user.username:
        # Prüfen ob Username bereits vergeben ist
        existing_user = db.query(User).filter(User.username == username, User.id != user.id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already taken")
        # Username validieren (nur alphanumerisch, Unterstriche, Bindestriche)
        import re
        # Entferne @ am Anfang falls vorhanden
        clean_username = username.lstrip('@')
        if not re.match(r'^[a-zA-Z0-9_-]{3,30}$', clean_username):
            raise HTTPException(status_code=400, detail="Invalid username. Use 3-30 characters: letters, numbers, _ or - (no @ symbol)")
        user.username = clean_username
    
    user.bio = bio if bio else None
    user.github = github if github else None
    user.twitter = twitter if twitter else None
    user.linkedin = linkedin if linkedin else None
    user.website = website if website else None
    user.email_visible = email_visible == "on"
    
    if avatar and avatar.filename:
        if avatar.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Invalid image type")
        user.avatar = save_upload(avatar, "avatars")
    
    db.commit()
    
    # If terms were just accepted (setup mode), redirect to dashboard
    if accept_terms == "on":
        return RedirectResponse(url="/dashboard", status_code=302)
    
    return RedirectResponse(url=f"/user/{user.username}", status_code=302)

@router.post("/project/{project_id}/delete")
async def delete_project(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db.delete(project)
    db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=302)

# ============ GitHub Repo Integration ============

@router.get("/github/repos")
async def get_user_github_repos(request: Request, db: Session = Depends(get_db)):
    """Holt alle GitHub Repos des eingeloggten Users"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    github_token = get_decrypted_github_token(user)
    if not github_token:
        raise HTTPException(status_code=400, detail="GitHub not connected. Please login with GitHub first.")
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.github.com/user/repos",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            params={"per_page": 100, "sort": "updated"}
        )
        
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch GitHub repos")
        
        repos = resp.json()
        return JSONResponse(content=[{
            "id": repo["id"],
            "name": repo["name"],
            "full_name": repo["full_name"],
            "description": repo["description"],
            "html_url": repo["html_url"],
            "stars": repo["stargazers_count"],
            "forks": repo["forks_count"],
            "language": repo["language"],
            "updated_at": repo["updated_at"],
            "private": repo["private"]
        } for repo in repos])

@router.post("/project/{project_id}/connect-repo")
async def connect_github_repo(
    project_id: int,
    request: Request,
    repo_url: str = Form(...),
    db: Session = Depends(get_db)
):
    """Verbindet ein GitHub Repo mit einem Projekt"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    project.github_url = repo_url
    db.commit()
    
    return RedirectResponse(url=f"/project/{project_id}", status_code=302)

# ===== Plausible Analytics API =====
@router.get("/project/{project_id}/analytics")
async def get_project_analytics(project_id: int, request: Request, db: Session = Depends(get_db)):
    """Holt Plausible Analytics Daten für ein Projekt"""
    import httpx
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.plausible_domain or not project.plausible_api_key:
        return {"error": "no_analytics", "message": "Plausible not configured"}
    
    # Entschlüssele den API Key
    plausible_key = get_decrypted_plausible_key(project)
    if not plausible_key:
        return {"error": "no_analytics", "message": "Plausible API key invalid"}
    
    # Debug: Log key length (not the key itself!)
    print(f"Plausible API: domain={project.plausible_domain}, key_length={len(plausible_key)}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {plausible_key}"}
            base_url = "https://plausible.io/api/v1/stats"
            
            # Realtime visitors
            realtime_resp = await client.get(
                f"{base_url}/realtime/visitors",
                params={"site_id": str(project.plausible_domain)},
                headers=headers
            )
            
            # Log realtime response for debugging
            if realtime_resp.status_code != 200:
                print(f"Plausible realtime error: {realtime_resp.status_code} - {realtime_resp.text}")
            
            realtime = realtime_resp.json() if realtime_resp.status_code == 200 else 0
            
            plausible_domain = str(project.plausible_domain)
            
            # Aggregate stats - try today first, then 30d
            # Today's stats
            aggregate_today_resp = await client.get(
                f"{base_url}/aggregate",
                params={
                    "site_id": plausible_domain,
                    "period": "day",
                    "metrics": "visitors,pageviews,bounce_rate,visit_duration"
                },
                headers=headers
            )
            aggregate_today = aggregate_today_resp.json().get("results", {}) if aggregate_today_resp.status_code == 200 else {}
            
            # 30 days stats
            aggregate_resp = await client.get(
                f"{base_url}/aggregate",
                params={
                    "site_id": plausible_domain,
                    "period": "30d",
                    "metrics": "visitors,pageviews,bounce_rate,visit_duration"
                },
                headers=headers
            )
            aggregate_30d = aggregate_resp.json().get("results", {}) if aggregate_resp.status_code == 200 else {}
            
            # Use 30d data if available, otherwise fall back to today
            aggregate = aggregate_30d
            if aggregate_30d.get("visitors", {}).get("value", 0) == 0 and aggregate_today.get("visitors", {}).get("value", 0) > 0:
                aggregate = aggregate_today
            
            # Time series (last 7 days, fallback to today)
            timeseries_resp = await client.get(
                f"{base_url}/timeseries",
                params={
                    "site_id": plausible_domain,
                    "period": "7d",
                    "metrics": "visitors,pageviews"
                },
                headers=headers
            )
            timeseries = timeseries_resp.json().get("results", []) if timeseries_resp.status_code == 200 else []
            
            # Always get today's hourly data for the hourly chart
            timeseries_hourly_resp = await client.get(
                f"{base_url}/timeseries",
                params={
                    "site_id": plausible_domain,
                    "period": "day",
                    "metrics": "visitors,pageviews"
                },
                headers=headers
            )
            timeseries_hourly = timeseries_hourly_resp.json().get("results", []) if timeseries_hourly_resp.status_code == 200 else []
            
            # Top pages (try day if 30d is empty)
            pages_resp = await client.get(
                f"{base_url}/breakdown",
                params={
                    "site_id": plausible_domain,
                    "period": "day",
                    "property": "event:page",
                    "limit": "5"
                },
                headers=headers
            )
            pages = pages_resp.json().get("results", []) if pages_resp.status_code == 200 else []
            
            # Top sources (try day if 30d is empty)
            sources_resp = await client.get(
                f"{base_url}/breakdown",
                params={
                    "site_id": plausible_domain,
                    "period": "day",
                    "property": "visit:source",
                    "limit": "5"
                },
                headers=headers
            )
            sources = sources_resp.json().get("results", []) if sources_resp.status_code == 200 else []
            
            return {
                "realtime_visitors": realtime,
                "aggregate": aggregate,
                "aggregate_today": aggregate_today,
                "timeseries": timeseries,
                "timeseries_hourly": timeseries_hourly,
                "top_pages": pages,
                "top_sources": sources,
                "domain": plausible_domain
            }
            
    except Exception as e:
        return {"error": "api_error", "message": str(e)}

@router.get("/github/repo-info")
async def get_github_repo_info(repo_url: str, request: Request, db: Session = Depends(get_db), project_id: int = None):
    """Holt detaillierte Repo-Infos"""
    user = await get_current_user(request, db)
    
    # Extract owner/repo from URL
    try:
        # Remove .git suffix if present
        clean_url = repo_url.rstrip('/').replace('.git', '')
        parts = clean_url.split('/')
        owner = parts[-2]
        repo = parts[-1]
    except:
        raise HTTPException(status_code=400, detail="Invalid repo URL")
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    # Try to get token: first from project owner, then from current user
    github_token = None
    if project_id:
        # Get project owner's token for private repos
        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.owner and project.owner.github_token:
            github_token = get_decrypted_github_token(project.owner)
    
    # Fallback to current user's token
    if not github_token and user:
        github_token = get_decrypted_github_token(user)
    
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Basic repo info
        resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Repo not found")
        
        repo_data = resp.json()
        
        # Get languages
        langs_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/languages",
            headers=headers
        )
        languages = langs_resp.json() if langs_resp.status_code == 200 else {}
        
        # Calculate total bytes from languages (more accurate than repo size)
        total_bytes = sum(languages.values()) if languages else 0
        
        # Estimate lines of code (average ~40 bytes per line)
        estimated_lines = total_bytes // 40 if total_bytes > 0 else 0
        
        # Format lines display
        if estimated_lines < 1000:
            lines_display = f"{estimated_lines}"
        elif estimated_lines < 1000000:
            lines_display = f"{estimated_lines / 1000:.1f}K"
        else:
            lines_display = f"{estimated_lines / 1000000:.1f}M"
        
        return JSONResponse(content={
            "name": repo_data.get("name"),
            "full_name": repo_data.get("full_name"),
            "description": repo_data.get("description"),
            "html_url": repo_data.get("html_url"),
            "stars": repo_data.get("stargazers_count"),
            "forks": repo_data.get("forks_count"),
            "watchers": repo_data.get("watchers_count"),
            "open_issues": repo_data.get("open_issues_count"),
            "language": repo_data.get("language"),
            "languages": languages,
            "total_bytes": total_bytes,
            "lines_of_code": estimated_lines,
            "lines_display": lines_display,
            "created_at": repo_data.get("created_at"),
            "updated_at": repo_data.get("updated_at"),
            "pushed_at": repo_data.get("pushed_at"),
            "default_branch": repo_data.get("default_branch"),
            "license": repo_data.get("license", {}).get("name") if repo_data.get("license") else None,
            "topics": repo_data.get("topics", []),
            "visibility": repo_data.get("visibility", "public"),
            "is_fork": repo_data.get("fork", False),
            "has_wiki": repo_data.get("has_wiki", False),
            "has_issues": repo_data.get("has_issues", True),
        })

@router.get("/github/repo-commits")
async def get_github_repo_commits(
    repo_url: str, 
    request: Request, 
    page: int = 1,
    per_page: int = 30,
    db: Session = Depends(get_db),
    project_id: int = None
):
    """Holt die Commit-History eines Repos"""
    user = await get_current_user(request, db)
    
    # Extract owner/repo from URL
    try:
        clean_url = repo_url.rstrip('/').replace('.git', '')
        parts = clean_url.split('/')
        owner = parts[-2]
        repo = parts[-1]
    except:
        raise HTTPException(status_code=400, detail="Invalid repo URL")
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    # Try to get token: first from project owner, then from current user
    github_token = None
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.owner and project.owner.github_token:
            github_token = get_decrypted_github_token(project.owner)
    if not github_token and user:
        github_token = get_decrypted_github_token(user)
    
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        commits_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/commits",
            headers=headers,
            params={"per_page": per_page, "page": page}
        )
        
        if commits_resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Could not fetch commits")
        
        commits = commits_resp.json()
        
        return JSONResponse(content={
            "commits": [{
                "sha": c["sha"],
                "sha_short": c["sha"][:7],
                "message": c["commit"]["message"],
                "message_short": c["commit"]["message"].split("\n")[0][:80],
                "author_name": c["commit"]["author"]["name"],
                "author_email": c["commit"]["author"]["email"],
                "author_avatar": c["author"]["avatar_url"] if c.get("author") else None,
                "author_login": c["author"]["login"] if c.get("author") else None,
                "date": c["commit"]["author"]["date"],
                "url": c["html_url"],
                "additions": c.get("stats", {}).get("additions"),
                "deletions": c.get("stats", {}).get("deletions"),
            } for c in commits],
            "page": page,
            "per_page": per_page,
            "has_more": len(commits) == per_page
        })

@router.get("/github/repo-contributors")
async def get_github_repo_contributors(
    repo_url: str, 
    request: Request,
    db: Session = Depends(get_db),
    project_id: int = None
):
    """Holt die Contributors eines Repos mit Statistiken"""
    user = await get_current_user(request, db)
    
    # Extract owner/repo from URL
    try:
        clean_url = repo_url.rstrip('/').replace('.git', '')
        parts = clean_url.split('/')
        owner = parts[-2]
        repo = parts[-1]
    except:
        raise HTTPException(status_code=400, detail="Invalid repo URL")
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    # Try to get token: first from project owner, then from current user
    github_token = None
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.owner and project.owner.github_token:
            github_token = get_decrypted_github_token(project.owner)
    if not github_token and user:
        github_token = get_decrypted_github_token(user)
    
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get contributors
        contrib_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/contributors",
            headers=headers,
            params={"per_page": 50}
        )
        
        if contrib_resp.status_code != 200:
            return JSONResponse(content={"contributors": [], "total": 0})
        
        contributors = contrib_resp.json()
        
        return JSONResponse(content={
            "contributors": [{
                "login": c["login"],
                "avatar_url": c["avatar_url"],
                "html_url": c["html_url"],
                "contributions": c["contributions"],
                "type": c["type"]
            } for c in contributors],
            "total": len(contributors)
        })

@router.get("/github/repo-activity")
async def get_github_repo_activity(
    repo_url: str, 
    request: Request,
    db: Session = Depends(get_db),
    project_id: int = None
):
    """Holt die Aktivitäten eines Repos (Issues, PRs, Comments)"""
    user = await get_current_user(request, db)
    
    # Extract owner/repo from URL
    try:
        clean_url = repo_url.rstrip('/').replace('.git', '')
        parts = clean_url.split('/')
        owner = parts[-2]
        repo = parts[-1]
    except:
        raise HTTPException(status_code=400, detail="Invalid repo URL")
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    # Try to get token: first from project owner, then from current user
    github_token = None
    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.owner and project.owner.github_token:
            github_token = get_decrypted_github_token(project.owner)
    if not github_token and user:
        github_token = get_decrypted_github_token(user)
    
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get recent events/activity
        events_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/events",
            headers=headers,
            params={"per_page": 50}
        )
        events = events_resp.json() if events_resp.status_code == 200 else []
        
        # Get recent issues
        issues_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            headers=headers,
            params={"per_page": 30, "state": "all", "sort": "updated"}
        )
        issues = issues_resp.json() if issues_resp.status_code == 200 else []
        
        # Get recent PRs
        prs_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers=headers,
            params={"per_page": 30, "state": "all", "sort": "updated"}
        )
        prs = prs_resp.json() if prs_resp.status_code == 200 else []
        
        # Get issue comments (recent)
        comments_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues/comments",
            headers=headers,
            params={"per_page": 20, "sort": "updated", "direction": "desc"}
        )
        comments = comments_resp.json() if comments_resp.status_code == 200 else []
        
        # Format events
        formatted_events = []
        for e in events[:30]:
            event_data = {
                "type": e["type"],
                "actor": e["actor"]["login"] if e.get("actor") else "unknown",
                "actor_avatar": e["actor"]["avatar_url"] if e.get("actor") else None,
                "created_at": e["created_at"],
            }
            
            # Add specific info based on event type
            if e["type"] == "PushEvent":
                payload = e.get("payload", {})
                event_data["commits"] = payload.get("size", 0)
                event_data["branch"] = payload.get("ref", "").replace("refs/heads/", "")
                event_data["description"] = f"pushed {payload.get('size', 0)} commit(s)"
            elif e["type"] == "IssueCommentEvent":
                event_data["description"] = "commented on an issue"
                event_data["issue_number"] = e.get("payload", {}).get("issue", {}).get("number")
            elif e["type"] == "IssuesEvent":
                action = e.get("payload", {}).get("action", "")
                event_data["description"] = f"{action} an issue"
            elif e["type"] == "PullRequestEvent":
                action = e.get("payload", {}).get("action", "")
                event_data["description"] = f"{action} a pull request"
            elif e["type"] == "CreateEvent":
                ref_type = e.get("payload", {}).get("ref_type", "")
                event_data["description"] = f"created {ref_type}"
            elif e["type"] == "WatchEvent":
                event_data["description"] = "starred the repository"
            elif e["type"] == "ForkEvent":
                event_data["description"] = "forked the repository"
            else:
                event_data["description"] = e["type"].replace("Event", "")
            
            formatted_events.append(event_data)
        
        return JSONResponse(content={
            "events": formatted_events,
            "issues": [{
                "number": i["number"],
                "title": i["title"],
                "state": i["state"],
                "user": i["user"]["login"] if i.get("user") else None,
                "user_avatar": i["user"]["avatar_url"] if i.get("user") else None,
                "created_at": i["created_at"],
                "updated_at": i["updated_at"],
                "comments": i["comments"],
                "url": i["html_url"],
                "is_pr": "pull_request" in i
            } for i in issues if "pull_request" not in i][:20],
            "pull_requests": [{
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "user": pr["user"]["login"] if pr.get("user") else None,
                "user_avatar": pr["user"]["avatar_url"] if pr.get("user") else None,
                "created_at": pr["created_at"],
                "updated_at": pr["updated_at"],
                "url": pr["html_url"],
                "merged": pr.get("merged_at") is not None
            } for pr in prs][:20],
            "recent_comments": [{
                "id": c["id"],
                "body": c["body"][:200] + "..." if len(c.get("body", "")) > 200 else c.get("body", ""),
                "user": c["user"]["login"] if c.get("user") else None,
                "user_avatar": c["user"]["avatar_url"] if c.get("user") else None,
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
                "issue_url": c["issue_url"],
                "html_url": c["html_url"]
            } for c in comments][:15]
        })

# ==================== ISSUE / FEEDBACK SYSTEM ====================

@router.post("/project/{project_id}/issue")
async def create_issue(
    project_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    issue_type: str = Form("bug"),
    screenshot: UploadFile = File(None),
    sync_to_github: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Erstellt ein neues Issue/Feedback für ein Projekt"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate issue type
    valid_types = ["bug", "feature", "question", "security", "docs", "feedback"]
    if issue_type not in valid_types:
        issue_type = "bug"
    
    # Handle screenshot upload
    screenshot_url = None
    if screenshot and screenshot.filename:
        if screenshot.content_type in ALLOWED_IMAGE_TYPES:
            screenshot_url = save_upload(screenshot, "issues")
    
    # GitHub Sync Variablen
    github_issue_number = None
    github_issue_url = None
    
    # Wenn GitHub Sync aktiviert und Projekt hat GitHub Repo
    github_token = get_decrypted_github_token(user)
    if sync_to_github and project.github_url and github_token:
        repo_owner, repo_name = parse_github_url(str(project.github_url))
        if repo_owner and repo_name:
            # Issue Body für GitHub formatieren
            github_body = f"{description}\n\n"
            github_body += "---\n"
            github_body += f"📍 *Reported via [Xdest]({settings.APP_URL})*\n"
            github_body += f"👤 Reporter: @{user.username}\n"
            
            # Screenshot einbetten wenn vorhanden
            if screenshot_url:
                full_screenshot_url = f"{settings.APP_URL}{screenshot_url}"
                github_body += f"\n### Screenshot\n![Screenshot]({full_screenshot_url})\n"
            
            # Labels für Issue Type - zuerst Label erstellen falls nicht vorhanden
            label_info = GITHUB_LABELS.get(issue_type)
            labels = []
            if label_info:
                # Erstelle Label falls es nicht existiert
                await ensure_label_exists(
                    github_token=github_token,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    label_info=label_info
                )
                labels = [label_info["name"]]
            
            # GitHub Issue erstellen
            github_result = await create_github_issue(
                github_token=github_token,
                repo_owner=repo_owner,
                repo_name=repo_name,
                title=title,
                body=github_body,
                labels=labels
            )
            
            if github_result:
                github_issue_number = github_result.get("number")
                github_issue_url = github_result.get("html_url")
    
    issue = Issue(
        project_id=project_id,
        user_id=user.id,
        title=title,
        description=description,
        screenshot=screenshot_url,
        issue_type=issue_type,
        status="open",
        source_platform="Xdest",
        github_issue_number=github_issue_number,
        github_issue_url=github_issue_url
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    
    # Check and fulfill any pending offer obligations for this project
    _fulfill_offer_obligation(db, user.id, project_id)
    
    return RedirectResponse(url=f"/project/{project_id}/issues", status_code=302)

@router.post("/issue/{issue_id}/respond")
async def respond_to_issue(
    issue_id: int,
    request: Request,
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    """Fügt eine Antwort zu einem Issue hinzu"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    response = IssueResponse(
        issue_id=issue_id,
        user_id=user.id,
        content=content
    )
    db.add(response)
    db.commit()
    
    # Check and fulfill any pending offer obligations for this project
    _fulfill_offer_obligation(db, user.id, issue.project_id)
    
    return RedirectResponse(url=f"/project/{issue.project_id}/issues/{issue_id}", status_code=302)

@router.post("/issue/{issue_id}/edit")
async def edit_issue(
    issue_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    issue_type: str = Form(...),
    screenshot: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """Bearbeitet ein Issue (nur Reporter)"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    # Nur Reporter darf bearbeiten
    if issue.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the reporter can edit this issue")
    
    # Geschlossene Issues können nicht bearbeitet werden
    closed_statuses = ["resolved", "closed", "wont_fix"]
    if issue.status in closed_statuses:
        raise HTTPException(status_code=403, detail="Closed issues cannot be edited")
    
    valid_types = ["bug", "feature", "question", "security", "docs", "feedback"]
    if issue_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid issue type")
    
    # Update fields
    issue.title = title
    issue.description = description
    issue.issue_type = issue_type
    issue.updated_at = datetime.utcnow()
    
    # Handle screenshot upload
    if screenshot and screenshot.filename:
        # Create uploads directory if needed
        upload_dir = Path("uploads/issues")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_ext = Path(screenshot.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = upload_dir / unique_filename
        
        # Save file
        with open(file_path, "wb") as f:
            content = await screenshot.read()
            f.write(content)
        
        issue.screenshot = f"/uploads/issues/{unique_filename}"
    
    db.commit()
    
    return RedirectResponse(url=f"/project/{issue.project_id}/issues/{issue_id}", status_code=302)

@router.post("/issue/{issue_id}/status")
async def update_issue_status(
    issue_id: int,
    request: Request,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    """Aktualisiert den Status eines Issues (nur Projektbesitzer)"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    # Nur Projektbesitzer darf Status ändern
    if issue.project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only project owner can change status")
    
    valid_statuses = ["open", "in_progress", "resolved", "closed", "wont_fix"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    issue.status = status
    issue.updated_at = datetime.utcnow()
    db.commit()
    
    return RedirectResponse(url=f"/project/{issue.project_id}/issues/{issue_id}", status_code=302)

@router.delete("/issue/{issue_id}")
async def delete_issue(
    issue_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Löscht ein Issue (nur Reporter oder Projektbesitzer)"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    # Nur Reporter oder Projektbesitzer darf löschen
    if issue.user_id != user.id and issue.project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    project_id = issue.project_id
    db.delete(issue)
    db.commit()
    
    return RedirectResponse(url=f"/project/{project_id}/issues", status_code=302)

# ==================== VOTE SYSTEM (Up/Down) ====================

@router.post("/response/{response_id}/vote")
async def vote_response(
    response_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Up- oder Downvote für eine Antwort"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    response = db.query(IssueResponse).filter(IssueResponse.id == response_id).first()
    if not response:
        raise HTTPException(status_code=404, detail="Response not found")
    
    if response.user_id == user.id:
        return JSONResponse({"error": "Cannot vote for own response"}, status_code=400)
    
    # vote_type aus Body lesen (default: upvote für Abwärtskompatibilität)
    try:
        body = await request.json()
        vote_type = body.get("vote_type", "upvote")
    except:
        vote_type = "upvote"
    
    if vote_type not in ("upvote", "downvote"):
        return JSONResponse({"error": "Invalid vote type"}, status_code=400)
    
    existing_vote = db.query(ResponseVote).filter(
        ResponseVote.response_id == response_id,
        ResponseVote.user_id == user.id
    ).first()
    
    if existing_vote:
        if existing_vote.vote_type == vote_type:
            # Gleicher Vote → entfernen (toggle)
            if vote_type == "upvote":
                response.helpful_count = max(0, response.helpful_count - 1)
            else:
                response.downvote_count = max(0, response.downvote_count - 1)
            db.delete(existing_vote)
            db.commit()
            return JSONResponse({"voted": None, "upvotes": response.helpful_count, "downvotes": response.downvote_count, "count": response.helpful_count})
        else:
            # Anderer Vote → wechseln
            if existing_vote.vote_type == "upvote":
                response.helpful_count = max(0, response.helpful_count - 1)
                response.downvote_count = response.downvote_count + 1
            else:
                response.downvote_count = max(0, response.downvote_count - 1)
                response.helpful_count = response.helpful_count + 1
            existing_vote.vote_type = vote_type
            db.commit()
            return JSONResponse({"voted": vote_type, "upvotes": response.helpful_count, "downvotes": response.downvote_count, "count": response.helpful_count})
    else:
        # Neuer Vote
        vote = ResponseVote(response_id=response_id, user_id=user.id, vote_type=vote_type)
        db.add(vote)
        if vote_type == "upvote":
            response.helpful_count = response.helpful_count + 1
        else:
            response.downvote_count = response.downvote_count + 1
        db.commit()
        return JSONResponse({"voted": vote_type, "upvotes": response.helpful_count, "downvotes": response.downvote_count, "count": response.helpful_count})

@router.post("/issue/{issue_id}/vote")
async def vote_issue(
    issue_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Up- oder Downvote für ein Issue"""
    from app.models import IssueVote
    
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    if issue.user_id == user.id:
        return JSONResponse({"error": "Cannot vote for own issue"}, status_code=400)
    
    try:
        body = await request.json()
        vote_type = body.get("vote_type", "upvote")
    except:
        vote_type = "upvote"
    
    if vote_type not in ("upvote", "downvote"):
        return JSONResponse({"error": "Invalid vote type"}, status_code=400)
    
    existing_vote = db.query(IssueVote).filter(
        IssueVote.issue_id == issue_id,
        IssueVote.user_id == user.id
    ).first()
    
    if existing_vote:
        if existing_vote.vote_type == vote_type:
            # Toggle off
            if vote_type == "upvote":
                issue.helpful_count = max(0, issue.helpful_count - 1)
            else:
                issue.downvote_count = max(0, issue.downvote_count - 1)
            db.delete(existing_vote)
            db.commit()
            return JSONResponse({"voted": None, "upvotes": issue.helpful_count, "downvotes": issue.downvote_count, "count": issue.helpful_count})
        else:
            # Switch vote
            if existing_vote.vote_type == "upvote":
                issue.helpful_count = max(0, issue.helpful_count - 1)
                issue.downvote_count = issue.downvote_count + 1
            else:
                issue.downvote_count = max(0, issue.downvote_count - 1)
                issue.helpful_count = issue.helpful_count + 1
            existing_vote.vote_type = vote_type
            db.commit()
            return JSONResponse({"voted": vote_type, "upvotes": issue.helpful_count, "downvotes": issue.downvote_count, "count": issue.helpful_count})
    else:
        vote = IssueVote(issue_id=issue_id, user_id=user.id, vote_type=vote_type)
        db.add(vote)
        if vote_type == "upvote":
            issue.helpful_count = issue.helpful_count + 1
        else:
            issue.downvote_count = issue.downvote_count + 1
        db.commit()
        return JSONResponse({"voted": vote_type, "upvotes": issue.helpful_count, "downvotes": issue.downvote_count, "count": issue.helpful_count})

@router.post("/response/{response_id}/solution")
async def mark_as_solution(
    response_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Markiert eine Antwort als Lösung (nur vom Issue-Ersteller)"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    response = db.query(IssueResponse).filter(IssueResponse.id == response_id).first()
    if not response:
        raise HTTPException(status_code=404, detail="Response not found")
    
    issue = response.issue
    
    # Nur der Issue-Ersteller oder Projektbesitzer kann Lösung markieren
    if issue.user_id != user.id and issue.project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Alle anderen Antworten als nicht-Lösung markieren
    db.query(IssueResponse).filter(IssueResponse.issue_id == issue.id).update({"is_solution": 0})
    
    # Diese Antwort als Lösung markieren
    response.is_solution = 1
    
    # Issue als gelöst markieren
    issue.status = "resolved"
    
    db.commit()
    
    return RedirectResponse(url=f"/project/{issue.project_id}/issues/{issue.id}", status_code=302)

@router.get("/leaderboard")
async def get_leaderboard(
    request: Request,
    db: Session = Depends(get_db)
):
    """Leaderboard with unified +1/-1 scoring system integrated with Test Karma."""
    
    user_scores = {}
    
    # Helper: ensure user entry exists
    def ensure_user(uid, username, avatar):
        if uid not in user_scores:
            user_scores[uid] = {
                "user_id": uid,
                "username": username,
                "avatar": avatar,
                "solutions": 0,
                "response_helpful": 0,
                "issue_helpful": 0,
                "github_positive": 0,
                "github_negative": 0,
                "five_star_ratings": 0,
                "issues_given": 0,
                "issues_received": 0,
                "offer_penalties": 0,
                "total_responses": 0,
                "total_issues": 0,
                "projects_count": 0
            }
    
    # 1. Response stats: solutions + helpful votes
    response_data = db.query(
        User.id, User.username, User.avatar,
        func.coalesce(func.sum(IssueResponse.helpful_count), 0).label('response_helpful'),
        func.coalesce(func.sum(IssueResponse.is_solution), 0).label('solutions_count'),
        func.count(IssueResponse.id).label('total_responses')
    ).outerjoin(IssueResponse, User.id == IssueResponse.user_id
    ).group_by(User.id).all()
    
    for row in response_data:
        ensure_user(row.id, row.username, row.avatar)
        user_scores[row.id]["solutions"] = row.solutions_count or 0
        user_scores[row.id]["response_helpful"] = row.response_helpful or 0
        user_scores[row.id]["total_responses"] = row.total_responses or 0
    
    # 2. Issue stats: helpful votes + GitHub reactions
    issue_data = db.query(
        User.id, User.username, User.avatar,
        func.coalesce(func.sum(Issue.helpful_count), 0).label('issue_helpful'),
        func.coalesce(func.sum(Issue.github_reactions), 0).label('github_pos'),
        func.coalesce(func.sum(Issue.github_negative_reactions), 0).label('github_neg'),
        func.count(Issue.id).label('total_issues')
    ).outerjoin(Issue, User.id == Issue.user_id
    ).group_by(User.id).all()
    
    for row in issue_data:
        ensure_user(row.id, row.username, row.avatar)
        user_scores[row.id]["issue_helpful"] = row.issue_helpful or 0
        user_scores[row.id]["github_positive"] = row.github_pos or 0
        user_scores[row.id]["github_negative"] = row.github_neg or 0
        user_scores[row.id]["total_issues"] = row.total_issues or 0
    
    # 3. Five-star ratings received
    five_star_data = db.query(
        UserRating.rated_user_id,
        func.count(UserRating.id).label('count')
    ).filter(UserRating.stars == 5).group_by(UserRating.rated_user_id).all()
    
    for row in five_star_data:
        if row.rated_user_id in user_scores:
            user_scores[row.rated_user_id]["five_star_ratings"] = row.count
        else:
            u = db.query(User).filter(User.id == row.rated_user_id).first()
            if u:
                ensure_user(u.id, u.username, u.avatar)
                user_scores[u.id]["five_star_ratings"] = row.count
    
    # 4. Test Karma: issues given to foreign projects (excludes system issues)
    for uid, data in list(user_scores.items()):
        issues_given = db.query(func.count(Issue.id)).join(
            Project, Issue.project_id == Project.id
        ).filter(
            Issue.user_id == uid,
            Project.user_id != uid,
            Issue.source_platform != "Xdest-System"
        ).scalar() or 0
        
        issues_received = db.query(func.count(Issue.id)).join(
            Project, Issue.project_id == Project.id
        ).filter(
            Project.user_id == uid,
            Issue.user_id != uid,
            Issue.source_platform != "Xdest-System"
        ).scalar() or 0
        
        offer_penalties = db.query(func.count(OfferRedemption.id)).filter(
            OfferRedemption.user_id == uid,
            OfferRedemption.karma_penalty_applied == True,
            OfferRedemption.karma_penalty_reversed == False
        ).scalar() or 0
        
        projects_count = db.query(func.count(Project.id)).filter(
            Project.user_id == uid
        ).scalar() or 0
        
        data["issues_given"] = issues_given
        data["issues_received"] = issues_received
        data["offer_penalties"] = offer_penalties
        data["projects_count"] = projects_count
    
    # 5. Calculate total score: everything is +1 or -1
    leaderboard = []
    for uid, d in user_scores.items():
        # Each category counts as +1 per instance, negatives as -1
        total = (
            d["solutions"]          # +1 per solution marked
            + d["response_helpful"]  # +1 per helpful vote on responses
            + d["issue_helpful"]     # +1 per helpful vote on issues
            + d["github_positive"]   # +1 per GitHub 👍
            - d["github_negative"]   # -1 per GitHub 👎
            + d["five_star_ratings"] # +1 per 5-star rating received
            + d["issues_given"]      # +1 per issue written for others (tester karma)
            + d["issues_received"]   # +1 per issue received on your projects
            - d["offer_penalties"]   # -1 per overdue offer obligation
        )
        
        # Test karma separate (for display)
        test_karma = d["issues_given"] - d["issues_received"] - d["offer_penalties"]
        
        if total > 0 or d["total_issues"] > 0 or d["total_responses"] > 0 or d["issues_given"] > 0 or d["issues_received"] > 0:
            leaderboard.append({
                **d,
                "total_score": total,
                "test_karma": test_karma
            })
    
    leaderboard.sort(key=lambda x: x["total_score"], reverse=True)
    
    # Limit to 50
    leaderboard = leaderboard[:50]
    
    for rank, entry in enumerate(leaderboard, 1):
        entry["rank"] = rank
    
    return JSONResponse({"leaderboard": leaderboard})


@router.get("/leaderboard/my-stats")
async def get_my_leaderboard_stats(
    request: Request,
    db: Session = Depends(get_db)
):
    """Personal leaderboard stats with unified +1/-1 scoring."""
    user = await get_current_user_optional(request, db)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    # Response stats
    response_data = db.query(
        func.coalesce(func.sum(IssueResponse.helpful_count), 0).label('response_helpful'),
        func.coalesce(func.sum(IssueResponse.is_solution), 0).label('solutions_count'),
        func.count(IssueResponse.id).label('total_responses')
    ).filter(IssueResponse.user_id == user.id).first()
    
    # Issue stats
    issue_data = db.query(
        func.coalesce(func.sum(Issue.helpful_count), 0).label('issue_helpful'),
        func.coalesce(func.sum(Issue.github_reactions), 0).label('github_pos'),
        func.coalesce(func.sum(Issue.github_negative_reactions), 0).label('github_neg'),
        func.count(Issue.id).label('total_issues')
    ).filter(Issue.user_id == user.id).first()
    
    five_star_count = db.query(func.count(UserRating.id)).filter(
        UserRating.rated_user_id == user.id,
        UserRating.stars == 5
    ).scalar() or 0
    
    # Test Karma data
    karma_data = calculate_test_karma(db, user.id)
    
    projects_count = db.query(func.count(Project.id)).filter(
        Project.user_id == user.id
    ).scalar() or 0
    
    # Rank
    full_leaderboard_response = await get_leaderboard(request, db)
    full_leaderboard = full_leaderboard_response.body.decode()
    leaderboard_data = json.loads(full_leaderboard)
    
    my_rank = None
    for entry in leaderboard_data.get("leaderboard", []):
        if entry["user_id"] == user.id:
            my_rank = entry["rank"]
            break
    
    # Recent activities (last 10)
    recent_activities = []
    
    recent_solutions = db.query(
        IssueResponse.created_at,
        Issue.title.label('issue_title'),
        Project.name.label('project_name')
    ).join(Issue, IssueResponse.issue_id == Issue.id
    ).join(Project, Issue.project_id == Project.id
    ).filter(
        IssueResponse.user_id == user.id,
        IssueResponse.is_solution == True
    ).order_by(IssueResponse.created_at.desc()).limit(5).all()
    
    for sol in recent_solutions:
        recent_activities.append({
            "type": "solution", "points": 1,
            "description": f"Solution marked for '{sol.issue_title}'",
            "project": sol.project_name,
            "created_at": sol.created_at.isoformat() if sol.created_at else None
        })
    
    recent_helpful_responses = db.query(
        IssueResponse.helpful_count, IssueResponse.created_at,
        Issue.title.label('issue_title'), Project.name.label('project_name')
    ).join(Issue, IssueResponse.issue_id == Issue.id
    ).join(Project, Issue.project_id == Project.id
    ).filter(
        IssueResponse.user_id == user.id,
        IssueResponse.helpful_count > 0,
        IssueResponse.is_solution == False
    ).order_by(IssueResponse.created_at.desc()).limit(5).all()
    
    for resp in recent_helpful_responses:
        recent_activities.append({
            "type": "response_helpful", "points": resp.helpful_count,
            "description": f"{resp.helpful_count}x helpful on '{resp.issue_title}'",
            "project": resp.project_name,
            "created_at": resp.created_at.isoformat() if resp.created_at else None
        })
    
    recent_helpful_issues = db.query(
        Issue.title, Issue.helpful_count, Issue.github_reactions,
        Issue.created_at, Project.name.label('project_name')
    ).join(Project, Issue.project_id == Project.id
    ).filter(
        Issue.user_id == user.id,
        (Issue.helpful_count > 0) | (Issue.github_reactions > 0)
    ).order_by(Issue.created_at.desc()).limit(5).all()
    
    for issue in recent_helpful_issues:
        points = (issue.helpful_count or 0) + (issue.github_reactions or 0)
        recent_activities.append({
            "type": "issue_helpful", "points": points,
            "description": f"Issue '{issue.title}' got {points} votes",
            "project": issue.project_name,
            "created_at": issue.created_at.isoformat() if issue.created_at else None
        })
    
    recent_ratings = db.query(
        UserRating.created_at, User.username.label('rater_username')
    ).join(User, UserRating.rater_user_id == User.id
    ).filter(
        UserRating.rated_user_id == user.id,
        UserRating.stars == 5
    ).order_by(UserRating.created_at.desc()).limit(5).all()
    
    for rating in recent_ratings:
        recent_activities.append({
            "type": "five_star", "points": 1,
            "description": f"5-star rating from {rating.rater_username}",
            "project": None,
            "created_at": rating.created_at.isoformat() if rating.created_at else None
        })
    
    # Recent issues given to other projects
    recent_issues_given = db.query(
        Issue.title, Issue.created_at, Project.name.label('project_name')
    ).join(Project, Issue.project_id == Project.id
    ).filter(
        Issue.user_id == user.id,
        Project.user_id != user.id,
        Issue.source_platform != "Xdest-System"
    ).order_by(Issue.created_at.desc()).limit(5).all()
    
    for iss in recent_issues_given:
        recent_activities.append({
            "type": "karma_given", "points": 1,
            "description": f"Tested '{iss.project_name}': {iss.title}",
            "project": iss.project_name,
            "created_at": iss.created_at.isoformat() if iss.created_at else None
        })
    
    recent_activities.sort(key=lambda x: x["created_at"] or "", reverse=True)
    recent_activities = recent_activities[:10]
    
    # Total score (same formula as leaderboard)
    solutions = response_data.solutions_count or 0
    resp_helpful = response_data.response_helpful or 0
    iss_helpful = issue_data.issue_helpful or 0
    gh_pos = issue_data.github_pos or 0
    gh_neg = issue_data.github_neg or 0
    
    total_score = (
        solutions + resp_helpful + iss_helpful
        + gh_pos - gh_neg
        + five_star_count
        + karma_data["given"]
        + karma_data["received"]
        - karma_data["offer_penalties"]
    )
    
    test_karma = karma_data["given"] - karma_data["received"] - karma_data["offer_penalties"]
    
    return JSONResponse({
        "user_id": user.id,
        "username": user.username,
        "avatar": user.avatar,
        "rank": my_rank,
        "total_score": total_score,
        "test_karma": test_karma,
        "breakdown": {
            "solutions": {"count": solutions, "points": solutions},
            "response_helpful": {"count": resp_helpful, "points": resp_helpful},
            "issue_helpful": {"count": iss_helpful, "points": iss_helpful},
            "github_reactions": {"positive": gh_pos, "negative": gh_neg, "points": gh_pos - gh_neg},
            "five_star_ratings": {"count": five_star_count, "points": five_star_count},
            "issues_given": {"count": karma_data["given"], "points": karma_data["given"]},
            "issues_received": {"count": karma_data["received"], "points": karma_data["received"]},
            "offer_penalties": {"count": karma_data["offer_penalties"], "points": -karma_data["offer_penalties"]}
        },
        "recent_activities": recent_activities,
        "stats": {
            "total_responses": response_data.total_responses or 0,
            "total_issues": issue_data.total_issues or 0,
            "projects_count": projects_count,
            "pending_obligations": karma_data["pending_obligations"]
        }
    })


# ==================== GITHUB SYNC ====================

@router.post("/project/{project_id}/sync-github-issues")
async def sync_github_issues(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Synchronisiert GitHub Issue Status mit dest Issues"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.github_url:
        return JSONResponse({"synced": 0, "message": "No GitHub repo connected"})
    
    # Parse GitHub URL
    repo_owner, repo_name = parse_github_url(str(project.github_url))
    if not repo_owner or not repo_name:
        return JSONResponse({"synced": 0, "message": "Invalid GitHub URL"})
    
    # Get all dest issues with GitHub issue numbers
    dest_issues = db.query(Issue).filter(
        Issue.project_id == project_id,
        Issue.github_issue_number.isnot(None)
    ).all()
    
    if not dest_issues:
        return JSONResponse({"synced": 0, "message": "No linked GitHub issues"})
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    github_token = get_decrypted_github_token(user)
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    
    synced_count = 0
    reactions_updated = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        for issue in dest_issues:
            try:
                # Get GitHub issue status and reactions
                gh_resp = await client.get(
                    f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{issue.github_issue_number}",
                    headers=headers
                )
                if gh_resp.status_code == 200:
                    gh_issue = gh_resp.json()
                    
                    # Sync status
                    gh_state = gh_issue.get("state", "open")
                    if gh_state == "closed" and issue.status not in ["closed", "resolved"]:
                        issue.status = "closed"
                        synced_count += 1
                    elif gh_state == "open" and issue.status in ["closed"]:
                        issue.status = "open"
                        synced_count += 1
                    
                    # Sync GitHub reactions (👍 thumbs up)
                    reactions = gh_issue.get("reactions", {})
                    thumbs_up = reactions.get("+1", 0)
                    thumbs_down = reactions.get("-1", 0)
                    if issue.github_reactions != thumbs_up:
                        issue.github_reactions = thumbs_up
                        reactions_updated += 1
                    if issue.github_negative_reactions != thumbs_down:
                        issue.github_negative_reactions = thumbs_down
                    
            except Exception as e:
                print(f"Error syncing issue {issue.id}: {e}")
                continue
    
    db.commit()
    return JSONResponse({
        "synced": synced_count, 
        "reactions_updated": reactions_updated,
        "message": f"{synced_count} Status + {reactions_updated} Reactions synchronisiert"
    })


@router.get("/issue/{issue_id}/github-reactions")
async def get_github_reactions(
    issue_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Holt die GitHub Reactions für ein Issue"""
    user = await get_current_user(request, db)
    
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue or not issue.github_issue_number:
        return JSONResponse({"reactions": {}, "total": 0})
    
    project = db.query(Project).filter(Project.id == issue.project_id).first()
    if not project or not project.github_url:
        return JSONResponse({"reactions": {}, "total": 0})
    
    repo_owner, repo_name = parse_github_url(str(project.github_url))
    if not repo_owner or not repo_name:
        return JSONResponse({"reactions": {}, "total": 0})
    
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    github_token = get_decrypted_github_token(user) if user else ""
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{issue.github_issue_number}",
                headers=headers
            )
            if resp.status_code == 200:
                gh_issue = resp.json()
                reactions = gh_issue.get("reactions", {})
                return JSONResponse({
                    "reactions": {
                        "thumbs_up": reactions.get("+1", 0),
                        "thumbs_down": reactions.get("-1", 0),
                        "laugh": reactions.get("laugh", 0),
                        "hooray": reactions.get("hooray", 0),
                        "confused": reactions.get("confused", 0),
                        "heart": reactions.get("heart", 0),
                        "rocket": reactions.get("rocket", 0),
                        "eyes": reactions.get("eyes", 0),
                    },
                    "total": reactions.get("total_count", 0),
                    "github_state": gh_issue.get("state", "unknown")
                })
        except Exception as e:
            print(f"Error getting GitHub reactions: {e}")
    
    return JSONResponse({"reactions": {}, "total": 0})


# ==================== STAR RATINGS ====================

from app.models import ProjectRating, UserRating

@router.post("/project/{project_id}/rate")
async def rate_project(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Bewerte ein Projekt mit 1-5 Sternen"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Nicht eingeloggt")
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden")
    
    # User kann eigenes Projekt nicht bewerten
    if project.user_id == user.id:
        raise HTTPException(status_code=400, detail="Du kannst dein eigenes Projekt nicht bewerten")
    
    data = await request.json()
    stars = data.get("stars", 0)
    
    if not 1 <= stars <= 5:
        raise HTTPException(status_code=400, detail="Bewertung muss zwischen 1 und 5 Sternen sein")
    
    # Bestehende Bewertung prüfen oder neue erstellen
    existing_rating = db.query(ProjectRating).filter(
        ProjectRating.project_id == project_id,
        ProjectRating.user_id == user.id
    ).first()
    
    if existing_rating:
        existing_rating.stars = stars
        existing_rating.updated_at = datetime.utcnow()
    else:
        new_rating = ProjectRating(
            project_id=project_id,
            user_id=user.id,
            stars=stars
        )
        db.add(new_rating)
    
    db.commit()
    
    # Durchschnitt berechnen
    avg_rating = db.query(func.avg(ProjectRating.stars)).filter(
        ProjectRating.project_id == project_id
    ).scalar() or 0
    
    rating_count = db.query(func.count(ProjectRating.id)).filter(
        ProjectRating.project_id == project_id
    ).scalar() or 0
    
    return JSONResponse({
        "success": True,
        "your_rating": stars,
        "average_rating": round(float(avg_rating), 1),
        "rating_count": rating_count
    })


@router.get("/project/{project_id}/rating")
async def get_project_rating(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Hole die Bewertung eines Projekts"""
    user = await get_current_user(request, db)
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden")
    
    # Durchschnitt
    avg_rating = db.query(func.avg(ProjectRating.stars)).filter(
        ProjectRating.project_id == project_id
    ).scalar() or 0
    
    # Anzahl Bewertungen
    rating_count = db.query(func.count(ProjectRating.id)).filter(
        ProjectRating.project_id == project_id
    ).scalar() or 0
    
    # Eigene Bewertung
    user_rating = None
    if user:
        user_rating_obj = db.query(ProjectRating).filter(
            ProjectRating.project_id == project_id,
            ProjectRating.user_id == user.id
        ).first()
        if user_rating_obj:
            user_rating = user_rating_obj.stars
    
    return JSONResponse({
        "average_rating": round(float(avg_rating), 1),
        "rating_count": rating_count,
        "user_rating": user_rating
    })


@router.post("/user/{username}/rate")
async def rate_user(
    username: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Bewerte einen User mit 1-5 Sternen"""
    current_user = await get_current_user(request, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Nicht eingeloggt")
    
    target_user = db.query(User).filter(User.username == username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    
    # User kann sich selbst nicht bewerten
    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Du kannst dich selbst nicht bewerten")
    
    data = await request.json()
    stars = data.get("stars", 0)
    
    if not 1 <= stars <= 5:
        raise HTTPException(status_code=400, detail="Bewertung muss zwischen 1 und 5 Sternen sein")
    
    # Bestehende Bewertung prüfen oder neue erstellen
    existing_rating = db.query(UserRating).filter(
        UserRating.rated_user_id == target_user.id,
        UserRating.rater_user_id == current_user.id
    ).first()
    
    if existing_rating:
        existing_rating.stars = stars
        existing_rating.updated_at = datetime.utcnow()
    else:
        new_rating = UserRating(
            rated_user_id=target_user.id,
            rater_user_id=current_user.id,
            stars=stars
        )
        db.add(new_rating)
    
    db.commit()
    
    # Durchschnitt berechnen
    avg_rating = db.query(func.avg(UserRating.stars)).filter(
        UserRating.rated_user_id == target_user.id
    ).scalar() or 0
    
    rating_count = db.query(func.count(UserRating.id)).filter(
        UserRating.rated_user_id == target_user.id
    ).scalar() or 0
    
    return JSONResponse({
        "success": True,
        "your_rating": stars,
        "average_rating": round(float(avg_rating), 1),
        "rating_count": rating_count
    })


@router.get("/user/{username}/rating")
async def get_user_rating(
    username: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Hole die Bewertung eines Users"""
    current_user = await get_current_user(request, db)
    
    target_user = db.query(User).filter(User.username == username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    
    # Durchschnitt
    avg_rating = db.query(func.avg(UserRating.stars)).filter(
        UserRating.rated_user_id == target_user.id
    ).scalar() or 0
    
    # Anzahl Bewertungen
    rating_count = db.query(func.count(UserRating.id)).filter(
        UserRating.rated_user_id == target_user.id
    ).scalar() or 0
    
    # Eigene Bewertung
    user_rating = None
    if current_user:
        user_rating_obj = db.query(UserRating).filter(
            UserRating.rated_user_id == target_user.id,
            UserRating.rater_user_id == current_user.id
        ).first()
        if user_rating_obj:
            user_rating = user_rating_obj.stars
    
    return JSONResponse({
        "average_rating": round(float(avg_rating), 1),
        "rating_count": rating_count,
        "user_rating": user_rating
    })


# ============================================
# Privacy & GDPR Endpoints
# ============================================

@router.get("/privacy/data-summary")
async def get_data_summary(request: Request, db: Session = Depends(get_db)):
    """Get a summary of user's data for the privacy page"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    from app.models import IssueVote, ProjectRating, UserRating
    
    projects_count = db.query(func.count(Project.id)).filter(Project.user_id == user.id).scalar() or 0
    issues_count = db.query(func.count(Issue.id)).filter(Issue.user_id == user.id).scalar() or 0
    responses_count = db.query(func.count(IssueResponse.id)).filter(IssueResponse.user_id == user.id).scalar() or 0
    
    # Count all votes (response votes + issue votes)
    response_votes = db.query(func.count(ResponseVote.id)).filter(ResponseVote.user_id == user.id).scalar() or 0
    issue_votes = db.query(func.count(IssueVote.id)).filter(IssueVote.user_id == user.id).scalar() or 0
    
    return JSONResponse({
        "projects": projects_count,
        "issues": issues_count,
        "responses": responses_count,
        "votes": response_votes + issue_votes
    })

@router.get("/privacy/my-data")
async def get_my_data(request: Request, db: Session = Depends(get_db)):
    """Get all user's personal data (GDPR Right to Access)"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    from app.models import IssueVote, ProjectRating, UserRating
    
    # User profile
    user_data = {
        "profile": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "avatar": user.avatar,
            "bio": user.bio,
            "github": user.github,
            "provider": user.provider,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None
        },
        "projects": [],
        "issues_created": [],
        "responses": [],
        "votes": {
            "issue_votes": [],
            "response_votes": []
        },
        "ratings": {
            "project_ratings_given": [],
            "user_ratings_given": [],
            "user_ratings_received": []
        }
    }
    
    # Projects
    projects = db.query(Project).filter(Project.user_id == user.id).all()
    for p in projects:
        user_data["projects"].append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "github_url": p.github_url,
            "project_url": p.project_url,
            "tags": p.tags,
            "created_at": p.created_at.isoformat() if p.created_at else None
        })
    
    # Issues created
    issues = db.query(Issue).filter(Issue.user_id == user.id).all()
    for i in issues:
        user_data["issues_created"].append({
            "id": i.id,
            "project_id": i.project_id,
            "title": i.title,
            "description": i.description,
            "type": i.issue_type,
            "status": i.status,
            "created_at": i.created_at.isoformat() if i.created_at else None
        })
    
    # Responses
    responses = db.query(IssueResponse).filter(IssueResponse.user_id == user.id).all()
    for r in responses:
        user_data["responses"].append({
            "id": r.id,
            "issue_id": r.issue_id,
            "content": r.content,
            "is_solution": r.is_solution,
            "helpful_count": r.helpful_count,
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    
    # Votes
    issue_votes = db.query(IssueVote).filter(IssueVote.user_id == user.id).all()
    for v in issue_votes:
        user_data["votes"]["issue_votes"].append({
            "issue_id": v.issue_id,
            "created_at": v.created_at.isoformat() if v.created_at else None
        })
    
    response_votes_data = db.query(ResponseVote).filter(ResponseVote.user_id == user.id).all()
    for v in response_votes_data:
        user_data["votes"]["response_votes"].append({
            "response_id": v.response_id,
            "created_at": v.created_at.isoformat() if v.created_at else None
        })
    
    # Ratings
    project_ratings = db.query(ProjectRating).filter(ProjectRating.user_id == user.id).all()
    for r in project_ratings:
        user_data["ratings"]["project_ratings_given"].append({
            "project_id": r.project_id,
            "stars": r.stars,
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    
    user_ratings_given = db.query(UserRating).filter(UserRating.rater_user_id == user.id).all()
    for r in user_ratings_given:
        user_data["ratings"]["user_ratings_given"].append({
            "rated_user_id": r.rated_user_id,
            "stars": r.stars,
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    
    user_ratings_received = db.query(UserRating).filter(UserRating.rated_user_id == user.id).all()
    for r in user_ratings_received:
        user_data["ratings"]["user_ratings_received"].append({
            "rater_user_id": r.rater_user_id,
            "stars": r.stars,
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    
    return JSONResponse(user_data)

@router.get("/privacy/download-data")
async def download_my_data(request: Request, db: Session = Depends(get_db)):
    """Download all user's data as JSON file (GDPR Right to Portability)"""
    from fastapi.responses import Response
    import json
    
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get all data using the existing endpoint logic
    data_response = await get_my_data(request, db)
    data = json.loads(data_response.body)
    
    # Add export metadata
    data["_export_info"] = {
        "exported_at": datetime.utcnow().isoformat(),
        "platform": "Xdest",
        "format_version": "1.0"
    }
    
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    
    return Response(
        content=json_str,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=xdest_data_{user.username}_{datetime.utcnow().strftime('%Y%m%d')}.json"
        }
    )

@router.delete("/privacy/delete-account")
async def delete_account(request: Request, db: Session = Depends(get_db)):
    """Delete user account and all associated data (GDPR Right to Erasure)
    
    WICHTIG: Punkte anderer User bleiben erhalten!
    - Antworten ANDERER User auf Issues des gelöschten Users bleiben erhalten
    - Nur eigene Antworten und eigene Issues werden entfernt
    """
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    from app.models import IssueVote, ProjectRating, UserRating
    from app.models.message import Message, MessageReply
    from app.models.offer import Offer
    
    try:
        # Delete in order of dependencies
        
        # 1. Delete votes BY this user
        db.query(ResponseVote).filter(ResponseVote.user_id == user.id).delete()
        db.query(IssueVote).filter(IssueVote.user_id == user.id).delete()
        
        # 2. Delete ratings BY this user
        db.query(ProjectRating).filter(ProjectRating.user_id == user.id).delete()
        db.query(UserRating).filter(UserRating.rater_user_id == user.id).delete()
        # Ratings FOR this user werden auch gelöscht
        db.query(UserRating).filter(UserRating.rated_user_id == user.id).delete()
        
        # 3. Delete message replies BY this user
        db.query(MessageReply).filter(MessageReply.user_id == user.id).delete()
        
        # 4. Delete messages BY this user (first delete their replies)
        user_messages = db.query(Message).filter(Message.user_id == user.id).all()
        for msg in user_messages:
            db.query(MessageReply).filter(MessageReply.message_id == msg.id).delete()
        db.query(Message).filter(Message.user_id == user.id).delete()
        
        # 5. Delete responses BY this user (seine eigenen Antworten)
        # Zuerst Votes auf diese Responses löschen
        user_responses = db.query(IssueResponse).filter(IssueResponse.user_id == user.id).all()
        for resp in user_responses:
            db.query(ResponseVote).filter(ResponseVote.response_id == resp.id).delete()
        db.query(IssueResponse).filter(IssueResponse.user_id == user.id).delete()
        
        # 6. Issues BY this user - NUR löschen wenn keine Antworten von anderen existieren
        user_issues = db.query(Issue).filter(Issue.user_id == user.id).all()
        for issue in user_issues:
            # Prüfe ob andere User geantwortet haben
            other_responses = db.query(IssueResponse).filter(
                IssueResponse.issue_id == issue.id,
                IssueResponse.user_id != user.id
            ).count()
            
            if other_responses == 0:
                # Keine Antworten von anderen - kann sicher gelöscht werden
                db.query(IssueVote).filter(IssueVote.issue_id == issue.id).delete()
                db.delete(issue)
            else:
                # Issue bleibt, aber setze user_id auf NULL (anonymisieren)
                issue.user_id = None
        
        # 7. Delete projects and their offers
        user_projects = db.query(Project).filter(Project.user_id == user.id).all()
        for project in user_projects:
            # Delete offers for this project
            db.query(Offer).filter(Offer.project_id == project.id).delete()
            
            # Delete posts and their comments for this project
            project_posts = db.query(Post).filter(Post.project_id == project.id).all()
            for post in project_posts:
                db.query(Comment).filter(Comment.post_id == post.id).delete()
            db.query(Post).filter(Post.project_id == project.id).delete()
            
            # Issues vom Projekt - wieder nur löschen wenn keine Antworten anderer
            project_issues = db.query(Issue).filter(Issue.project_id == project.id).all()
            for issue in project_issues:
                # Responses auf dieses Issue (von anderen Usern)
                other_responses = db.query(IssueResponse).filter(
                    IssueResponse.issue_id == issue.id
                ).count()
                
                if other_responses == 0:
                    db.query(IssueVote).filter(IssueVote.issue_id == issue.id).delete()
                    db.delete(issue)
                # else: Issue bleibt bestehen wegen Antworten anderer User
            
            # Projekt-Ratings löschen
            db.query(ProjectRating).filter(ProjectRating.project_id == project.id).delete()
            
            # Prüfe ob noch Issues am Projekt hängen
            remaining_issues = db.query(Issue).filter(Issue.project_id == project.id).count()
            if remaining_issues == 0:
                db.delete(project)
            # else: Projekt bleibt wegen der Issues mit Antworten
        
        # 8. Delete remaining comments and posts by this user (on OTHER projects)
        # First delete comments on posts by this user
        user_posts = db.query(Post).filter(Post.user_id == user.id).all()
        for post in user_posts:
            db.query(Comment).filter(Comment.post_id == post.id).delete()
        db.query(Post).filter(Post.user_id == user.id).delete()
        db.query(Comment).filter(Comment.user_id == user.id).delete()
        
        # 9. Finally delete the user
        db.delete(user)
        db.commit()
        
        # Clear session
        request.session.clear()
        
        return JSONResponse({"message": "Account and all data deleted successfully"})
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")


# ========== OFFERS ==========

@router.post("/offers")
async def create_offer(
    request: Request,
    project_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    offer_type: str = Form("other"),
    original_price: str = Form(None),
    offer_price: str = Form(None),
    discount_percent: int = Form(None),
    duration: str = Form(None),
    coupon_code: str = Form(None),
    redemption_url: str = Form(None),
    max_redemptions: int = Form(None),
    valid_until: str = Form(None),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if user.role == "tester":
        raise HTTPException(status_code=403, detail="Testers cannot create offers")
    
    # Verify project ownership
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or not owned by you")
    
    # Parse valid_until date
    valid_until_date = None
    if valid_until:
        try:
            valid_until_date = datetime.strptime(valid_until, "%Y-%m-%d")
        except ValueError:
            pass
    
    # Create offer
    offer = Offer(
        project_id=project_id,
        title=title,
        description=description,
        offer_type=offer_type,
        original_price=original_price or None,
        offer_price=offer_price or None,
        discount_percent=discount_percent,
        duration=duration or None,
        coupon_code=coupon_code.upper() if coupon_code else None,
        redemption_url=redemption_url or None,
        max_redemptions=max_redemptions,
        valid_until=valid_until_date
    )
    
    db.add(offer)
    db.commit()
    
    return RedirectResponse(url="/offers", status_code=302)


@router.get("/offers/{offer_id}/delete")
async def delete_offer(
    offer_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # Verify ownership via project
    if offer.project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db.delete(offer)
    db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=302)


@router.post("/offers/{offer_id}/edit")
async def update_offer(
    offer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(...),
    description: str = Form(...),
    offer_type: str = Form(...),
    original_price: str = Form(None),
    offer_price: str = Form(None),
    discount_percent: int = Form(None),
    duration: str = Form(None),
    coupon_code: str = Form(None),
    redemption_url: str = Form(None),
    max_redemptions: int = Form(None),
    valid_until: str = Form(None),
    is_active: bool = Form(True)
):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # Verify ownership via project
    if offer.project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Update offer fields
    offer.title = title
    offer.description = description
    offer.offer_type = offer_type
    offer.original_price = original_price if original_price else None
    offer.offer_price = offer_price if offer_price else None
    offer.discount_percent = discount_percent if discount_percent else None
    offer.duration = duration if duration else None
    offer.coupon_code = coupon_code if coupon_code else None
    offer.redemption_url = redemption_url if redemption_url else None
    offer.max_redemptions = max_redemptions if max_redemptions else None
    offer.is_active = is_active
    
    if valid_until:
        try:
            offer.valid_until = datetime.strptime(valid_until, "%Y-%m-%d")
        except:
            pass
    else:
        offer.valid_until = None
    
    offer.updated_at = datetime.utcnow()
    db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=302)


@router.put("/offers/{offer_id}/toggle")
async def toggle_offer(
    offer_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # Verify ownership via project
    if offer.project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    offer.is_active = not offer.is_active
    db.commit()
    
    return JSONResponse({"message": "Offer toggled", "is_active": offer.is_active})


# ============================================
# Community Messages (for all users including testers)
# ============================================

@router.post("/messages")
async def create_message(
    request: Request,
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    """Create a new community message - available to all logged in users"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if not content.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    message = Message(
        user_id=user.id,
        content=content.strip()
    )
    db.add(message)
    db.commit()
    
    return RedirectResponse(url="/community", status_code=302)

@router.post("/messages/{message_id}/reply")
async def reply_to_message(
    message_id: int,
    request: Request,
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    """Reply to a community message - available to all logged in users"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if not content.strip():
        raise HTTPException(status_code=400, detail="Reply cannot be empty")
    
    reply = MessageReply(
        message_id=message_id,
        user_id=user.id,
        content=content.strip()
    )
    db.add(reply)
    db.commit()
    
    return RedirectResponse(url="/community", status_code=302)

@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete own message"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Delete all replies first
    db.query(MessageReply).filter(MessageReply.message_id == message_id).delete()
    db.delete(message)
    db.commit()
    
    return JSONResponse({"message": "Deleted"})

@router.delete("/messages/reply/{reply_id}")
async def delete_reply(
    reply_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete own reply"""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    reply = db.query(MessageReply).filter(MessageReply.id == reply_id).first()
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    
    if reply.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db.delete(reply)
    db.commit()
    
    return JSONResponse({"message": "Deleted"})


# ==================== COMMUNITY VOTE SYSTEM ====================

@router.post("/messages/{message_id}/vote")
async def vote_message(
    message_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Up- oder Downvote für eine Community Message"""
    from app.models import MessageVote
    
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.user_id == user.id:
        return JSONResponse({"error": "Cannot vote for own message"}, status_code=400)
    
    try:
        body = await request.json()
        vote_type = body.get("vote_type", "upvote")
    except:
        vote_type = "upvote"
    
    if vote_type not in ("upvote", "downvote"):
        return JSONResponse({"error": "Invalid vote type"}, status_code=400)
    
    existing_vote = db.query(MessageVote).filter(
        MessageVote.message_id == message_id,
        MessageVote.user_id == user.id
    ).first()
    
    if existing_vote:
        if existing_vote.vote_type == vote_type:
            if vote_type == "upvote":
                message.upvote_count = max(0, message.upvote_count - 1)
            else:
                message.downvote_count = max(0, message.downvote_count - 1)
            db.delete(existing_vote)
            db.commit()
            return JSONResponse({"voted": None, "upvotes": message.upvote_count, "downvotes": message.downvote_count})
        else:
            if existing_vote.vote_type == "upvote":
                message.upvote_count = max(0, message.upvote_count - 1)
                message.downvote_count = message.downvote_count + 1
            else:
                message.downvote_count = max(0, message.downvote_count - 1)
                message.upvote_count = message.upvote_count + 1
            existing_vote.vote_type = vote_type
            db.commit()
            return JSONResponse({"voted": vote_type, "upvotes": message.upvote_count, "downvotes": message.downvote_count})
    else:
        vote = MessageVote(message_id=message_id, user_id=user.id, vote_type=vote_type)
        db.add(vote)
        if vote_type == "upvote":
            message.upvote_count = message.upvote_count + 1
        else:
            message.downvote_count = message.downvote_count + 1
        db.commit()
        return JSONResponse({"voted": vote_type, "upvotes": message.upvote_count, "downvotes": message.downvote_count})


@router.post("/messages/reply/{reply_id}/vote")
async def vote_message_reply(
    reply_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Up- oder Downvote für eine Community Reply"""
    from app.models import MessageReplyVote
    
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    reply = db.query(MessageReply).filter(MessageReply.id == reply_id).first()
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    
    if reply.user_id == user.id:
        return JSONResponse({"error": "Cannot vote for own reply"}, status_code=400)
    
    try:
        body = await request.json()
        vote_type = body.get("vote_type", "upvote")
    except:
        vote_type = "upvote"
    
    if vote_type not in ("upvote", "downvote"):
        return JSONResponse({"error": "Invalid vote type"}, status_code=400)
    
    existing_vote = db.query(MessageReplyVote).filter(
        MessageReplyVote.reply_id == reply_id,
        MessageReplyVote.user_id == user.id
    ).first()
    
    if existing_vote:
        if existing_vote.vote_type == vote_type:
            if vote_type == "upvote":
                reply.upvote_count = max(0, reply.upvote_count - 1)
            else:
                reply.downvote_count = max(0, reply.downvote_count - 1)
            db.delete(existing_vote)
            db.commit()
            return JSONResponse({"voted": None, "upvotes": reply.upvote_count, "downvotes": reply.downvote_count})
        else:
            if existing_vote.vote_type == "upvote":
                reply.upvote_count = max(0, reply.upvote_count - 1)
                reply.downvote_count = reply.downvote_count + 1
            else:
                reply.downvote_count = max(0, reply.downvote_count - 1)
                reply.upvote_count = reply.upvote_count + 1
            existing_vote.vote_type = vote_type
            db.commit()
            return JSONResponse({"voted": vote_type, "upvotes": reply.upvote_count, "downvotes": reply.downvote_count})
    else:
        vote = MessageReplyVote(reply_id=reply_id, user_id=user.id, vote_type=vote_type)
        db.add(vote)
        if vote_type == "upvote":
            reply.upvote_count = reply.upvote_count + 1
        else:
            reply.downvote_count = reply.downvote_count + 1
        db.commit()
        return JSONResponse({"voted": vote_type, "upvotes": reply.upvote_count, "downvotes": reply.downvote_count})


# Logo Size Logger Endpoint
import logging

# Setup logo logger
logo_logger = logging.getLogger('logo_size')
logo_logger.setLevel(logging.INFO)

# Create file handler for logo size changes
logo_handler = logging.FileHandler('logo_size.log')
logo_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logo_logger.addHandler(logo_handler)

@router.post("/log/logo-size")
async def log_logo_size(request: Request):
    """Log logo size changes from client"""
    try:
        data = await request.json()
        
        log_entry = {
            "event": data.get("event"),
            "page": data.get("page"),
            "logoSrc": data.get("logoSrc"),
            "oldSize": data.get("oldSize"),
            "newSize": data.get("newSize"),
            "viewport": data.get("viewport"),
            "timestamp": data.get("timestamp"),
            "client_ip": request.client.host if request.client else "unknown"
        }
        
        logo_logger.info(json.dumps(log_entry))
        
        return JSONResponse({"status": "logged"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


# ==================== OFFER REDEMPTION SYSTEM ====================

@router.post("/offers/{offer_id}/claim")
async def claim_offer(
    offer_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Claim an offer coupon code. User agrees to test the project within 7 days."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    if not offer.is_valid:
        raise HTTPException(status_code=400, detail="This offer is no longer available")
    
    # Check if user already claimed this offer
    existing = db.query(OfferRedemption).filter(
        OfferRedemption.offer_id == offer_id,
        OfferRedemption.user_id == user.id
    ).first()
    
    if existing:
        return JSONResponse({
            "status": "already_claimed",
            "coupon_code": offer.coupon_code,
            "redemption_url": offer.redemption_url,
            "deadline": existing.deadline.isoformat(),
            "fulfilled": existing.fulfilled
        })
    
    # Can't claim your own project's offers
    if offer.project.user_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot claim your own project's offers")
    
    # Create redemption
    from datetime import timedelta
    now = datetime.utcnow()
    redemption = OfferRedemption(
        offer_id=offer_id,
        user_id=user.id,
        project_id=offer.project_id,
        claimed_at=now,
        deadline=now + timedelta(days=7)
    )
    db.add(redemption)
    
    # Increment redemption counter
    offer.current_redemptions = (offer.current_redemptions or 0) + 1
    
    db.commit()
    
    return JSONResponse({
        "status": "claimed",
        "coupon_code": offer.coupon_code,
        "redemption_url": offer.redemption_url,
        "deadline": redemption.deadline.isoformat(),
        "project_id": offer.project_id,
        "project_name": offer.project.name
    })

@router.get("/offers/{offer_id}/check-claim")
async def check_offer_claim(
    offer_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Check if current user has claimed this offer."""
    user = await get_current_user_optional(request, db)
    if not user:
        return JSONResponse({"claimed": False, "logged_in": False})
    
    redemption = db.query(OfferRedemption).filter(
        OfferRedemption.offer_id == offer_id,
        OfferRedemption.user_id == user.id
    ).first()
    
    if redemption:
        offer = db.query(Offer).filter(Offer.id == offer_id).first()
        return JSONResponse({
            "claimed": True,
            "logged_in": True,
            "coupon_code": offer.coupon_code if offer else None,
            "redemption_url": offer.redemption_url if offer else None,
            "fulfilled": redemption.fulfilled,
            "deadline": redemption.deadline.isoformat(),
            "is_overdue": redemption.is_overdue
        })
    
    return JSONResponse({"claimed": False, "logged_in": True})

@router.get("/user/pending-obligations")
async def get_pending_obligations(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get all pending test obligations for the current user."""
    user = await get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    pending = db.query(OfferRedemption).filter(
        OfferRedemption.user_id == user.id,
        OfferRedemption.fulfilled == False
    ).all()
    
    obligations = []
    for r in pending:
        offer = db.query(Offer).filter(Offer.id == r.offer_id).first()
        project = db.query(Project).filter(Project.id == r.project_id).first()
        obligations.append({
            "redemption_id": r.id,
            "offer_title": offer.title if offer else "Unknown",
            "project_id": r.project_id,
            "project_name": project.name if project else "Unknown",
            "claimed_at": r.claimed_at.isoformat(),
            "deadline": r.deadline.isoformat(),
            "days_remaining": r.days_remaining,
            "is_overdue": r.is_overdue,
            "karma_penalty_applied": r.karma_penalty_applied
        })
    
    return JSONResponse({"obligations": obligations})

