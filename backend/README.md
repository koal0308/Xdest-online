# DevPlatform - Developer Collaboration Platform

Eine moderne Plattform für Entwickler zum Erstellen von Profilen, Projekten und zum Teilen von Updates.

## Features

- 🔐 OAuth Login (GitHub + Google)
- 👤 Entwicklerprofile
- 📁 Projektseiten mit GitHub-Integration
- 📝 Projekt-Updates mit Bild/Video-Upload
- 💬 Kommentarsystem
- 🌙 Dark Mode UI

## Voraussetzungen

- Python 3.11+
- PostgreSQL
- GitHub OAuth App (optional, für GitHub Login)
- Google OAuth App (optional, für Google Login)

## Installation

### 1. PostgreSQL Setup

```bash
# PostgreSQL installieren (Ubuntu/Debian)
sudo apt install postgresql postgresql-contrib

# Datenbank erstellen
sudo -u postgres psql
CREATE DATABASE devplatform;
CREATE USER devuser WITH PASSWORD 'devpassword';
GRANT ALL PRIVILEGES ON DATABASE devplatform TO devuser;
\q
```

### 2. Projekt Setup

```bash
cd backend

# Virtual Environment erstellen
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# Environment konfigurieren
cp .env.example .env
# .env Datei bearbeiten mit deinen Credentials
```

### 3. OAuth Apps erstellen (Optional)

**GitHub OAuth:**
1. Gehe zu https://github.com/settings/developers
2. "New OAuth App" klicken
3. Homepage URL: `http://localhost:8000`
4. Callback URL: `http://localhost:8000/auth/github/callback`
5. Client ID und Secret in `.env` eintragen

**Google OAuth:**
1. Gehe zu https://console.cloud.google.com/
2. Neues Projekt erstellen → APIs & Services → Credentials
3. OAuth 2.0 Client ID erstellen (Web Application)
4. Authorized redirect URI: `http://localhost:8000/auth/google/callback`
5. Client ID und Secret in `.env` eintragen

### 4. Server starten

```bash
cd backend
source venv/bin/activate

# Mit uvicorn starten
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Oder direkt mit Python
python main.py
```

Die App läuft dann auf: **http://localhost:8000**

## Projektstruktur

```
backend/
├── app/
│   ├── models/          # SQLAlchemy Models
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── post.py
│   │   └── comment.py
│   ├── routers/         # FastAPI Routes
│   │   ├── auth.py      # OAuth Login
│   │   ├── pages.py     # HTML Pages
│   │   └── api.py       # API Endpoints
│   ├── templates/       # Jinja2 Templates
│   │   ├── base.html
│   │   ├── landing.html
│   │   ├── dashboard.html
│   │   └── ...
│   ├── static/          # Static Files
│   ├── config.py        # Settings
│   ├── database.py      # DB Connection
│   ├── auth.py          # OAuth Config
│   └── dependencies.py  # Helper Functions
├── uploads/             # User Uploads
├── main.py              # App Entry Point
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpunkte

| Methode | Route | Beschreibung |
|---------|-------|--------------|
| GET | `/` | Landing Page |
| GET | `/dashboard` | User Dashboard |
| GET | `/user/{username}` | Public Profile |
| GET | `/project/{id}` | Project Page |
| GET | `/create-project` | Create Project Form |
| GET | `/edit-profile` | Edit Profile Form |
| GET | `/explore` | Browse Projects |
| GET | `/auth/github` | GitHub OAuth |
| GET | `/auth/google` | Google OAuth |
| GET | `/auth/logout` | Logout |
| POST | `/api/project/create` | Create Project |
| POST | `/api/project/{id}/post` | Create Post |
| POST | `/api/post/{id}/comment` | Create Comment |
| POST | `/api/profile/update` | Update Profile |
| POST | `/api/project/{id}/delete` | Delete Project |

## Lokales Testing ohne OAuth

Falls du OAuth nicht konfigurieren möchtest, kannst du einen Test-User direkt in der Datenbank erstellen:

```sql
INSERT INTO users (username, email, avatar, provider, provider_id, created_at)
VALUES ('testuser', 'test@example.com', NULL, 'local', '12345', NOW());
```

Dann in der Session den User setzen (für Entwicklung).

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy
- **Database:** PostgreSQL
- **Auth:** Authlib (OAuth2)
- **Templates:** Jinja2
- **CSS:** TailwindCSS (CDN)
- **Server:** Uvicorn

## Lizenz

MIT
