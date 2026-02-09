# 🌀 AEra Chat Server - Deployment Guide

## 📦 Was ist in diesem Paket?

Dieser Ordner enthält alles, was du brauchst, um den AEra Chat Assistenten auf deinem Server zu deployen:

```
aera_chat_deployment/
├── server.py              # FastAPI Backend-Server
├── requirements.txt       # Python Dependencies
├── .env.example          # Environment-Variablen Template
├── chat_popup.html       # Frontend Widget (für Landing Page)
├── DEPLOYMENT_GUIDE.md   # Diese Anleitung
└── start.sh              # Start-Script (wird generiert)
```

## 🚀 Schnellstart (3 Schritte)

### 1. Dateien auf Server kopieren

```bash
# Auf deinem lokalen System
scp -r aera_chat_deployment/* user@server:/var/www/aera_chat/

# Oder per Git
cd /var/www/
git clone <dein-repo>
cd aera_chat_deployment
```

### 2. Server Setup

```bash
# SSH auf den Server
ssh user@server

# In Deployment-Verzeichnis wechseln
cd /var/www/aera_chat/

# Virtual Environment erstellen
python3 -m venv venv
source venv/bin/activate

# Dependencies installieren
pip install -r requirements.txt

# Environment-Datei erstellen
cp .env.example .env
# Optional: API-Key anpassen (ist bereits gesetzt)
nano .env
```

### 3. Server starten

```bash
# Direkt starten (für Test)
python3 server.py

# Oder als Background-Service
nohup python3 server.py > aera_chat.log 2>&1 &

# Prüfen ob läuft
curl http://localhost:8850/health
```

## 🔧 Production Deployment mit Systemd

Für dauerhaften Betrieb empfehle ich einen systemd Service:

### Service-Datei erstellen

```bash
sudo nano /etc/systemd/system/aera-chat.service
```

Inhalt:

```ini
[Unit]
Description=AEra Chat Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/aera_chat
Environment="PATH=/var/www/aera_chat/venv/bin"
ExecStart=/var/www/aera_chat/venv/bin/python3 /var/www/aera_chat/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Service aktivieren

```bash
# Service neu laden
sudo systemctl daemon-reload

# Service starten
sudo systemctl start aera-chat

# Service-Status prüfen
sudo systemctl status aera-chat

# Autostart aktivieren
sudo systemctl enable aera-chat

# Logs anzeigen
sudo journalctl -u aera-chat -f
```

## 🌐 Frontend Integration

### Option 1: Direktes Einbinden

Kopiere den Inhalt von `chat_popup.html` in deine Landing Page vor dem schließenden `</body>` Tag:

```html
<!-- Am Ende deiner landing.html, vor </body> -->
<script src="path/to/chat_popup.html"></script>
```

### Option 2: Als separates Script

Extrahiere nur das JavaScript und CSS:

```html
<!-- In deinem <head> -->
<link rel="stylesheet" href="/static/aera-chat.css">

<!-- Am Ende von <body> -->
<script src="/static/aera-chat.js"></script>
```

### API-URL konfigurieren

In der `chat_popup.html` oder deinem JS-File, ändere die API-URL:

```javascript
const CONFIG = {
    API_URL: 'https://your-domain.com:8850/api/chat',  // Production
    ENABLE_CONTEXT: true
};
```

## 🔒 Reverse Proxy mit Nginx (Empfohlen)

Statt Port 8850 direkt zu exponieren, nutze einen Reverse Proxy:

```nginx
# /etc/nginx/sites-available/aeralogin.com

server {
    listen 443 ssl;
    server_name aeralogin.com;

    # SSL Config...

    # AEra Chat Endpoint
    location /api/aera-chat {
        proxy_pass http://localhost:8850/api/chat;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        
        # CORS Headers
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "POST, OPTIONS";
        add_header Access-Control-Allow-Headers "Content-Type";
    }

    # Deine anderen Locations...
}
```

Dann in der Frontend-Config:

```javascript
const CONFIG = {
    API_URL: 'https://aeralogin.com/api/aera-chat',
    ENABLE_CONTEXT: true
};
```

## 📊 Monitoring & Logs

### Logs überwachen

```bash
# Systemd Logs (wenn als Service)
sudo journalctl -u aera-chat -f

# Direkte Log-Datei
tail -f /var/www/aera_chat/aera_chat.log
```

### Health Check

```bash
# Lokal
curl http://localhost:8850/health

# Von außen (mit Nginx)
curl https://aeralogin.com/api/aera-chat/health
```

Erwartete Antwort:

```json
{
    "status": "healthy",
    "service": "aera-chat",
    "api_configured": true,
    "timestamp": "2025-12-06T..."
}
```

## 🐛 Troubleshooting

### Server startet nicht

```bash
# Prüfe Python-Version (min. 3.8)
python3 --version

# Prüfe ob Port 8850 frei ist
sudo ss -tulpn | grep 8850

# Prüfe Logs für Fehler
tail -50 aera_chat.log
```

### API-Calls schlagen fehl

```bash
# Teste API direkt
curl -X POST http://localhost:8850/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Was ist AEraLogIn?"}'

# Prüfe DeepSeek API-Key
cat .env | grep DEEPSEEK_API_KEY
```

### CORS-Fehler im Browser

- Prüfe ob deine Domain in der `allow_origins` Liste ist (server.py, Zeile 44)
- Bei Nginx: Prüfe CORS-Headers in der Nginx-Config

## 🔄 Updates

```bash
# Server stoppen
sudo systemctl stop aera-chat

# Code aktualisieren
cd /var/www/aera_chat
git pull  # oder neue Dateien kopieren

# Dependencies aktualisieren
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Server starten
sudo systemctl start aera-chat
```

## 📈 Performance-Tipps

1. **Caching:** DeepSeek-Antworten cachen (Redis)
2. **Rate Limiting:** Verhindere Abuse (10 req/min pro IP)
3. **Load Balancing:** Bei hoher Last mehrere Instanzen
4. **CDN:** Statische Assets (JS/CSS) über CDN

## 🔐 Sicherheit

- ✅ API-Key in `.env` (niemals in Git!)
- ✅ HTTPS für Production (Nginx SSL)
- ✅ CORS nur für deine Domains
- ⚠️ Rate Limiting implementieren (TODO)
- ⚠️ Input Validation erweitern (TODO)

## 📞 Support

Bei Fragen oder Problemen:
1. Prüfe erst die Logs
2. Teste die Health-Endpoint
3. Verifiziere API-Key und CORS-Settings

---

🌀 **AEra Chat ist bereit für Production!**

Entwickelt mit Resonanz und Bewusstsein.
