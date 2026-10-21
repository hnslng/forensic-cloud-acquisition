# Phase 2 – iCloud zuerst

Der Benutzer möchte ein vollständig vorbereitetes Labor, um danach sein eigens
vorbereitetes iCloud-Konto direkt in FCA anzumelden und erreichbare Bereiche zu
prüfen. Ein vorab festgelegter Testordner ist dafür nicht erforderlich. Es wurden
keine Zugangsdaten geliefert und bisher kein echtes iCloud-Konto angemeldet.

## Verbindlicher Ablauf

1. Fall wie bisher starten und ein iCloud-Konto mit freier Bezeichnung hinzufügen.
2. „Authentifizieren“ öffnet den geschützten iCloud-Dialog.
3. Apple-ID und reguläres Apple-Passwort eingeben; app-spezifische Passwörter sind
   für diesen Adapter ungeeignet. Eingabe ausschließlich im privaten HTTPS-Labor.
4. Den Code des vertrauenswürdigen Apple-Geräts bestätigen; bei Bedarf SMS
   anfordern und den von Apple angebotenen Zustellweg wählen.
5. Nach erfolgreicher Anmeldung „iCloud Drive ansehen“ oder „iCloud Fotos ansehen“
   wählen. Jede Aktion liest ausschließlich die gewählte Verzeichnisebene.
6. Ordner/Alben können geöffnet werden. Es startet weder ein Gesamtscan noch
   ein Download. „Sicherung starten“ bleibt bis zur Implementierung von Phase 3
   deaktiviert. Angezeigte Bereichsnamen beweisen keine Vollständigkeit.
7. Über „Gespeicherte iCloud-Anmeldedaten entfernen“ wird nur die lokale
   Verbindungskonfiguration entfernt; Cloud-Dateien werden nicht verändert.

Das freigegebene dunkelblaue Design ist eingefroren. Nur funktional notwendige
Bedienelemente für Anmeldung, 2FA und Bereichsübersicht werden ergänzt.

## Tatsächliche Implementierung

- rclone `v1.75.2`, auf den geprüften Image-Digest
  `sha256:2687085f718d3c628f7fdfb77c52a1d344332aed543110bb88088f2c70d43eb5`
  fixiert. Upstream-Quellstand `be8d6044eacb843b74d335db0c5fbe09222031fe`.
- `providers/apple/adapter.py` kapselt reguläre SRP-Anmeldung, 2FA und explizite
  einseitige Bereichsabfrage. Keine Shell-Eingaben oder Remote-Schreiboperationen.
- rclone-Prozess nur während einer Anfrage, ohne TCP-Listener; zufällig
  authentifizierter Unix-Socket in privatem temporärem Verzeichnis.
- API validiert Sitzung, CSRF, Origin, Fall- und Schreibrecht vor jedem Zugriff
  und prüft die Berechtigung nach der Netzwerkanfrage erneut.
- Maximal eine Provideranfrage gleichzeitig auf der kleinen VM; acht
  Anmelde-/Bestätigungsversuche pro Konto in zehn Minuten.
- Provideranmeldung und Cookies liegen in einer verschlüsselten Konfiguration
  unter `/var/lib/fca/cloud-auth/<Fall-UUID>/<Konto-UUID>/rclone.conf`.
  Die zugrunde liegende rclone-Konfiguration kann das reguläre Apple-Passwort
  enthalten und ist deshalb vollständig verschlüsselt, nicht bloß „obscured“.
- Der unabhängige Hauptschlüssel liegt in `/etc/fca/secrets/cloud_master_key`
  außerhalb von Datenbank, Git und Konfigurationsbackup. Kontoschlüssel werden
  per HMAC mit Fall-/Konto-ID abgeleitet; bestehender Schlüssel wird nie ersetzt.
- Temporäre Authentifizierungszustände werden verschlüsselt durch rclone
  gespeichert. Eine private Begleitdatei enthält lediglich den nicht geheimen
  2FA-Schrittnamen, zufällige Challenge-ID, Ablauf, Initiator und numerische
  Zustellweg-Auswahlwerte; niemals Passwort, Code oder Cookie.
- Challenge zehn Minuten gültig und an den anmeldenden FCA-Benutzer gebunden.
  Die Verbindung verlangt spätestens nach konservativen 29 Tagen eine Anmeldung.
  Providerfehler werden sicher zusammengefasst, niemals unverändert ausgegeben.
- Datenbankmigration 0005 ergänzt ausschließlich Anmeldeversuchszähler. Vorhandene
  Cloud-Katalogzeilen einschließlich ihres bisherigen Status bleiben erhalten;
  aktueller Verbindungsstatus wird separat ermittelt. Sicherung bleibt unverfügbar.
- Die API veröffentlicht weiterhin nur den privaten nginx-Zugang. rclone hat
  weder Hostports noch einen von Browsern erreichbaren Verwaltungsendpunkt.

## Anbietergrenzen und Quellen

Die Funktionen wurden am festgeschriebenen Releasequellcode und zur Vorbereitung
an der [rclone-iCloud-Dokumentation](https://rclone.org/iclouddrive/) geprüft.
Drive und Photos sind getrennte Dienste. Der Fotoszugriff ist in rclone lesend;
Live-Photo-Begleitdateien, Metadaten, große Alben und unterschiedliche Bibliotheken
müssen in einer echten Testkonto-Abnahme gesondert geprüft werden.

[Apple erläutert Webzugriff und erweiterten Datenschutz](https://support.apple.com/en-us/102630).
Bei aktiviertem erweitertem Datenschutz können Webzugriff und eine temporäre
Gerätefreigabe erforderlich sein. FCA verändert diese Apple-Einstellungen nicht.

[rclone RC ist ein privilegierter Verwaltungszugang](https://rclone.org/rc/).
Deshalb existiert ausschließlich private, authentifizierte lokale Kommunikation;
Browser erhalten weder diesen Zugriff noch Tokens oder Konfigurationsschlüssel.

## Nachweise und offene Abnahme

Acht Offline-Vertragstests verwenden das echte fixierte rclone ohne Netzwerk:
Version/Fähigkeiten, Unix-Authentifizierung, vollständige Konfigurations-
Verschlüsselung, erneutes Öffnen, falscher Schlüssel, Kontotrennung, Sperren,
Zustandsparser, verweigerte Schreibbefehle und Standardlauf ohne Cloudzugriff.
Ein speicherinterner synthetischer rclone-Backend ersetzt dabei ausschließlich
Testkonfigurationen, niemals eine behauptete Apple-Anmeldung.

Zusätzliche API- und Browserprüfungen verwenden ausdrücklich synthetische
Providerantworten, um 2FA-Bedienung, Zugriffsschutz und Audit zu prüfen. Diese
Tests sind kein Nachweis erfolgreicher echter Apple-Kommunikation.

Noch offen bis zur persönlichen Anmeldung mit dem vorbereiteten Konto:
reguläre Apple-Anmeldung/2FA, tatsächlich erreichbare Drive-/Fotosbereiche,
ADP-Verhalten und Ablauf/Erneuerung einer echten Apple-Sitzung. Downloads,
Queue/Wiederanlauf, SHA-256-Manifeste und Sicherungsabschluss gehören zu Phase 3/4.
Google und Microsoft bleiben deaktiviert. Es werden keine realen Downloadwerte,
Erfolge oder Vollständigkeitszusagen simuliert.

## Betrieb und Wiederherstellung

Datenbank und Provider-Konfigurationen vor Updates sichern. Den Hauptschlüssel
unabhängig und verschlüsselt sichern; ohne ihn lassen sich bestehende
Providerkonfigurationen nicht wiederherstellen. Ein DB-Restore allein genügt nicht.
Die getrennten Kommandozeilen-Werkzeuge `compose.icloud-lab.yaml` und
`scripts/prepare_icloud_test.py` bleiben optionale Entwicklerwerkzeuge. Der
normale Benutzer benötigt sie nicht und meldet sich direkt über FCA an.

## Bereitstellung und Abnahme am 21.10.2026

Implementierungscommit `cc43fa76271901f42ab4776fd9232df7ef681880`,
Version 0.4.1 auf VM 105 bereitgestellt. [GitHub-Testlauf erfolgreich](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39647423448).

**45 automatisierte Prüfungen bestanden:** 11 Infrastruktur-, 21 API-/DB-,
5 Chromium-Browser- und 8 echte rclone-Offline-Vertragstests. Browser und API
prüfen den iCloud-Ablauf mit klar synthetischen Providerantworten; die Offline-
Vertragstests laufen ohne Netz. Damit wird ausdrücklich keine erfolgreiche
reale Apple-Anmeldung behauptet.

Zusätzlich im laufenden API-Container praktisch geprüft: iCloud-Funktion
aktiviert, separater Hauptschlüssel lesbar, exakte rclone-Version, erfolgreiche
lokale authentifizierte Adapterkommunikation und Drive-/Photos-Fähigkeiten.
Der technische Vorabcheck führte keine Apple-Anmeldung aus und nutzte nur ein
privates temporäres Verzeichnis, keine Kontokonfiguration der Anwendung.

Private TLS-Zertifikatskette/IP und SHA-256 der drei ausgelieferten Frontenddateien
entsprechen dem Quellstand. API gesund; anonyme Abfragen von Fall- und
Providerstatus werden abgewiesen. Ports 80, 5432 und 8000 sind weiterhin aus dem
LAN nicht erreichbar. Nur die API wurde neu gestartet; kein VM-/Host-Neustart.

Vor der additiven Migration 0005: vollständiges Datenbankbackup und alter
Quellstand unter `/var/backups/fca/phase2-icloud-web`, rootgeschützt. Das Backup
wurde erfolgreich in `fca_restore_phase2_check` wiederhergestellt; die separate
Prüfdatenbank danach entfernt. Nach Bereitstellung sind alle vorherigen Zeilen
in Benutzer-, Fall-, Rechte-, Cloud-Konto-, Sitzungs-, Limit-, Audit- und
Phase-0-Nachweistabellen anhand gespeicherter Zeilenprüfsummen unverändert.
Der neue Anmeldeversuchszähler ergänzt das Schema, ohne alte Daten umzuschreiben.

Momentaufnahme nach Bereitstellung um 19:54 Europe/Vienna: 1,37 GiB RAM verfügbar,
API 52,58 MiB, PostgreSQL 52,29 MiB; 19,17 GiB auf der Systemdisk frei. Die
Systembelegung enthält zusätzliche Browser-/Adapter-Testimages und Build-Caches.
Dies ist kein Cloud-Last- oder Downloadnachweis.

Bildschirmnachweise: privater VM-Pfad `/var/lib/fca/validation/browser`, lokal
`.local/phase2-validation`. Sie enthalten ausschließlich synthetische Konten und
Providerantworten. Passwörter, Codes und Tokens sind nicht in Git gespeichert.
