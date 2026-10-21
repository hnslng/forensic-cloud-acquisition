# iCloud-Adapter

**Aktueller Stand 0.5.0:** [Sicherungsfunktionen, Anleitung, Grenzen und ausstehende Echtkonto-Abnahme](../../docs/cloud-acquisition.md). Ältere Phasenangaben unten dokumentieren den vorherigen Entwicklungsstand.


`adapter.py`: festgeschriebenes rclone v1.75.2, reguläre Apple-Anmeldung und 2FA,
verschlüsselte Kontokonfiguration, geschützter Unix-Socket und ausschließlich
explizite Verzeichnisabfragen. Der Webzugang wird in `backend/cloud_auth.py`
mit persönlicher Sitzung, Fallrechten, Begrenzungen und Audit verbunden.

`cli.py` ist nur eine getrennte manuelle Entwickler-Testbank. Normale Bedienung
über „Authentifizieren“ innerhalb des Fallarbeitsbereichs.

Echte Apple-Abnahme erfordert die persönliche Anmeldung mit einem vorbereiteten
Konto. Downloads sind noch nicht implementiert. Offline-/synthetische Tests sind
kein Nachweis erfolgreicher realer Providerintegration.

Siehe `docs/phase-2-icloud.md` für Stand, Grenzen, Betrieb und offene Nachweise.
