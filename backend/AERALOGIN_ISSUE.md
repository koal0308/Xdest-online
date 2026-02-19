

Antwort:

Hallo @karlbeis,

Ich habe eure Integration getestet und kann bestätigen:

✅ Eure App ist korrekt registriert
✅ Die Client ID ist gültig
✅ Die Redirect URI ist korrekt hinterlegt
✅ Die Authorization URL ist korrekt formatiert
✅ Der AEraLogIn OAuth-Endpoint antwortet korrekt

Die URL https://aeralogin.com/oauth/authorize?client_id=aera_4042836bd8852b520f9f2b5448446627&redirect_uri=... 
funktioniert und zeigt die Wallet-Connect-Seite.

Mögliche Ursachen auf eurer Seite:

1. **JavaScript deaktiviert?** - Die Auth-Seite benötigt JS für MetaMask/WalletConnect

2. **Popup-Blocker** - Falls ihr ein Popup verwendet statt direktem Redirect

3. **Browser-Konsole prüfen** - Gibt es JS-Errors beim Laden?

4. **Direkt-Test** - Öffnet diese URL manuell im Browser:
   https://aeralogin.com/oauth/authorize?client_id=aera_4042836bd8852b520f9f2b5448446627&redirect_uri=https%3A%2F%2Fxdest.dev%2Fauth%2Faera%2Fcallback&response_type=code&state=test123

Wenn die Seite dort korrekt angezeigt wird, liegt das Problem bei der Redirect-Implementierung.

Keine zusätzlichen Parameter (scope etc.) sind erforderlich.

Bei Fragen gerne melden!