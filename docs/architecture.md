# Architektur – implementierter Stand und freigabepflichtige Erweiterungen

Stand 21.10.2026, Schema 8. Diese Übersicht beschreibt die vorhandene Implementierung; eine neue Rclone-Anbindung für Google/OneDrive ist noch nicht umgesetzt. [Stufe A](stufe-a-machbarkeit.md) endet vor der Integration.

## Komponenten

Privater Browser → Nginx/HTTPS → statisches Frontend und FastAPI-API. PostgreSQL speichert Benutzer, Sitzungen, Fälle, Mitgliedschaften, Konten, Inventare, Aufträge, Dateizustände und Audit-Protokolle. Ein separater Worker nutzt einen PostgreSQL-Advisory-Lock als Koordinator und einen begrenzten Thread-Pool. Es gibt keinen Redis-Dienst und derzeit keine allgemeine Lease-/SKIP-LOCKED-Architektur.

Maximal zwei Konten und je vier Dateiübertragungen laufen gleichzeitig. Die Erfassung schreibt fortlaufend in die persistente Warteschlange; freie Downloadplätze werden nachbesetzt. Die Werte lassen sich innerhalb der Laborgrenzen reduzieren. Größere Serverprofile erfordern noch Änderungen an API-, Datenbank- und Poolgrenzen.

## Anbieter und Anmeldung

- iCloud: gepinnter Rclone-Prozess je aktiver Kontositzung, verschlüsselte Konfiguration, privater authentifizierter Unix-Socket; Drive und Fotos einzeln oder gemeinsam.
- Google/Microsoft: bestehender `WebProvider` über offizielle REST-Schnittstellen; Google-/Outlook-Kalender bleiben separate Datenkategorien. Noch keine Rclone-Dateiadapter für diese beiden Anbieter.
- `oauth.py`: Authorization Code, PKCE S256, einmaliger zeitlich begrenzter State und Benutzer-/Fall-/Kontobindung. Tokens sind pro Konto verschlüsselt außerhalb der Datenbank abgelegt. Konkrete FCA-Sitzungsbindung und alternative Callback-Transporte gehören zur Bewertung von Stufe B.
- Die vorhandene Webanmeldung setzt eine einmalige Administratorregistrierung voraus. Die aktuell nur per privater IP erreichbare FCA-Adresse genügt Googles normalem Web-Redirect nicht. Ein Desktop-/Loopback-Flow ist eine andere mögliche Variante und noch nicht integriert.

Keine Bestätigung von Kontoverfügbarkeit allein aus einer vorhandenen Implementierung ableiten. [Providerstatus und Grenzen](cloud-acquisition.md), [Stufe-A-Befunde](stufe-a-technik.md).

## Rechte, Ablage und Integrität

Authentifizierte Benutzer und Fallrechte werden serverseitig geprüft; Bearbeiter und Auftraggeber werden im Lauf protokolliert. CSRF-/Origin-Schutz und HTTPS-Cookies schützen mutierende Webzugriffe. Benutzerverwaltung liegt getrennt vom Fallarbeitsbereich. Historische Audit-Fallreferenzen überleben eine ausdrücklich angeforderte administrative Falllöschung.

Fallpfade enthalten die sicher normalisierte Fallnummer und volle Fall-UUID. Kontenordner sind nummeriert, jeder Lauf besitzt eine eigene UUID. Frei gewählte Kontobezeichnungen gelangen nicht automatisch in Pfade. Die Cloud-Struktur wird mit sicheren, stabil nach Quell-ID ergänzten Dateinamen abgebildet; ursprüngliche Namen und Metadaten stehen im Manifest.

Dateien werden temporär heruntergeladen, auf Größe und soweit implementiert auf Anbieterprüfsummen geprüft, lokal mit MD5 und SHA-256 erfasst und ohne Überschreiben atomar übernommen. Neue Prüfberichte enthalten beide lokalen Prüfsummen. Historische Dateien erhalten fehlende MD5-Werte nach erfolgreicher erneuter Prüfung bei Wiederaufnahme. Fertige Dateien bleiben erhalten; unvollständige Einzeldateien beginnen erneut bei Byte 0. Google-native Exporte sind abgeleitete Dateien.

Ein erfolgreicher Auftrag bezieht sich nur auf sein erfasstes Inventar. Nicht inventarisierte Bereiche, fehlende Rechte, nicht unterstützte Objekte und unverfügbare Quellhashes bleiben Einschränkungen. Die strukturierte Umfangsbilanz und der fehlende OneDrive-Quellhashabgleich sind offene Punkte; keine Gesamtkonto-Vollständigkeit zusichern.

## Betrieb und Geheimnisse

Docker Compose trennt API, Worker und PostgreSQL. Die API ist nur an VM-Loopback gebunden; Nginx stellt HTTPS im erlaubten privaten Netz bereit. Rclone besitzt keinen öffentlichen Steuerport. Container laufen ohne Rootrechte, mit schreibgeschütztem System und begrenzten Ressourcen. Laufzustand und Sicherungsdatenträger sind getrennt eingebunden. Hauptschlüssel und Providergeheimnisse liegen außerhalb von Git und Datenbank; ihre gesonderte Sicherung ist für Wiederherstellung nötig.

Es existieren Labor-Bootstrap-, Datenbank-, HTTPS- und Validierungsskripte. Ein allgemeiner, nicht laborspezifischer Installations-/Updatepfad ist noch auszuarbeiten. Code-Rollback ersetzt keine Datenbankwiederherstellung. Stufe B umfasst nach Freigabe Rückwärtskompatibilität, Backup/Restore, Anbieterprüfungen und erst anschließend Bereitstellung. In Stufe A bleibt die VM unverändert.
