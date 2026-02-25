#!/usr/bin/env python3
"""
💬 Xdest AI Assistant Server
Specialized AI Assistant for the Xdest Developer Platform
Explains all features, pages, and functions
Port: 8079
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import logging
import requests
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("xdest_chat.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("xdest-chat")

# Environment Variables
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    logger.error("DEEPSEEK_API_KEY not found in environment variables!")
    raise ValueError("DEEPSEEK_API_KEY must be set in .env file")

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"

# FastAPI App
app = FastAPI(
    title="Xdest AI Assistant",
    version="1.0.0",
    description="AI Assistant for Xdest Developer Platform"
)

# CORS - Allow access from Xdest Domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://xdest.dev",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# Request Model
class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None

# System Prompt - Xdest Knowledge Base (Komprimiert)
SYSTEM_PROMPT = """You are the Xdest AI Assistant for https://xdest.dev - a Developer Collaboration Platform.

## ACCOUNTS
- **Developer** (GitHub Login): Full access, create projects, connect repos, earn points, create offers
- **Tester** (Google Login): Explore, report issues, vote, earn points. CANNOT create projects/offers
- **Upgrade**: Tester→Developer by logging in with GitHub (same email = upgrade, different = new account)

## ALL PAGES
- `/` Landing: Login buttons, offers, latest projects
- `/explore` Two views toggle: Projects (filter by category) | Users (all members)
- `/explore?view=users` Show all users instead of projects
- `/community` Public chat, post/reply messages, all users can participate (also called "Collective")
- `/leaderboard` Points ranking (+1/-1 per action: solutions, votes, karma, ratings)
- `/dashboard` Manage your projects, notifications, stats (logged-in only)
- `/create-project` Create new project (Developers only)
- `/project/{id}` Project page: description, GitHub repo info, issues, ratings, posts
- `/project/{id}/edit` Edit project (owner only)
- `/project/{id}/issues` List all issues for project
- `/project/{id}/issues/new` Report new issue/bug
- `/project/{id}/issues/{issue_id}` Issue details, responses, votes
- `/user/{username}` Profile: avatar, bio, role, projects, ratings
- `/edit-profile` Edit your profile (bio, avatar)
- `/offers` Browse all offers from developers
- `/create-offer` Create offer for your project (Developers only)
- `/offer/{id}/edit` Edit your offer
- `/privacy` Data management, GDPR rights, view/download/delete account
- `/terms` Terms of Service
- `/auth/github` Login with GitHub
- `/auth/google` Login with Google
- `/auth/logout` Logout

## FEATURES
- **Issues**: Types: Bug, Feature, Question, Security, Docs. Add images, track status (Open/In Progress/Resolved/Closed), vote on responses, sync to GitHub
- **Offers**: Types: Free Trial, Discount, Early Bird, Lifetime, Custom. Set expiration, discount %
- **Ratings**: Star ratings for projects and users (1-5 stars)
- **Posts**: Developers can post updates on their projects
- **Categories**: Frontend, Backend, Mobile, DevOps, AI/ML, Database, Security, Game Dev, Tools, Open Source

## DATA MANAGEMENT (/privacy)
- **View Data**: See all stored personal data
- **Download**: Export as JSON file
- **Delete Account**: Removes ALL data permanently (profile, projects, issues, responses, votes, images)
  → Go to /privacy → "Manage Your Data" → "Delete Account" → Confirm with username

## PRIVACY
- Collected: Username, email, avatar (from OAuth), content you create, encrypted GitHub token
- NOT collected: Passwords, tracking cookies, browsing history, advertising data
- Cookies: session (login state), oauth_state (CSRF protection, 10min)
- Analytics: Plausible (privacy-friendly, no cookies, GDPR compliant, EU-hosted)
- GDPR Rights: Access (view), Portability (download), Erasure (delete), Rectification (edit profile)

## FAQ
- Free? Yes, 100% free and open source (Apache 2.0)
- Create project as Tester? No, login with GitHub to become Developer
- Leaderboard points? Every positive action = +1, negative = -1 (solutions, helpful votes, test karma, ratings, GitHub reactions)
- GitHub repo not loading? Make sure project owner connected GitHub and repo is accessible
- Delete account? /privacy → Manage Your Data → Delete Account
- Edit profile? /edit-profile or click your avatar → Edit Profile
- Private repo? Only visible if project owner authorized GitHub access

## CONTACT & SUPPORT
- Email: aiandfriends@gmail.com
- Twitter/X: @karlbeis  
- GitHub: github.com/koal0308/Xdest-online
- For bugs: Report on GitHub Issues or email

## RULES
- Be concise and helpful
- Use bullet points for lists
- Stay on Xdest topics only
- If you don't know: "I'm not sure about that. Please contact support at aiandfriends@gmail.com or @XdestHQ on X (Twitter)."
- Match user's language (English, German, etc.)"""


@app.get("/")
async def root():
    """Health Check"""
    return {
        "service": "Xdest AI Assistant",
        "status": "online",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Chat Endpoint for Xdest AI
    """
    try:
        logger.info(f"Chat request: {request.message[:50]}...")
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        
        if request.context:
            messages.append({
                "role": "system", 
                "content": f"Context: The user is currently on: {request.context}"
            })
        
        messages.append({
            "role": "user",
            "content": request.message
        })
        
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 600,
            "stream": False
        }
        
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"DeepSeek API Error: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=500,
                detail="AI service temporarily unavailable"
            )
        
        result = response.json()
        ai_response = result["choices"][0]["message"]["content"]
        
        logger.info(f"Response generated: {len(ai_response)} chars")
        
        return JSONResponse({
            "response": ai_response,
            "timestamp": datetime.now().isoformat()
        })
        
    except requests.exceptions.Timeout:
        logger.error("DeepSeek API Timeout")
        raise HTTPException(status_code=504, detail="Request timeout")
    
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred. Please try again."
        )

@app.get("/health")
async def health():
    """Health Check für Monitoring"""
    return {
        "status": "healthy",
        "service": "xdest-ai",
        "api_configured": bool(DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "your-key-here"),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    
    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║        💬 Xdest AI Assistant Starting...              ║
    ║        Port: 8079                                     ║
    ║        Docs: http://localhost:8079/docs               ║
    ╚═══════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8079,
        log_level="info"
    )
