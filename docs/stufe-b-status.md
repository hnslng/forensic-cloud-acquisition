# Stufe B – Entwicklung und noch offene Echtkonto-Abnahme

Stand: 22.10.2026 (Europe/Vienna). Die technische Entwicklung ist freigegeben. Der Auftraggeber hat die Domainwahl ausdrücklich zurückgestellt und die weitere Arbeit an Stabilität, Fehlerbehandlung und Rclone mit synthetischen Tests beauftragt. DNS, Zertifikate, externe App-Registrierungen und echte Cloud-Anmeldungen bleiben gesondert freizugeben.

## Implementiert

- Vorhandene Browseranmeldung mit PKCE und einmaligem State zusätzlich an die konkrete FCA-Sitzung, den Anbieter, Client und die Rückkehradresse gebunden. Eine andere Sitzung desselben Benutzers kann die Anmeldung nicht übernehmen. Ermittler müssen weder Tokens noch Befehle übertragen.
- Google-/OneDrive-Dateitransport über die bereits gepinnte Rclone-Version 1.75.2. Die offizielle REST-Inventarisierung erhält Original-IDs, Metadaten und Exportkennzeichnung. Kalender verwenden weiterhin ihre bestehenden REST-Adapter.
- Getrennte verschlüsselte Rclone-Dateikonfigurationen je Fall/Konto, authentifizierte Unix-Sockets, keine öffentlichen Steuerports. FCA übernimmt die Browserautorisierung; der native Rclone-Anmeldeablauf ohne PKCE wird nicht eingesetzt. Rclone erneuert Tokens während seiner exklusiven Kontositzung; aktualisierte Tokens werden verschlüsselt erhalten und mit FCA synchronisiert. Beim Schließen wird keine neue Netzwerkanmeldung ausgelöst.
- Google-Dateien werden mit dem geprüften Rclone-Befehl `copyid` anhand ihrer ID zum ausschließlich lokalen temporären Ziel kopiert. Gleichnamige Dateien werden nicht verwechselt. Andere Backend-Befehle, Verschieben und Cloud-Ziele sind gesperrt. OneDrive prüft vor der Kopie die zum Pfad aufgelöste Datei-ID.
- HTTP 401/ungültige Anmeldung, dauerhafte 403/404-Zugriffsfehler, begründete Google-Rate-Limits, HTTP 429 und vorübergehende Serverfehler werden unterschieden. Ein ungültiger Token beendet den Lauf, statt das gesamte Inventar mit aussichtslosen Anfragen abzuarbeiten. Rohantworten erscheinen weder im Fallprotokoll noch in Fehlermeldungen.
- Verfügbare OneDrive-SHA1-, QuickXorHash- und CRC32-Werte werden verglichen. Graph bezeichnet `sha256Hash` ausdrücklich als nicht unterstützt; lokale SHA-256-Prüfung bleibt unabhängig davon erhalten. Fehlende unterstützte Quellhashes sind als fehlend dokumentiert. [Microsoft Hash-Felder](https://learn.microsoft.com/en-us/graph/api/resources/hashes?view=graph-rest-1.0).
- Berichte unterscheiden abgeschlossene, fehlgeschlagene, unzugängliche und wartende Dateien, unbekannte Größen, offene Inventare und nicht untersuchte/unterstützte Bereiche. Erfolgreich gesicherte Bytes werden ausschließlich aus abgeschlossenen Dateien summiert; Teilübertragungen stehen getrennt. Keine Behauptung einer vollständigen Gesamtkontosicherung.
- Migration 0009 erweitert ausschließlich die möglichen Parallelitätsgrenzen. Bestehende Werte bleiben 4 Dateien / 2 Konten. Ein Administrator kann bei einer späteren Installation ein größeres Ressourcenprofil freigeben: maximal 16 Dateien je Konto, 8 Konten und 32 Übertragungsplätze insgesamt. API und Worker begrenzen identisch; die Oberfläche zeigt die eingerichteten Grenzen. Keine Optimierung oder Erhöhung der Laborwerte.
- Rclone-Puffer und Statistikgruppen sind begrenzt. Eine durch Speicherschutz ausgelöste Pause speichert künftig die tatsächlichen Auslösewerte. Bewusst pausierte Aufträge werden nicht automatisch fortgesetzt.
- Konfigurierbarer lokaler HTTPS-Prüfplan über `scripts/prepare_private_https.py`. Er erzeugt ausschließlich Dateien zur Prüfung; er führt weder DNS-/ACME-Anfragen noch Serveränderungen aus. Kein Domainname ist in der Anwendung festgeschrieben.

## Anbieter und Umfang

| Bereich | Implementierter Entwicklungsstand | Praktische Anbieterabnahme |
|---|---|---|
| iCloud Drive/Fotos | Bestehender Adapter, kombinierte Auswahl, Queue und Integritätsprüfung erhalten | Anmeldung/2FA und Teilübertragungen früher erfolgt; vollständige Abnahme weiterhin offen. Bestehender Lauf bleibt auf Wunsch pausiert. |
| Google „Meine Ablage“ | REST-Inventar, Rclone-ID-Download, Binärdateien, Docs→DOCX, Sheets→XLSX, Slides→PPTX, Drawings→PDF | Nur synthetische Tests; Domain/App und persönliche Anmeldung stehen aus. |
| Google „Mit mir geteilt“ / Shared Drives | Nicht eigenständig inventarisiert; getrennt als nicht untersucht bilanziert | Offen. Zusätzliche Wurzelauswahl, Berechtigungen, ID-/Pfadabbildung und Bereichstests erforderlich. |
| OneDrive Personal / Business | Ermittlung des Standardlaufwerks, Rclone-Kopie, ID-/Versions-/Hashvergleich | Nur synthetische Personal-/Business-Konfigurationen; tatsächliche Microsoft-Konten und Mandantenrichtlinien ungeprüft. |
| Weitere Drives / SharePoint-Bibliotheken | Noch keine eigenständige Auswahl und vollständige Erfassung | Zusätzliche Discovery und gegebenenfalls Sites-/erweiterte Dateirechte erforderlich. Keine pauschalen Schreibrechte hinzufügen. |
| Google-/Outlook-Kalender | Bestehende Adapter unverändert; Outlook-Zeitraum erforderlich | Synthetische Regressionstests; Echtkonto-Abnahme offen. |

Geteilte Bereiche erfordern zusätzliche Bereichsmodellierung und Testbestände; Rclone-Unterstützung allein genügt nicht für eine vollständige FCA-Erfassung. Ein sinnvoller Zeitaufwand ist erst mit freigegebenem Workspace-/Microsoft-365-Testmandanten und geklärten Rechten belastbar abschätzbar. Google-native Dateien bleiben Exporte, keine unveränderten Binäroriginale. Versionshistorie, gelöschte Inhalte, nicht exportierbare Typen, Paketobjekte und externe Verknüpfungen sind nicht zugesichert. Unfertige Einzeldateien beginnen bei Byte 0; fertig geprüfte Dateien bleiben erhalten.

## Tests und Bereitstellung

Nachweise werden nach dem abschließenden Testlauf unter [Stufe-B-Validierung](stufe-b-validierung.md) festgehalten. Getrennte PostgreSQL-Testdatenbank, isolierte Testcontainer, synthetische Browseranmeldungen und echte Rclone-Prozesse gegen lokale Daten. Ein solcher Test beweist keinen erfolgreichen Google-/Microsoft-Login und keine reale Providerleistung.

Vor den Tests: neue Datenbank-, Sicherungsdaten- und Zugangskonfigurationsarchive; Wiederherstellung sämtlicher 16 öffentlicher Tabellen in einer separaten Datenbank identisch geprüft. Originale Sicherungsdaten und pausierter Lauf bleiben unangetastet. Keine Bereitstellung in den laufenden Laborcontainern, solange GitHub CI nicht nachweislich erfolgreich ist. Keine DNS-, TLS- oder Anbieteränderung ausgeführt.

## Nächster Freigabepunkt

Der echte Google-Test benötigt einen ausgewählten Namen, freigegebene DNS-/Zertifikatseinrichtung, eine eigene Google-Web-App und die persönliche Zustimmung des Auftraggebers. [Vorbereiteter Ablauf und einmalige Administration](private-https-oauth.md). Die tatsächliche Anmeldung führt der Auftraggeber im eigenen Browser durch. Microsoft folgt mit getrenntem Testkonto. Kein Windows-Anmeldehelfer entwickelt.
