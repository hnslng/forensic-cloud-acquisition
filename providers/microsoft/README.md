# Microsoft – aktueller FCA-Stand

Implementiert ist ein lesender REST-Adapter für das Standard-OneDrive und Outlook-Kalenderexporte mit festgelegtem Zeitraum. Die Webanmeldung verwendet den vorhandenen FCA-OAuth-Ablauf mit PKCE und benötigt in dieser Implementierung eine eigene, einmalig administrierte App. Persönliche Konten und Geschäftsmandanten sind getrennt praktisch abzunehmen.

**Automatisiert getestet:** synthetische API-Antworten, Kalenderfenster, Seitenwechsel, Download-Weiterleitungen ohne Bearer-Weitergabe und Rechteprüfungen. **Echtkonto-Abnahme:** noch offen.

Rclone mit gemeinsamer Microsoft-Registrierung wurde in [Stufe A](../../docs/stufe-a-machbarkeit.md) bewertet; diese Variante ist **nicht in FCA integriert**. Schreibrechte aus den Rclone-Standardeinstellungen dürfen nicht ungeprüft übernommen werden. Der bisher fehlende OneDrive-Quellhashvergleich und die pauschale HTTP-403-Wiederholung sind bestätigte Befunde für Stufe B, noch keine behobenen Funktionen.

[Unterstützter Umfang und Grenzen](../../docs/cloud-acquisition.md) · [Technische Stufe-A-Befunde](../../docs/stufe-a-technik.md).
