# Xdest - Developer Collaboration Hub

Eine moderne Entwickler-Plattform für Zusammenarbeit, Projekte und Issue-Tracking.

## Features

- 🔐 **GitHub OAuth** - Login mit GitHub
- 📁 **Projekte** - Erstelle und verwalte Projekte mit GitHub-Repo-Integration
- 🐛 **Issues & Feedback** - Issue-System mit GitHub-Sync
- 👍 **Voting-System** - Helpful-Votes für Issues und Antworten
- 🏆 **Leaderboard** - Rangliste basierend auf Community-Beiträgen
- ⭐ **Star Ratings** - Bewerte Projekte und Nutzer
- 🎨 **Dark Mode** - Modernes dunkles Design

## Tech Stack

- **Backend:** FastAPI (Python)
- **Database:** SQLite
- **Auth:** GitHub OAuth (Authlib)
- **Frontend:** Jinja2 Templates + TailwindCSS
- **API:** GitHub API Integration

## Installation

1. Repository klonen:
```bash
git clone https://github.com/koal0308-2/Xdest.git
cd Xdest/backend
```

2. Virtual Environment erstellen:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows
```

3. Dependencies installieren:
```bash
pip install -r requirements.txt
```

4. Environment-Variablen setzen (`.env` erstellen):
```env
SECRET_KEY=your-secret-key
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
```

5. Server starten:
```bash
python main.py
```

Die App läuft dann auf `http://localhost:8080`

## Projektstruktur

```
backend/
├── app/
│   ├── models/       # SQLAlchemy Models
│   ├── routers/      # FastAPI Routes
│   └── templates/    # Jinja2 Templates
├── static/           # Static files (Logo, etc.)
├── uploads/          # User uploads
├── main.py           # App Entry Point
└── requirements.txt  # Dependencies
```

## Leaderboard Scoring

Every action = +1 or -1 (simple & fair):

- ✅ Solution marked: +1
- 👍 Helpful vote: +1
- 🐙 GitHub 👍 reaction: +1
- 👎 GitHub 👎 reaction: -1
- ⭐ 5-star user rating: +1
- 🧪 Test Karma — Issue given: +1
- 📥 Test Karma — Issue received: +1
- ⚠️ Offer penalty (overdue obligation): -1

## Copyright © 2026 Xdest
Developed by Karlheinz Beismann
Licensed under the Apache License, Version 2.0.
You may not use this project except in compliance with the License.
