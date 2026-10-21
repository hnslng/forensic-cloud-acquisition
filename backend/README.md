# Backend

FastAPI mit persönlicher Anmeldung, austauschbarer Identity-Provider-Schnittstelle,
persistenten Sitzungen, CSRF/Origin-Prüfung, Benutzer- und Fallverwaltung.
Fallrechte werden unabhängig von eingegebenen Bearbeiterkürzeln geprüft.
`main.py` enthält die API, `identity.py` die lokale Authentifizierung,
`db.py` Verbindungen/Audit, `manage.py` den einmaligen Offline-Admin-Bootstrap.

Direkte Anforderungen stehen in `requirements*.txt`, aufgelöste Versionen in
`requirements*.lock`. API-Container läuft ohne Root und mit schreibgeschütztem
Root-Dateisystem. Der Cloud-Katalog speichert Anbieter und freie Bezeichnungen
fallbezogen mit UUID, Versionsprüfung und Audit. Provider-Anmeldung und
Sicherungsfunktionen sind noch nicht implementiert. Die Chromium-Abhängigkeiten
werden ausschließlich im separaten Testziel installiert.
