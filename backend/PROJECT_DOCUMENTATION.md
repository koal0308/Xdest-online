# Xdest - Developer Collaboration Platform

**Vollständige Projektdokumentation**

---

## 📋 Inhaltsverzeichnis

1. [Überblick](#überblick)
2. [Technologie-Stack](#technologie-stack)
3. [Architektur](#architektur)
4. [Benutzerrollen & Authentifizierung](#benutzerrollen--authentifizierung)
5. [Kernfunktionen](#kernfunktionen)
6. [Datenmodelle](#datenmodelle)
7. [API-Endpunkte](#api-endpunkte)
8. [Seitenstruktur](#seitenstruktur)
9. [AI-Assistent](#ai-assistent)
10. [Sicherheit & Datenschutz](#sicherheit--datenschutz)
11. [Deployment](#deployment)
12. [Lizenz](#lizenz)

---

## 🎯 Überblick

**Xdest** ist eine moderne Developer-Collaboration-Plattform, die Softwareentwickler mit Testern verbindet. Die Plattform ermöglicht es Entwicklern, ihre Projekte zu präsentieren, Feedback zu sammeln und mit der Community zu interagieren.

### Vision
Eine zentrale Anlaufstelle für Entwickler, um:
- Projekte zu präsentieren und Sichtbarkeit zu erhöhen
- Qualitatives Feedback von Testern zu erhalten
- Mit anderen Entwicklern zu kollaborieren
- Angebote und Deals für ihre Produkte zu erstellen

### Zielgruppe
- **Entwickler**: Indie-Entwickler, Startups, Open-Source-Maintainer
- **Tester**: QA-Enthusiasten, Beta-Tester, Community-Mitglieder

---

## 🛠 Technologie-Stack

### Backend
| Technologie | Version | Verwendung |
|-------------|---------|------------|
| **Python** | 3.11+ | Programmiersprache |
| **FastAPI** | 0.109.0 | Web-Framework |
| **SQLAlchemy** | 2.0.25 | ORM / Datenbankabstraktion |
| **SQLite** | - | Datenbank (devplatform.db) |
| **Uvicorn** | 0.27.0 | ASGI-Server |
| **Authlib** | 1.3.0 | OAuth-Authentifizierung |
| **HTTPX** | 0.26.0 | Async HTTP-Client |
| **Cryptography** | - | Token-Verschlüsselung (Fernet/AES) |

### Frontend
| Technologie | Verwendung |
|-------------|------------|
| **Jinja2** | Template-Engine |
| **TailwindCSS** | CSS-Framework (via CDN) |
| **Vanilla JavaScript** | Interaktivität |

### AI-Service
| Technologie | Verwendung |
|-------------|------------|
| **DeepSeek API** | LLM für AI-Assistent |
| **FastAPI** | Separater Server (Port 8079) |

### Externe Dienste
| Dienst | Verwendung |
|--------|------------|
| **GitHub OAuth** | Entwickler-Authentifizierung |
| **Google OAuth** | Tester-Authentifizierung |
| **GitHub API** | Repository-Daten, Issue-Sync |
| **Plausible Analytics** | Datenschutzfreundliche Analytics (optional) |

---

## 🏗 Architektur

### Verzeichnisstruktur

```
dest/
├── backend/
│   ├── main.py                    # FastAPI App-Einstiegspunkt
│   ├── requirements.txt           # Python-Abhängigkeiten
│   ├── devplatform.db             # SQLite-Datenbank
│   ├── .env                       # Umgebungsvariablen (geheim)
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py              # Konfiguration & Settings
│   │   ├── database.py            # DB-Verbindung & Session
│   │   ├── auth.py                # OAuth-Konfiguration
│   │   ├── dependencies.py        # FastAPI Dependencies
│   │   ├── encryption.py          # Token-Verschlüsselung (Fernet)
│   │   │
│   │   ├── models/                # SQLAlchemy-Modelle
│   │   │   ├── user.py            # User-Modell
│   │   │   ├── project.py         # Project-Modell
│   │   │   ├── issue.py           # Issue & Response-Modelle
│   │   │   ├── post.py            # Post-Modell
│   │   │   ├── comment.py         # Comment-Modell
│   │   │   ├── offer.py           # Offer-Modell
│   │   │   ├── rating.py          # Rating-Modelle
│   │   │   └── message.py         # Community-Message-Modell
│   │   │
│   │   ├── routers/               # API-Router
│   │   │   ├── auth.py            # OAuth-Routen
│   │   │   ├── pages.py           # HTML-Seiten
│   │   │   └── api.py             # REST-API-Endpunkte
│   │   │
│   │   ├── templates/             # Jinja2-Templates
│   │   │   ├── base.html          # Basis-Template
│   │   │   ├── landing.html       # Startseite
│   │   │   ├── dashboard.html     # Dashboard
│   │   │   ├── explore.html       # Projekt-Explorer
│   │   │   ├── project.html       # Projektseite
│   │   │   ├── profile.html       # Benutzerprofil
│   │   │   ├── community.html     # Collective (Chat)
│   │   │   ├── leaderboard.html   # Rangliste
│   │   │   ├── offers.html        # Angebote
│   │   │   ├── issues.html        # Issue-Liste
│   │   │   ├── issue_detail.html  # Issue-Details
│   │   │   ├── privacy.html       # Datenschutz
│   │   │   ├── terms.html         # Nutzungsbedingungen
│   │   │   └── ...
│   │   │
│   │   └── static/                # App-spezifische Assets
│   │
│   ├── static/                    # Globale statische Dateien
│   │   ├── logo.png               # X-Logo
│   │   ├── favicon.ico
│   │   └── ...
│   │
│   ├── uploads/                   # Benutzer-Uploads
│   │   ├── avatars/
│   │   ├── projects/
│   │   ├── posts/
│   │   └── issues/
│   │
│   ├── xdest_ai/                  # AI-Assistent-Service
│   │   ├── server.py              # AI-Server (Port 8079)
│   │   └── .env                   # DeepSeek API Key
│   │
│   └── scripts/
│       └── migrate_encrypt_tokens.py  # Token-Migration
│
├── LICENSE                        # Apache 2.0
└── README.md                      # Projekt-README
```

### Server-Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                        Nginx (Reverse Proxy)                 │
│                         https://xdest.dev                    │
└──────────────────┬────────────────────────┬─────────────────┘
                   │                        │
                   ▼                        ▼
    ┌──────────────────────┐    ┌──────────────────────┐
    │   Xdest Backend      │    │   Xdest AI Assistant │
    │   FastAPI            │    │   FastAPI            │
    │   Port: 8080         │    │   Port: 8079         │
    └──────────┬───────────┘    └──────────┬───────────┘
               │                           │
               ▼                           ▼
    ┌──────────────────────┐    ┌──────────────────────┐
    │   SQLite Database    │    │   DeepSeek API       │
    │   devplatform.db     │    │   (External)         │
    └──────────────────────┘    └──────────────────────┘
```

---

## 👥 Benutzerrollen & Authentifizierung

### Zwei-Rollen-System

| Rolle | Login-Methode | Rechte |
|-------|---------------|--------|
| **Developer** | GitHub OAuth | Vollzugriff: Projekte erstellen, Issues verwalten, Angebote erstellen |
| **Tester** | Google OAuth | Eingeschränkt: Projekte erkunden, Issues melden, abstimmen, Punkte sammeln |

### OAuth-Flow

```
┌─────────┐     ┌─────────┐     ┌─────────────┐
│  User   │────▶│  Xdest  │────▶│ GitHub/     │
│         │     │         │     │ Google      │
└─────────┘     └─────────┘     └──────┬──────┘
                                       │
                     ┌─────────────────┘
                     ▼
              ┌─────────────┐
              │  Callback   │
              │  /auth/...  │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │ User wird   │
              │ erstellt/   │
              │ eingeloggt  │
              └─────────────┘
```

### Upgrade-Pfad
- Tester kann zum Developer werden durch GitHub-Login
- Bei gleicher E-Mail: Account wird geupgraded
- Bei unterschiedlicher E-Mail: Neuer Account wird erstellt

### Session-Management
- Session Middleware mit SECRET_KEY
- Session-Cookie für Login-Status
- OAuth-State-Cookie für CSRF-Schutz (10 Min.)

---

## ⚡ Kernfunktionen

### 1. Projekte

**Funktionen:**
- Projekt erstellen (Name, Beschreibung, URL, Tags)
- GitHub-Repository verknüpfen (automatische Stats)
- Projektbild hochladen
- Google Analytics / Plausible Integration
- Social-Media-Sharing (X, LinkedIn, Reddit, Facebook, Farcaster)
- OG Meta-Tags für Link-Previews

**Kategorien:**
Frontend, Backend, Mobile, DevOps, AI/ML, Database, Security, Game Dev, Tools, Open Source

### 2. Issue-System

**Issue-Typen:**
| Typ | Label | Farbe |
|-----|-------|-------|
| Bug | 🐛 bug | Rot |
| Feature | ✨ enhancement | Cyan |
| Question | ❓ question | Lila |
| Security | 🔒 security | Orange |
| Docs | 📚 documentation | Blau |

**Status-Workflow:**
```
Open → In Progress → Resolved → Closed
                  ↘ Won't Fix
```

**Features:**
- Screenshot-Upload
- GitHub-Sync (Issues werden automatisch auf GitHub erstellt)
- Voting-System (Helpful-Votes)
- Antworten mit Lösungsmarkierung
- Benachrichtigungen für Projekt-Owner

### 3. Bewertungssystem

**Projekt-Bewertungen:**
- 1-5 Sterne
- Durchschnittsbewertung wird angezeigt
- Nur eingeloggte Benutzer können bewerten
- Eigene Projekte können nicht bewertet werden

**Benutzer-Bewertungen:**
- 1-5 Sterne für Benutzerprofile
- Zeigt Durchschnitt auf Profilseite

### 4. Punkte & Leaderboard

**Punktevergabe:**
| Aktion | Punkte |
|--------|--------|
| Issue melden | +X |
| Antwort erhalten | +X |
| Helpful-Vote bekommen | +X |
| Lösung markiert | +X |

**Leaderboard:**
- Rangliste aller Benutzer nach Punkten
- Zeigt Top-Contributor

### 5. Angebote (Offers)

**Angebotstypen:**
| Typ | Beschreibung |
|-----|--------------|
| Free Trial | Kostenlose Testphase |
| Discount | Prozent-Rabatt |
| Early Bird | Frühbucher-Preis |
| Lifetime | Einmalzahlung |
| Beta Access | Kostenloser Beta-Zugang |
| Other | Sonstige |

**Features:**
- Coupon-Codes
- Einlösungs-URL
- Begrenzte Verfügbarkeit
- Ablaufdatum
- Anzeige auf Landing Page

### 6. Collective (Community)

**Features:**
- Öffentlicher Chat
- Nachrichten posten
- Auf Nachrichten antworten
- Alle Benutzer können teilnehmen

### 7. Posts & Kommentare

**Features:**
- Entwickler können Updates zu Projekten posten
- Medien-Upload (Bilder, Videos)
- Kommentare unter Posts

---

## 📊 Datenmodelle

### User
```python
User:
  - id: Integer (PK)
  - username: String (unique)
  - email: String (unique)
  - avatar: String (URL)
  - bio: Text
  - github: String (GitHub URL)
  - github_token: String (encrypted)
  - provider: String (github/google)
  - provider_id: String
  - role: String (developer/tester)
  - created_at: DateTime
```

### Project
```python
Project:
  - id: Integer (PK)
  - user_id: Integer (FK → User)
  - name: String
  - description: Text
  - project_url: String
  - github_url: String
  - image: String (URL)
  - tags: String (comma-separated)
  - google_analytics_id: String
  - plausible_domain: String
  - plausible_api_key: String (encrypted)
  - created_at: DateTime
```

### Issue
```python
Issue:
  - id: Integer (PK)
  - project_id: Integer (FK → Project)
  - user_id: Integer (FK → User)
  - title: String
  - description: Text
  - screenshot: String (URL)
  - issue_type: Enum (bug/feature/question/security/docs)
  - status: Enum (open/in_progress/resolved/closed/wont_fix)
  - helpful_count: Integer
  - github_issue_number: Integer
  - github_issue_url: String
  - is_read_by_owner: Boolean
  - created_at: DateTime
  - updated_at: DateTime
```

### Offer
```python
Offer:
  - id: Integer (PK)
  - project_id: Integer (FK → Project)
  - title: String
  - description: Text
  - offer_type: Enum
  - original_price: String
  - offer_price: String
  - discount_percent: Integer
  - duration: String
  - coupon_code: String
  - redemption_url: String
  - max_redemptions: Integer
  - current_redemptions: Integer
  - valid_from: DateTime
  - valid_until: DateTime
  - is_active: Boolean
```

### Message (Collective)
```python
Message:
  - id: Integer (PK)
  - user_id: Integer (FK → User)
  - content: Text
  - created_at: DateTime

MessageReply:
  - id: Integer (PK)
  - message_id: Integer (FK → Message)
  - user_id: Integer (FK → User)
  - content: Text
  - created_at: DateTime
```

### Ratings
```python
ProjectRating:
  - id: Integer (PK)
  - project_id: Integer (FK → Project)
  - user_id: Integer (FK → User)
  - stars: Integer (1-5)
  - created_at: DateTime

UserRating:
  - id: Integer (PK)
  - rated_user_id: Integer (FK → User)
  - rater_user_id: Integer (FK → User)
  - stars: Integer (1-5)
  - created_at: DateTime
```

---

## 🌐 API-Endpunkte

### Authentifizierung (`/auth`)
| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| GET | `/auth/github` | GitHub OAuth starten |
| GET | `/auth/github/callback` | GitHub OAuth Callback |
| GET | `/auth/google` | Google OAuth starten |
| GET | `/auth/google/callback` | Google OAuth Callback |
| GET | `/auth/logout` | Ausloggen |

### API (`/api`)
| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| POST | `/api/project/create` | Neues Projekt erstellen |
| POST | `/api/project/{id}/edit` | Projekt bearbeiten |
| POST | `/api/project/{id}/delete` | Projekt löschen |
| POST | `/api/project/{id}/post` | Post erstellen |
| POST | `/api/project/{id}/issue` | Issue melden |
| POST | `/api/issue/{id}/response` | Antwort hinzufügen |
| POST | `/api/issue/{id}/vote` | Issue als hilfreich markieren |
| POST | `/api/response/{id}/vote` | Antwort bewerten |
| POST | `/api/project/{id}/rate` | Projekt bewerten |
| GET | `/api/project/{id}/rating` | Projekt-Bewertung abrufen |
| POST | `/api/profile/update` | Profil aktualisieren |
| POST | `/api/offer/create` | Angebot erstellen |
| POST | `/api/message` | Collective-Nachricht senden |
| POST | `/api/message/{id}/reply` | Auf Nachricht antworten |
| GET | `/api/user/data` | Eigene Daten exportieren |
| POST | `/api/user/delete` | Account löschen |

### Seiten (`/`)
| Endpunkt | Beschreibung |
|----------|--------------|
| `/` | Landing Page |
| `/explore` | Projekte & User erkunden |
| `/community` | Collective (Chat) |
| `/leaderboard` | Rangliste |
| `/dashboard` | Benutzer-Dashboard |
| `/project/{id}` | Projektseite |
| `/project/{id}/issues` | Issue-Liste |
| `/project/{id}/issues/new` | Neues Issue |
| `/project/{id}/issues/{issue_id}` | Issue-Details |
| `/user/{username}` | Benutzerprofil |
| `/offers` | Alle Angebote |
| `/privacy` | Datenschutz & Account-Management |
| `/terms` | Nutzungsbedingungen |

---

## 📄 Seitenstruktur

### Öffentliche Seiten
- **Landing Page** (`/`): Hero, Angebote, neueste Projekte
- **Explore** (`/explore`): Projekte durchsuchen, Kategorie-Filter
- **Collective** (`/community`): Öffentlicher Chat
- **Leaderboard** (`/leaderboard`): Punkte-Rangliste
- **Offers** (`/offers`): Alle Angebote
- **Project** (`/project/{id}`): Projektdetails, Issues, Bewertungen
- **Profile** (`/user/{username}`): Benutzerprofil
- **Privacy** (`/privacy`): Datenschutz, GDPR-Rechte
- **Terms** (`/terms`): Nutzungsbedingungen

### Geschützte Seiten (Login erforderlich)
- **Dashboard** (`/dashboard`): Eigene Projekte, Benachrichtigungen
- **Create Project** (`/create-project`): Neues Projekt (nur Developer)
- **Edit Profile** (`/edit-profile`): Profil bearbeiten
- **Create Offer** (`/create-offer`): Neues Angebot (nur Developer)

---

## 🤖 AI-Assistent

### Übersicht
Separater FastAPI-Server auf Port 8079, der einen KI-gestützten Support-Chat bereitstellt.

### Technologie
- **LLM**: DeepSeek Chat API
- **Framework**: FastAPI
- **Integration**: Widget in `base.html` (alle Seiten)

### System-Prompt
Der AI-Assistent kennt:
- Alle Seiten und deren Funktionen
- Unterschiede zwischen Developer und Tester
- FAQ und häufige Probleme
- Datenschutzinformationen
- Kontaktinformationen

### Endpunkte
| Methode | Endpunkt | Beschreibung |
|---------|----------|--------------|
| GET | `/` | Health Check |
| POST | `/api/chat` | Chat-Anfrage |
| GET | `/health` | Server-Status |

### Chat-Widget
- Schwebendes X-Logo unten rechts
- Öffnet Chat-Modal
- Kontextsensitiv (kennt aktuelle Seite)
- Mehrsprachig (passt sich Benutzersprache an)

---

## 🔒 Sicherheit & Datenschutz

### Authentifizierung
- OAuth 2.0 mit GitHub und Google
- Session-basierte Authentifizierung
- CSRF-Schutz über State-Parameter

### Verschlüsselung
```python
# Token-Verschlüsselung mit Fernet (AES-128-CBC + HMAC)
- GitHub Access Tokens: verschlüsselt gespeichert
- Plausible API Keys: verschlüsselt gespeichert
- PBKDF2 Key Derivation (100.000 Iterationen)
```

### Datenschutz (DSGVO-konform)
- **Datenminimierung**: Nur notwendige Daten werden gesammelt
- **Keine Tracking-Cookies**: Nur Session-Cookies
- **Keine Werbung**: Keine Daten an Dritte
- **GDPR-Rechte**: 
  - Auskunft (Daten einsehen)
  - Portabilität (Daten exportieren)
  - Löschung (Account löschen)
  - Berichtigung (Profil bearbeiten)

### Account-Löschung
1. `/privacy` → "Manage Your Data"
2. "Delete Account" klicken
3. Username zur Bestätigung eingeben
4. Alle Daten werden permanent gelöscht
5. Issues werden anonymisiert ("Deleted User")

### Rechtliche Dokumente
- **Nutzungsbedingungen**: `/terms`
- **Datenschutzerklärung**: `/privacy`
- **Rechtsordnung**: Österreich (EU)
- **Kontakt**: aiandfriends@gmail.com

---

## 🚀 Deployment

### Umgebungsvariablen (.env)
```env
# Core
SECRET_KEY=your-secure-secret-key
DATABASE_URL=sqlite:///./devplatform.db
APP_URL=https://xdest.dev

# OAuth
GITHUB_CLIENT_ID=xxx
GITHUB_CLIENT_SECRET=xxx
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=xxx

# Encryption
ENCRYPTION_KEY=your-encryption-key

# AI Service
DEEPSEEK_API_KEY=xxx
```

### Server starten
```bash
# Backend (Port 8080)
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8080

# AI Service (Port 8079)
cd xdest_ai
python server.py
```

### Systemd Services (Produktion)
```ini
# /etc/systemd/system/xdest.service
[Unit]
Description=Xdest Backend
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/backend
ExecStart=/path/to/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx-Konfiguration
```nginx
server {
    listen 443 ssl http2;
    server_name xdest.dev;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /ai/ {
        proxy_pass http://127.0.0.1:8079/;
    }
}
```

---

## 📜 Lizenz

**Apache License 2.0**

```
Copyright 2026 Xdest

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

## 📞 Kontakt

- **Website**: https://xdest.dev
- **E-Mail**: aiandfriends@gmail.com
- **X (Twitter)**: [@XdestHQ](https://x.com/XdestHQ)
- **GitHub**: [koal0308/Xdest-online](https://github.com/koal0308/Xdest-online)
- **Entwickler**: [@karlbeis](https://x.com/karlbeis)

---

*Letzte Aktualisierung: 11. Februar 2026*
