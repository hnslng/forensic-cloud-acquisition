# Architektur – implementierter Stand und freigabepflichtige Erweiterungen

Stand 22.10.2026: Stufe-B-Entwicklungszweig mit Schema 9, isoliert getestet und nach erfolgreicher CI auf der Laborinstallation bereitgestellt. Echtkonto-Abnahme steht aus. [Stufe-B-Status](stufe-b-status.md).

## Komponenten

Privater Browser → Nginx/HTTPS → statisches Frontend und FastAPI-API. PostgreSQL speichert Benutzer, Sitzungen, Fälle, Mitgliedschaften, Konten, Inventare, Aufträge, Dateizustände und Audit-Protokolle. Ein separater Worker nutzt einen PostgreSQL-Advisory-Lock als Koordinator und einen begrenzten Thread-Pool. Es gibt keinen Redis-Dienst und derzeit keine allgemeine Lease-/SKIP-LOCKED-Architektur.

Maximal zwei Konten und je vier Dateiübertragungen laufen gleichzeitig. Die Erfassung schreibt fortlaufend in die persistente Warteschlange; freie Downloadplätze werden nachbesetzt. Die Laborwerte bleiben unverändert. Installationsprofile über `FCA_MAX_FILE_PARALLELISM` und `FCA_MAX_ACCOUNT_PARALLELISM` können nach Lastprüfung größere Grenzen erlauben: maximal 16/8 und 32 Plätze insgesamt. Migration 0009 erhält bestehende Einstellungen und Dateien; API und Worker begrenzen identisch.

## Anbieter und Anmeldung

- iCloud: gepinnter Rclone-Prozess je aktiver Kontositzung, verschlüsselte Konfiguration, privater authentifizierter Unix-Socket; Drive und Fotos einzeln oder gemeinsam.
- Google/Microsoft: offizielles REST-Inventar und Rclone-Dateitransport über private Unix-Sockets. Google kopiert anhand der Original-ID; OneDrive vergleicht die zum Pfad aufgelöste ID. Google-/Outlook-Kalender bleiben separate REST-Datenkategorien.
- `oauth.py`: Authorization Code, PKCE S256, einmaliger zeitlich begrenzter State und Benutzer-/Sitzungs-/Fall-/Kontobindung sowie Bindung an Client und Rückkehradresse. Tokens sind pro Konto verschlüsselt außerhalb der Datenbank abgelegt. Während einer Dateisitzung ist Rclone alleiniger Refresh-Eigentümer; aktualisierte Tokens bleiben verschlüsselt erhalten und werden mit FCA synchronisiert.
- Die vorhandene Webanmeldung setzt eine einmalige Administratorregistrierung voraus. Die aktuell nur per privater IP erreichbare FCA-Adresse genügt Googles normalem Web-Redirect nicht. Ein Desktop-/Loopback-Flow ist eine andere mögliche Variante und noch nicht integriert.

Keine Bestätigung von Kontoverfügbarkeit allein aus einer vorhandenen Implementierung ableiten. [Providerstatus und Grenzen](cloud-acquisition.md), [Stufe-A-Befunde](stufe-a-technik.md).

## Rechte, Ablage und Integrität

Authentifizierte Benutzer und Fallrechte werden serverseitig geprüft; Bearbeiter und Auftraggeber werden im Lauf protokolliert. CSRF-/Origin-Schutz und HTTPS-Cookies schützen mutierende Webzugriffe. Benutzerverwaltung liegt getrennt vom Fallarbeitsbereich. Historische Audit-Fallreferenzen überleben eine ausdrücklich angeforderte administrative Falllöschung.

Fallpfade enthalten die sicher normalisierte Fallnummer und volle Fall-UUID. Kontenordner sind nummeriert, jeder Lauf besitzt eine eigene UUID. Frei gewählte Kontobezeichnungen gelangen nicht automatisch in Pfade. Die Cloud-Struktur wird mit sicheren, stabil nach Quell-ID ergänzten Dateinamen abgebildet; ursprüngliche Namen und Metadaten stehen im Manifest.

Dateien werden temporär heruntergeladen, auf Größe und soweit implementiert auf Anbieterprüfsummen geprüft, lokal mit MD5 und SHA-256 erfasst und ohne Überschreiben atomar übernommen. Neue Prüfberichte enthalten beide lokalen Prüfsummen. Historische Dateien erhalten fehlende MD5-Werte nach erfolgreicher erneuter Prüfung bei Wiederaufnahme. Fertige Dateien bleiben erhalten; unvollständige Einzeldateien beginnen erneut bei Byte 0. Google-native Exporte sind abgeleitete Dateien.

Ein erfolgreicher Auftrag bezieht sich nur auf sein erfasstes Inventar. Nicht inventarisierte Bereiche, fehlende Rechte, nicht unterstützte Objekte und unverfügbare Quellhashes bleiben Einschränkungen. Berichte bilanzieren diese Zustände getrennt. OneDrive-QuickXorHash/SHA1/CRC32 werden geprüft, sofern vorhanden; fehlender oder historisch nicht aufgezeichneter Vergleich wird ausgewiesen. Keine Gesamtkonto-Vollständigkeit zusichern.

## Betrieb und Geheimnisse

Docker Compose trennt API, Worker und PostgreSQL. Die API ist nur an VM-Loopback gebunden; Nginx stellt HTTPS im erlaubten privaten Netz bereit. Rclone besitzt keinen öffentlichen Steuerport. Container laufen ohne Rootrechte, mit schreibgeschütztem System und begrenzten Ressourcen. Laufzustand und Sicherungsdatenträger sind getrennt eingebunden. Hauptschlüssel und Providergeheimnisse liegen außerhalb von Git und Datenbank; ihre gesonderte Sicherung ist für Wiederherstellung nötig.

Es existieren Labor-Bootstrap-, Datenbank-, HTTPS- und Validierungsskripte. Ein allgemeiner, nicht laborspezifischer Installations-/Updatepfad ist noch auszuarbeiten. Code-Rollback ersetzt keine Datenbankwiederherstellung. Der allgemeine Domain-/WireGuard-/TLS-Installationsablauf ist [dokumentiert](private-https-oauth.md); ein Generator erzeugt nur prüfbare lokale Konfiguration. Vor einer Übernahme: Backup/Restore, Regression und nachweislich grüne GitHub CI. Externe Einstellungen und echte Anmeldungen bleiben gesondert freizugeben.
