# Google – aktueller FCA-Stand

Der Stufe-B-Entwicklungszweig verwendet das offizielle REST-Inventar für „Meine Ablage“ und Rclone 1.75.2 für Dateidownloads anhand der Original-ID. Das verhindert die Verwechslung gleichnamiger Dateien. Docs/Sheets/Slides/Drawings werden als abgeleitete Exporte gekennzeichnet. Google-Kalender bleiben beim vorhandenen REST-Adapter.

Die bestehende Webanmeldung behält PKCE und einmaligen State; zusätzlich sind konkrete FCA-Sitzung, Anbieter, Client und Rückkehradresse gebunden. Anbieterregistrierung und HTTPS-Origin werden einmalig administriert. Rclone-Konfigurationen bleiben pro Konto verschlüsselt; Rclone ist während seiner Dateisitzung alleiniger Token-Refresh-Eigentümer. Keine manuelle Tokenübertragung und kein nativer Rclone-Browserflow.

**Getestet:** synthetische REST-Antworten, echte lokale Rclone-Kopien mit simulierten Anbieter-Metadaten, Hashfehler, Kontotrennung, Erhalt rotierter Tokens und Browser-Rücksprung über eine simulierte Anbieterseite. **Nicht getestet:** echte Google-Anmeldung, tatsächlicher Google-Download und Google-Refresh-Endpunkt. Noch keine Übernahme in laufende Laborcontainer.

Eigene Web-App und administrierter interner HTTPS-Name sind vorbereitet; Domain und Google-Freigabestatus noch offen. Domainlose Tunnelanmeldung bleibt eine Alternative ohne implementierten Client. Geteilte Wurzeln werden nicht eigenständig inventarisiert. Keine uneingeschränkte Verwendbarkeit einer unverifizierten App oder der auslaufenden gemeinsamen Rclone-Google-ID behaupten.

[Stufe-B-Status](../../docs/stufe-b-status.md) · [Privates HTTPS und erster Test](../../docs/private-https-oauth.md) · [Unterstützter Umfang](../../docs/cloud-acquisition.md).
