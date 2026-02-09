# 🌀 AEra Chat - Quick Reference

## 🚀 Schnellbefehle

### Lokal testen
```bash
./start.sh              # Server starten
./test.sh               # Alle Tests durchführen
curl localhost:8850/health  # Health Check
```

### Auf Server deployen
```bash
# 1. Dateien kopieren
scp -r aera_chat_deployment/* user@server:/var/www/aera_chat/

# 2. Auf Server
ssh user@server
cd /var/www/aera_chat
./start.sh
```

### Systemd Service
```bash
# Erstellen
sudo nano /etc/systemd/system/aera-chat.service
# (Inhalt siehe DEPLOYMENT_GUIDE.md)

# Starten
sudo systemctl start aera-chat
sudo systemctl status aera-chat
sudo systemctl enable aera-chat

# Logs
sudo journalctl -u aera-chat -f
```

## 📡 API Endpunkte

### Chat
```bash
curl -X POST http://localhost:8850/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Was ist AEraLogIn?"}'
```

### Health
```bash
curl http://localhost:8850/health
```

## 🎨 Frontend Integration

### Landing Page HTML
```html
<!-- Am Ende vor </body> -->
<button class="aera-chat-button" id="aeraChatButton">🌀</button>
<div class="aera-chat-popup" id="aeraChatPopup">...</div>
<script src="aera-chat.js"></script>
```

### JavaScript Config
```javascript
const CONFIG = {
    API_URL: 'https://aeralogin.com:8850/api/chat',
    ENABLE_CONTEXT: true
};
```

## 🔧 Nginx Reverse Proxy

```nginx
location /api/aera-chat {
    proxy_pass http://localhost:8850/api/chat;
    proxy_set_header Host $host;
    add_header Access-Control-Allow-Origin *;
}
```

Dann Frontend-URL ändern:
```javascript
API_URL: 'https://aeralogin.com/api/aera-chat'
```

## 🐛 Troubleshooting

| Problem | Lösung |
|---------|--------|
| Server startet nicht | `python3 --version` (min 3.8), Port 8850 frei? |
| API-Key Fehler | `.env` Datei prüfen |
| CORS Fehler | `allow_origins` in server.py anpassen |
| Timeout | DeepSeek API erreichbar? |

## 📊 Wichtige Dateien

| Datei | Beschreibung |
|-------|--------------|
| `server.py` | Haupt-Backend-Server |
| `chat_popup.html` | Komplettes Frontend Widget |
| `.env` | Konfiguration (API-Key) |
| `requirements.txt` | Python Dependencies |
| `start.sh` | Auto-Start-Script |
| `test.sh` | Test-Suite |

## 🔒 Sicherheit Checklist

- [ ] `.env` nicht in Git commiten
- [ ] CORS nur für eigene Domains
- [ ] HTTPS in Production
- [ ] Rate Limiting implementieren
- [ ] Regelmäßige Updates

## 📈 Performance

| Metrik | Wert |
|--------|------|
| Startup Zeit | ~2s |
| Response Zeit | ~1-3s (DeepSeek) |
| RAM Usage | ~150 MB |
| Concurrent Req | ~10 (Single-Instance) |

## 🌐 URLs

- **Lokal:** http://localhost:8850
- **Health:** http://localhost:8850/health
- **Docs:** http://localhost:8850/docs
- **Chat API:** http://localhost:8850/api/chat

## 📞 Support

1. **Logs prüfen:** `tail -f aera_chat.log`
2. **Health testen:** `curl localhost:8850/health`
3. **Manual test:** `./test.sh`

---

🌀 **Ready to deploy!**
