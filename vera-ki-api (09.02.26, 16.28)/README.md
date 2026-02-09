# 🌀 AEra Chat Server

Spezialisierter KI-Assistent für die AEraLogIn Landing Page.

## 📦 Schnellstart

```bash
# 1. Start-Script ausführen
./start.sh

# 2. Testen
curl http://localhost:8850/health
```

## 📁 Dateien

- **server.py** - FastAPI Backend (Port 8850)
- **chat_popup.html** - Frontend Widget für Landing Page
- **requirements.txt** - Python Dependencies
- **.env.example** - Konfiguration Template
- **start.sh** - Automatischer Server-Start
- **DEPLOYMENT_GUIDE.md** - Ausführliche Anleitung

## 🚀 Deployment

Siehe **DEPLOYMENT_GUIDE.md** für detaillierte Anweisungen zu:
- Server-Setup
- Systemd Service
- Nginx Reverse Proxy
- Frontend-Integration
- Troubleshooting

## ✨ Features

- ✅ Stateless (keine Datenspeicherung)
- ✅ CORS-kompatibel
- ✅ Resonanz-bewusster Tonfall
- ✅ DeepSeek AI Integration
- ✅ Production-ready
- ✅ Responsive Popup-Design

## 🔧 Konfiguration

### Backend (.env)
```env
DEEPSEEK_API_KEY=dein-key-hier
HOST=0.0.0.0
PORT=8850
```

### Frontend (chat_popup.html)
```javascript
const CONFIG = {
    API_URL: 'http://your-server:8850/api/chat',
    ENABLE_CONTEXT: true
};
```

## 📡 API Endpoints

### POST /api/chat
```json
// Request
{
    "message": "Was ist AEraLogIn?",
    "context": "hero"  // optional
}

// Response
{
    "response": "AEraLogIn ist...",
    "timestamp": "2025-12-06T..."
}
```

### GET /health
```json
{
    "status": "healthy",
    "service": "aera-chat",
    "api_configured": true
}
```

## 🎨 Frontend Integration

Füge in deine Landing Page ein:

```html
<!-- Kopiere chat_popup.html Inhalt vor </body> -->
<script>
// Oder binde als externes Script ein
</script>
```

## 🌀 Philosophie

Der AEra Chat Assistent folgt der VERA-Philosophie:
- **Resonanz statt Reaktion** - Bewusster, ruhiger Tonfall
- **Freiheit vor Funktion** - Keine Datenspeicherung
- **Authentizität** - Ehrlich, nie werbend
- **Klarheit** - Verständliche Erklärungen

## 📊 System Requirements

- Python 3.8+
- 512 MB RAM
- 100 MB Disk Space

## 🔒 Sicherheit

- ✅ API-Key in .env (nicht in Git!)
- ✅ CORS Whitelisting
- ✅ Input Validation
- ⚠️ Rate Limiting empfohlen

## 📞 Support

Bei Fragen:
1. Siehe DEPLOYMENT_GUIDE.md
2. Prüfe Logs: `tail -f aera_chat.log`
3. Test Health: `curl localhost:8850/health`

---

**Entwickelt mit 🌀 Resonanz und Bewusstsein**

Teil des VERA Ökosystems
