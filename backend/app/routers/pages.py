from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import User, Project, Post, Comment, Issue, IssueResponse, Offer, Message, MessageReply
from app.dependencies import get_current_user_optional, get_current_user
import httpx
from typing import Optional
from datetime import datetime

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    projects = db.query(Project).order_by(Project.created_at.desc()).limit(6).all()
    offers = db.query(Offer).filter(Offer.is_active == True).order_by(Offer.created_at.desc()).limit(5).all()
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "user": user,
        "projects": projects,
        "offers": offers
    })

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    projects = db.query(Project).filter(Project.user_id == user.id).order_by(Project.created_at.desc()).all()
    
    # Get user's offers (through their projects)
    project_ids = [p.id for p in projects]
    offers = db.query(Offer).filter(Offer.project_id.in_(project_ids)).order_by(Offer.created_at.desc()).all() if project_ids else []
    
    # Count unread issues and responses for notifications
    unread_issues_count = 0
    unread_responses_count = 0
    unread_issues = []
    if project_ids:
        # Unread issues on user's projects
        unread_issues = db.query(Issue).filter(
            Issue.project_id.in_(project_ids),
            Issue.is_read_by_owner == False
        ).order_by(Issue.created_at.desc()).limit(10).all()
        unread_issues_count = len(unread_issues)
        
        # Unread responses on issues of user's projects
        unread_responses_count = db.query(IssueResponse).join(Issue).filter(
            Issue.project_id.in_(project_ids),
            IssueResponse.is_read_by_owner == False
        ).count()
    
    total_notifications = unread_issues_count + unread_responses_count
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "projects": projects,
        "offers": offers,
        "unread_issues": unread_issues,
        "unread_issues_count": unread_issues_count,
        "unread_responses_count": unread_responses_count,
        "total_notifications": total_notifications
    })

@router.get("/user/{username}", response_class=HTMLResponse)
async def user_profile(username: str, request: Request, db: Session = Depends(get_db)):
    current_user = await get_current_user_optional(request, db)
    profile_user = db.query(User).filter(User.username == username).first()
    
    if not profile_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    projects = db.query(Project).filter(Project.user_id == profile_user.id).order_by(Project.created_at.desc()).all()
    is_owner = current_user and current_user.id == profile_user.id
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": current_user,
        "profile_user": profile_user,
        "projects": projects,
        "is_owner": is_owner
    })

@router.get("/project/{project_id}", response_class=HTMLResponse)
async def project_page(project_id: int, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    posts = db.query(Post).filter(Post.project_id == project_id).order_by(Post.created_at.desc()).all()
    is_owner = user and user.id == project.user_id
    
    # Fetch GitHub repo info if URL exists
    github_info = None
    if project.github_url:
        github_info = await fetch_github_repo_info(project.github_url)
    
    return templates.TemplateResponse("project.html", {
        "request": request,
        "user": user,
        "project": project,
        "posts": posts,
        "is_owner": is_owner,
        "github_info": github_info
    })

@router.get("/project/{project_id}/edit", response_class=HTMLResponse)
async def edit_project_page(project_id: int, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Only owner can edit
    if project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return templates.TemplateResponse("edit_project.html", {
        "request": request,
        "user": user,
        "project": project
    })

@router.get("/create-project", response_class=HTMLResponse)
async def create_project_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    # Testers cannot create projects
    if user.role == "tester":
        return RedirectResponse(url="/dashboard", status_code=302)
    
    return templates.TemplateResponse("create_project.html", {
        "request": request,
        "user": user
    })

@router.get("/edit-profile", response_class=HTMLResponse)
async def edit_profile_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("edit_profile.html", {
        "request": request,
        "user": user
    })

@router.get("/explore", response_class=HTMLResponse)
async def explore_page(request: Request, category: Optional[str] = None, q: Optional[str] = None, view: Optional[str] = None, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    
    # Developer categories
    categories = [
        {"id": "frontend", "name": "Frontend", "icon": "🎨", "tags": ["react", "vue", "angular", "css", "html", "javascript", "typescript", "tailwind", "nextjs", "svelte"]},
        {"id": "backend", "name": "Backend", "icon": "⚙️", "tags": ["python", "node", "java", "go", "rust", "php", "ruby", "django", "fastapi", "express", "spring"]},
        {"id": "mobile", "name": "Mobile", "icon": "📱", "tags": ["ios", "android", "flutter", "react-native", "swift", "kotlin", "mobile"]},
        {"id": "devops", "name": "DevOps", "icon": "🚀", "tags": ["docker", "kubernetes", "aws", "azure", "gcp", "ci/cd", "terraform", "ansible", "jenkins"]},
        {"id": "ai-ml", "name": "AI / ML", "icon": "🤖", "tags": ["machine-learning", "ai", "tensorflow", "pytorch", "nlp", "computer-vision", "data-science", "deep-learning"]},
        {"id": "database", "name": "Database", "icon": "🗄️", "tags": ["sql", "postgres", "mongodb", "redis", "mysql", "database", "graphql"]},
        {"id": "security", "name": "Security", "icon": "🔒", "tags": ["security", "cryptography", "penetration", "authentication", "oauth"]},
        {"id": "gamedev", "name": "Game Dev", "icon": "🎮", "tags": ["unity", "unreal", "gamedev", "game", "3d", "graphics"]},
        {"id": "tools", "name": "Tools", "icon": "🛠️", "tags": ["cli", "tool", "automation", "script", "utility", "productivity"]},
        {"id": "opensource", "name": "Open Source", "icon": "💚", "tags": ["opensource", "open-source", "community", "contribution"]},
    ]
    
    # View mode: projects or users
    current_view = view if view in ["projects", "users"] else "projects"
    
    # Base query for posts with projects
    posts_query = db.query(Post).join(Project).join(User, Post.user_id == User.id)
    
    # Base query for projects
    projects_query = db.query(Project)
    
    # Base query for users
    users_query = db.query(User)
    
    # Search filter
    search_query = q.strip() if q else None
    if search_query:
        search_filter = or_(
            Project.name.ilike(f"%{search_query}%"),
            Project.description.ilike(f"%{search_query}%"),
            Project.tags.ilike(f"%{search_query}%")
        )
        posts_query = posts_query.filter(search_filter)
        projects_query = projects_query.filter(search_filter)
        
        # Search users by username or bio
        user_search_filter = or_(
            User.username.ilike(f"%{search_query}%"),
            User.bio.ilike(f"%{search_query}%")
        )
        users_query = users_query.filter(user_search_filter)
    
    # Filter by category if selected
    active_category = None
    if category:
        for cat in categories:
            if cat["id"] == category:
                active_category = cat
                # Filter posts where project tags contain any of the category tags
                tag_filters = [Project.tags.ilike(f"%{tag}%") for tag in cat["tags"]]
                posts_query = posts_query.filter(or_(*tag_filters))
                projects_query = projects_query.filter(or_(*tag_filters))
                break
    
    posts = posts_query.order_by(Post.created_at.desc()).limit(50).all()
    projects = projects_query.order_by(Project.created_at.desc()).all()
    all_users = users_query.order_by(User.created_at.desc()).all()
    
    return templates.TemplateResponse("explore.html", {
        "request": request,
        "user": user,
        "projects": projects,
        "posts": posts,
        "all_users": all_users,
        "categories": categories,
        "active_category": active_category,
        "current_category": category,
        "search_query": search_query,
        "current_view": current_view
    })

@router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    return templates.TemplateResponse("leaderboard.html", {
        "request": request,
        "user": user
    })

@router.get("/community", response_class=HTMLResponse)
async def community_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    messages = db.query(Message).order_by(Message.created_at.desc()).limit(50).all()
    return templates.TemplateResponse("community.html", {
        "request": request,
        "user": user,
        "messages": messages
    })

async def fetch_github_repo_info(github_url: str):
    """Fetch repo info from GitHub API"""
    try:
        # Extract owner/repo from URL
        parts = github_url.rstrip('/').split('/')
        if len(parts) >= 2:
            owner = parts[-2]
            repo = parts[-1]
            
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}",
                    headers={"Accept": "application/vnd.github.v3+json"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "name": data.get("name"),
                        "description": data.get("description"),
                        "stars": data.get("stargazers_count"),
                        "forks": data.get("forks_count"),
                        "language": data.get("language"),
                        "updated_at": data.get("updated_at"),
                        "open_issues": data.get("open_issues_count")
                    }
    except Exception:
        pass
    return None

# ==================== ISSUE PAGES ====================

@router.get("/project/{project_id}/issues", response_class=HTMLResponse)
async def project_issues_page(
    project_id: int, 
    request: Request, 
    status: Optional[str] = None,
    issue_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Liste aller Issues für ein Projekt"""
    user = await get_current_user_optional(request, db)
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Query Issues mit Filtern
    query = db.query(Issue).filter(Issue.project_id == project_id)
    
    if status:
        query = query.filter(Issue.status == status)
    if issue_type:
        query = query.filter(Issue.issue_type == issue_type)
    
    issues = query.order_by(Issue.created_at.desc()).all()
    is_owner = user and user.id == project.user_id
    
    # Zähle Issues nach Status
    issue_counts = {
        "all": db.query(Issue).filter(Issue.project_id == project_id).count(),
        "open": db.query(Issue).filter(Issue.project_id == project_id, Issue.status == "open").count(),
        "in_progress": db.query(Issue).filter(Issue.project_id == project_id, Issue.status == "in_progress").count(),
        "resolved": db.query(Issue).filter(Issue.project_id == project_id, Issue.status == "resolved").count(),
        "closed": db.query(Issue).filter(Issue.project_id == project_id, Issue.status == "closed").count(),
    }
    
    return templates.TemplateResponse("issues.html", {
        "request": request,
        "user": user,
        "project": project,
        "issues": issues,
        "is_owner": is_owner,
        "issue_counts": issue_counts,
        "current_status": status,
        "current_type": issue_type
    })

@router.get("/project/{project_id}/issues/new", response_class=HTMLResponse)
async def new_issue_page(project_id: int, request: Request, db: Session = Depends(get_db)):
    """Formular für neues Issue"""
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url=f"/project/{project_id}", status_code=302)
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return templates.TemplateResponse("new_issue.html", {
        "request": request,
        "user": user,
        "project": project
    })

@router.get("/project/{project_id}/issues/{issue_id}", response_class=HTMLResponse)
async def issue_detail_page(project_id: int, issue_id: int, request: Request, db: Session = Depends(get_db)):
    """Detailansicht eines Issues"""
    user = await get_current_user_optional(request, db)
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    issue = db.query(Issue).filter(Issue.id == issue_id, Issue.project_id == project_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    is_owner = user and user.id == project.user_id
    is_reporter = user and user.id == issue.user_id
    
    # Mark issue and its responses as read if owner is viewing
    if is_owner:
        if not issue.is_read_by_owner:
            issue.is_read_by_owner = True
        # Mark all responses as read
        for response in issue.responses:
            if not response.is_read_by_owner:
                response.is_read_by_owner = True
        db.commit()
    
    return templates.TemplateResponse("issue_detail.html", {
        "request": request,
        "user": user,
        "project": project,
        "issue": issue,
        "is_owner": is_owner,
        "is_reporter": is_reporter
    })


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    return templates.TemplateResponse("privacy.html", {
        "request": request,
        "user": user
    })


@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    return templates.TemplateResponse("terms.html", {
        "request": request,
        "user": user
    })


# ========== OFFERS ==========

@router.get("/offers", response_class=HTMLResponse)
async def offers_page(
    request: Request, 
    db: Session = Depends(get_db),
    q: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = "active",
    sort: Optional[str] = "newest"
):
    user = await get_current_user_optional(request, db)
    
    # Base query
    query = db.query(Offer)
    
    # Search
    if q:
        query = query.join(Project).filter(
            or_(
                Offer.title.ilike(f"%{q}%"),
                Offer.description.ilike(f"%{q}%"),
                Project.name.ilike(f"%{q}%")
            )
        )
    
    # Type filter
    if type:
        query = query.filter(Offer.offer_type == type)
    
    # Status filter (active only by default)
    if status == "active":
        query = query.filter(
            Offer.is_active == True,
            or_(Offer.valid_until == None, Offer.valid_until > datetime.utcnow())
        )
    
    # Sort
    if sort == "newest":
        query = query.order_by(Offer.created_at.desc())
    elif sort == "ending_soon":
        query = query.filter(Offer.valid_until != None).order_by(Offer.valid_until.asc())
    elif sort == "discount":
        query = query.order_by(Offer.discount_percent.desc().nullslast())
    
    offers = query.all()
    
    return templates.TemplateResponse("offers.html", {
        "request": request,
        "user": user,
        "offers": offers,
        "search_query": q,
        "current_type": type,
        "current_status": status,
        "current_sort": sort
    })


@router.get("/create-offer", response_class=HTMLResponse)
async def create_offer_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    if user.role == "tester":
        raise HTTPException(status_code=403, detail="Testers cannot create offers")
    
    # Get user's projects
    projects = db.query(Project).filter(Project.user_id == user.id).order_by(Project.name).all()
    
    if not projects:
        return RedirectResponse(url="/create-project?message=Create a project first", status_code=302)
    
    return templates.TemplateResponse("create_offer.html", {
        "request": request,
        "user": user,
        "projects": projects
    })


@router.get("/offer/{offer_id}/edit", response_class=HTMLResponse)
async def edit_offer_page(offer_id: int, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    # Verify ownership via project
    if offer.project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return templates.TemplateResponse("edit_offer.html", {
        "request": request,
        "user": user,
        "offer": offer
    })
