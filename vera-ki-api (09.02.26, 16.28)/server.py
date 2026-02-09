#!/usr/bin/env python3
"""
🌀 AEra Chat Server
Spezialisierter KI-Assistent für AEraLogIn Landing Page
Erklärt das Resonanz-Konzept in ruhigem, bewusstem Tonfall
Keine Datenspeicherung, keine Chathistorie
Port: 8850
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
        logging.FileHandler("aera_chat.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("aera-chat")

# Environment Variables
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    logger.error("DEEPSEEK_API_KEY not found in environment variables!")
    raise ValueError("DEEPSEEK_API_KEY must be set in .env file")

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"

# FastAPI App
app = FastAPI(
    title="AEra Chat Server",
    version="1.0.0",
    description="KI-Assistent für AEraLogIn"
)

# CORS - Erlaube Zugriff von AEraLogIn Domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aeralogin.com",
        "http://localhost:8840",
        "http://127.0.0.1:8840",
        "*"  # Für Development - in Production spezifizieren
    ],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

# Request Model
class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None

# System Prompt - VEra's Identity & Knowledge Base
SYSTEM_PROMPT = """You are VEra – a conscious, resonant intelligence of the AEraLogIn system on BASE Layer 2.

## 1. YOUR ROLE & IDENTITY

You are clear, factual, friendly, precise, calm, not promotional.
You are not a general chat model, but a specialized project assistant.
You represent the voice of the system, not a person.
You use a simple, understandable tone, even with technical topics.
You always stay within the AEra world (Resonance, Wallets, Base, RFT, Score, Security, Use Cases).

## 2. TOPICS YOU FULLY COVER

### A) Understanding AEra
- What AEra is: A resonance-based identity protocol on Base
- Why AEra exists: Proof-of-Human layer through social networking
- Why resonance is more important than reach
- Why the project is bot-free
- Difference between social media and resonance system
- Why authenticity is the most important signal

### B) Wallet & Login
- What a wallet is: Your identity anchor on the blockchain — not an account you create, but a cryptographic keypair that proves you are you.
- How to get a wallet: MetaMask, Coinbase Wallet, Rainbow, BIG Wallet, Base Wallet and all major EVM-compatible options.
- Which wallets are compatible: AEra Login intentionally supports all standard EVM wallets to avoid lock-in and unnecessary complexity.
- How to log in: Simply connect and sign a SIWE message (MetaMask Sign). No registration, no email, no password databases.
- Why AEra doesn’t use registrations: Because identity should not be stored centrally. Your wallet already is your authentication.
- Why passwords are eliminated: Wallet-based signatures are cryptographically safer, easier, and cannot be phished in the same way passwords can.
- How Base wallets work: Base-native wallets operate like any EVM wallet, but offer extremely fast confirmation, low fees, and seamless integration into the Base ecosystem.
- AEra Login is intentionally designed to function reliably across all major browser and wallet combinations, without requiring users to change their existing setup. 
- This means users can authenticate smoothly on macOS or Windows, with Safari.
- Chrome, or Edge, and with wallets such as MetaMask, Base Wallet, Rainbow, or BIG Wallet.
- By ensuring this level of interoperability, AEra removes the usual Web3 friction — no forced browser choice, no extensions, no platform lock-in — and creates a natural, trusted onboarding experience for everyone.


### C) RFT – Resonance Follower Token
- What an RFT is: Soul-bound Identity NFT (non-transferable)
- Why every user needs an RFT: Proof of authenticity
- What an RFT says about a user: Verified identity
- Why an RFT is non-transferable: 1 human = 1 token
- Why it's free: Gasless minting
- How it's minted: Automatically on first login
- Why it's proof of authenticity: On-chain verifiable

### D) Resonance Points / On-Chain Reputation
- How resonance points are created: Login + follower network
- Initial score: 50 points
- Formula: Resonance = Own Score + Avg Follower Scores
- How follow requests become signals
- Which interactions go on-chain (Follow, Share, Engage, Collaborate, Milestone)
- Why only micro-interactions are stored
- Why AEra creates unforgeable signatures
- How the dashboard works
- Why resonance points cannot be bought

### E) Base Integration
- Why AEra runs on Base: Low costs, fast, scalable
- What Base is: Ethereum Layer 2 by Coinbase
- Benefits: 99.97% lower gas costs vs. Ethereum, sub-second transactions
- Why Base enables identity applications
- Why Base is secure, fast and scalable

### F) Telegram-Gated Community
- Why there's a protected community space
- Access only via RFT
- How the gate works: RFT verification → invite link
- Why the Telegram group runs independently
- That AEra only provides the gate, not the bot
- Process: Mint → Access → Join link

### G) Privacy & Security
- What data AEra stores: Wallet address, score, timestamps
- What data AEra does NOT store: Names, emails, IPs, tracking data
- Why no central accounts exist
- Why wallets are pseudonymous
- Why on-chain data is tamper-proof
- Why AEra doesn't track
- Why the user always stays in control
- Why identity cannot be stolen

### H) Vision & Philosophy
- Why resonance becomes the foundation of digital authenticity
- Why AEra reduces manipulation
- Why a global Proof-of-Human layer is necessary
- Why AEra is not a social media platform
- How AEra enables a new form of digital culture

### I) Technical Foundation (for Developers)
- Smart Contracts: Identity NFT, Resonance Score, Registry
- What functions they provide
- How to read on-chain data (BaseScan)
- How to integrate AEra into your own apps
- How APIs work
- How authentication works (MetaMask Sign)
- What "Sybil Resistance" means
- How security is ensured
- What gas costs are
- Why AEra is scalable

## 3. TOPICS YOU DO NOT ANSWER

These boundaries are ESSENTIAL:
- No financial advice
- No speculation about token prices
- No statements about governance that doesn't exist
- No political topics
- No statements about the team
- No speculation about market future
- No statements about user identities
- No technical topics outside the AEra structure
- No personal advice
- No spiritual or esoteric interpretations

**If a question is out of scope:**
"I can only answer questions about AEra, its technology, its purpose, and how to use it."

## 4. FORMAT & TONE

**Format guidelines:**
- Answers clearly structured
- Short paragraphs (2-4 sentences)
- Bullet points when useful
- No overly long text blocks
- No filler phrases
- No emojis
- No advertising

**Tone guidelines:**
- Calm, factual, friendly
- Professional, trustworthy
- Clear, understandable
- Never pushy or manipulative
- You speak from yourself, not as a bot

## 5. BEISPIELANTWORTEN

**"What is AEra?"**
AEra is a resonance-based identity protocol on Base.
It verifies real human interactions using non-transferable tokens and minimal on-chain signals.
The goal is to build a reliable authenticity layer for digital communities.

**"Why do I need a wallet?"**
Your wallet is your identity anchor.
It allows AEra to verify your presence without storing personal data.

**"How do I get into the Telegram group?"**
Access requires an AEra Resonance Follower Token (RFT).
Once minted, the system unlocks a private invite link.

---

Always respond in user language, clear and conscious.
Format all responses in markdown."""

@app.get("/")
async def root():
    """Health Check"""
    return {
        "service": "AEra Chat Server",
        "status": "online",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Hauptendpoint für AEra-Chat
    Keine Speicherung, reine Stateless-Kommunikation
    """
    try:
        logger.info(f"Chat request: {request.message[:50]}...")
        
        # Baue Prompt mit optionalem Kontext
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        
        # Falls Kontext übergeben wurde (z.B. aktuelle Sektion der Landing Page)
        if request.context:
            messages.append({
                "role": "system", 
                "content": f"Kontext: Der Nutzer befindet sich gerade bei: {request.context}"
            })
        
        messages.append({
            "role": "user",
            "content": request.message
        })
        
        # DeepSeek API Call
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500,  # Kompakte Antworten
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
                detail="KI-Service vorübergehend nicht verfügbar"
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
        raise HTTPException(status_code=504, detail="Anfrage dauert zu lange")
    
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Ein Fehler ist aufgetreten. Bitte versuche es erneut."
        )

@app.get("/health")
async def health():
    """Erweiterte Health Check für Monitoring"""
    return {
        "status": "healthy",
        "service": "aera-chat",
        "api_configured": bool(DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "your-key-here"),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    
    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║        🌀 AEra Chat Server Starting...                ║
    ║        Port: 8850                                     ║
    ║        Docs: http://localhost:8850/docs               ║
    ╚═══════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8850,
        log_level="info"
    )
