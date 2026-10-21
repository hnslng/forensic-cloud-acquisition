# Stufe A – technische Befunde und Prüfnachweise

> Historischer Befund aus Commit `4553cc4`. Der aktuelle Entwicklungsstand steht unter [Stufe B](stufe-b-status.md). Die damaligen Befundprüfungen sind mit dem damaligen Code zu reproduzieren; behobene Fehler müssen heute nicht mehr reproduzierbar sein.

## 1. Was tatsächlich vorhanden ist

Browser → privates HTTPS/Nginx → FastAPI; PostgreSQL enthält Benutzer, Fälle, Mitgliedschaften, Konten, Inventar, Warteschlange und Audit. Ein separater Worker koordiniert maximal zwei Konten und je bis zu vier Dateiübertragungen mit laufender Nachbesetzung. Ein Datenbank-Advisory-Lock verhindert doppelte Koordinatoren. Netzwerkzugriffe liegen außerhalb langer Schreibtransaktionen. Es gibt keine Redis-Abhängigkeit.

- `providers/acquisition.py`: iCloud über Rclone/privaten Unix-Socket; Google und Microsoft derzeit über `WebProvider`/REST, **nicht** über Rclone.
- `backend/oauth.py`: bestehender Web-Authorization-Code-Ablauf mit PKCE S256, einmaligem State, zehn Minuten Gültigkeit und Bindung an Benutzer/Fall/Konto. Tokens sind getrennt je Konto authentifiziert verschlüsselt; der externe Hauptschlüssel bleibt außerhalb von Git und Datenbank. Die Pending-Struktur bindet noch nicht zusätzlich an eine konkrete FCA-Sitzungs-ID.
- `backend/main.py`: Anmeldung, sichere Cookies, Origin/CSRF, Fallrechte, Eingabevalidierung, Administrator-Konfiguration. `frontend/oauth-callback.js` entfernt den Code aus der sichtbaren URL und nutzt einen geschützten POST. Die Einstellungen verlangen derzeit HTTPS und die aktuelle FCA-Origin.
- `backend/acquisitions.py`: persistente Dateizustände, begrenzte Übertragungen, Wiederholungen, Speicherprüfung, MD5/SHA-256, atomare Übernahme, Berichte. Fertige Dateien werden bei Wiederaufnahme geprüft; unfertige Dateien starten bei Byte 0. Keine allgemeine Byte-/HTTP-Range-Wiederaufnahme versprechen.
- Technische Fallpfade enthalten die normalisierte Fallnummer und Fall-UUID; Konten sind nummeriert, Läufe UUID-basiert. Frei vergebene Kontobezeichnungen werden nicht automatisch in Pfade eingesetzt.
- Schema 8, Compose-Limits: API 384 MiB, Worker 512 MiB, Datenbank 512 MiB. Die Konfigurationsobergrenzen 4/2 sind zusätzlich in API, Datenbank und Thread-Pools festgeschrieben. Skalierbarkeit über diese Grenzen ist in Stufe B vorzubereiten, nicht bereits vorhanden.
- Installationsbestand: VM-spezifische Bootstrap-, Datenbank- und HTTPS-Skripte; noch kein fertiger, allgemeiner Behördeninstaller. Laborpfade, Netzwerte und externe Secrets müssen im späteren Installer als Installationsparameter behandelt werden. Keine Installation oder Migration in Stufe A.

`oauth.py` bleibt erforderlich, unter anderem für Kalender und verschlüsselte Zustände. Es wird nicht entfernt. Die Provider-READMEs und Architekturübersicht waren teilweise veraltet und wurden dokumentarisch korrigiert; Laufzeitcode, Oberfläche und VM wurden nicht verändert.

## 2. Bewertung der Anmeldevarianten

| Variante | PC-Voraussetzung / Bedienung | Sicherheits- und Betriebsbewertung |
|---|---|---|
| Bestehender Webflow unter administriertem HTTPS-Namen | Browser; Administrator richtet Namen, TLS und Apps einmalig ein | Bevorzugte Behördenvariante. Rückkehr direkt zu FCA, bewährte Benutzer-/Fallrechte. FCA kann im LAN bleiben; Google benötigt keinen öffentlichen Zugriff auf den Callback, der Browser muss ihn erreichen. Googles Verifizierung kann getrennt davon öffentliche Informations-/Datenschutzseiten verlangen. |
| Desktop-Loopback plus vorbereiteter SSH-Tunnel | Bereits verfügbarer SSH-Client, sichere zentrale Vorbereitung; keine manuell eingegebenen Befehle im Ermittlerablauf | Bedingt geeignet. Ohne vorhandenen Client/zugelassenen Startmechanismus erfüllt dies die Vorgabe „keine Installation“ nicht. Kein beliebiger Shell-Zugang: Tunnelkonto ausschließlich für benötigtes Ziel, Hostschlüsselprüfung, lokale Bindung, keine Passwort-/Tokenübergabe. Auf Windows noch nicht praktisch abgenommen. |
| Lokaler Windows-Anmeldehelfer | Signiertes/zugelassenes Programm und erlaubter lokaler Listener; möglichst portabel ohne Adminrechte | Nur nach gesonderter Entscheidung. Erfordert Updates, Signierung, Endpoint-Freigabe und sichere Einmal-Kopplung an FCA. Keine Entwicklung in Stufe A. |
| Rückkehr-Link/Code/Token einfügen | Clipboard und manuelle Übertragung | Kein Standard. Verwechslungs-/Phishingrisiko und unnötige Exposition über Zwischenablage/Support. Der historische Google-OOB-Flow ist eingestellt; er darf nicht wieder eingeführt werden. Rclone-`authorize` liefert üblicherweise ein Tokenpaket, nicht nur einen harmlosen Code. |
| Microsoft Device Code | Browser plus eingegebener Code, eigene passende App-Konfiguration | Offiziell verfügbar, aber nicht als Standard gewählt. Kontobezogene Phishingrisiken und Conditional-Access-Vorgaben sind zu berücksichtigen. |

[Google Desktop/Loopback und OOB](https://developers.google.com/identity/protocols/oauth2/native-app), [Rclone Remote Setup](https://rclone.org/remote_setup/), [Windows OpenSSH](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse), [Microsoft Device Code](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code), [Microsoft Sicherheitsbewertung](https://learn.microsoft.com/en-us/entra/identity/conditional-access/concept-authentication-flows).

**Drei unterschiedliche Loopbacks:** Ermittler-PC, Debian-VM und Container haben jeweils ihr eigenes `127.0.0.1`. Ein Tunnel zum VM-Loopback erreicht nicht automatisch Rclone im Worker-Container. Für Stufe B ist eine begrenzte Callback-Anbindung über vorhandene Komponenten zu entwerfen; keine öffentliche Veröffentlichung eines Rclone-Steuerports. Eine Browserseite startet von sich aus keinen SSH-Tunnel.

Der synthetisch geprüfte Standardablauf von Rclone 1.75.2 nutzt bei Google `http://127.0.0.1:53682/`, bei Microsoft `http://localhost:53682/`. Ein zweiter gleichzeitiger Listener scheitert am belegten Port. Beide Anfragen enthielten **kein `code_challenge` und keinen `code_verifier`**. State-Prüfung allein ist daher kein Ersatz für den vorhandenen FCA-PKCE-Schutz. Empfehlung: Authentifizierung und Rclone-Dateizugriff getrennt beurteilen; vorhandenen FCA-Schutz wiederverwenden und die Konto-/Sitzungsbindung für den gewählten Transport vervollständigen. Ein Desktop-Client-Geheimnis ist kein verlässlich geheim haltbares Servergeheimnis.

Google verbietet rohe IP-Adressen für normale Web-Rückkehradressen; Desktop-Loopback ist eine eigene Ausnahme. Microsoft verlangt registrierte, exakt passende Rückkehradressen und unterstützt HTTPS. Die Unterlagen enthalten nicht dieselbe allgemeine IP-Sperre wie Google; eine konkrete Registrierung mit der privaten Labor-IP wurde ohne Freigabe nicht angelegt. Deshalb **keine Abnahmezusage für die aktuelle IP**. Die Rclone-App erlaubt außerdem keine beliebige eigene Callback-Adresse; diese ist eine Eigenschaft der fremden App-Registrierung. [Google Webregeln](https://developers.google.com/identity/protocols/oauth2/web-server#uri-validation), [Microsoft Rückkehradressen](https://learn.microsoft.com/en-us/entra/identity-platform/reply-url).

## 3. Registrierungen und Freigaben

Google: eigenes Projekt, Drive API, lesender Scope `drive.readonly`; Desktop-Client für Loopback oder Web-Client für die Domainvariante. Testnutzer nur im Labor. „In Produktion“ und „verifiziert“ sind unterschiedliche Zustände. Eine Ausnahme für interne Workspace-Apps erfasst nicht automatisch beliebige externe Google-Konten. `drive.file` reduziert die Zugriffstiefe auf appbezogen freigegebene Dateien; Metadaten-Scopes erlauben keine vollständigen Downloads. Service Accounts ersetzen keine Anmeldung an fremden Privatkonten; Domain-Delegation setzt eine entsprechende Workspace-Verwaltung und deren Berechtigung voraus.

Für `drive.readonly` und Serververarbeitung ist die Verifizierbarkeit des konkreten FCA-Einsatzzwecks mit Google zu klären. Ohne einschlägige Ausnahme können Verifizierung und jährliche Sicherheitsbewertung erforderlich sein; Zeit und Kosten sind noch nicht ermittelt. Öffentlich erreichbare Informationsseiten im Prüfverfahren sind von einem öffentlich erreichbaren FCA-Dienst zu unterscheiden. [Google Verifizierung](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification), [App-Zustände](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview).

Microsoft: Rclone enthält eine gemeinsame Registrierung, die laut Dokumentation nutzbar sein kann. In der gepinnten Version enthalten die Standard-Scopes auch Schreibrechte. Für FCA ausdrücklich lesende `access_scopes` festlegen; `Files.Read`, gegebenenfalls `Files.Read.All`, `offline_access` sowie nur tatsächlich benötigte Profil-/Sites-Rechte. Persönliche und Geschäftskonten sowie Mandantenrichtlinien getrennt testen. Für den Behördenbetrieb eigene App mit passender Kontozielgruppe, Publisher-/Adminzustimmung nach Bedarf und nachvollziehbarer Berechtigungsverwaltung. Ein einfacher privater OneDrive-Test beweist keine Freigabe in Microsoft-365-Mandanten. [Rclone OneDrive](https://rclone.org/onedrive/#getting-your-own-client-id-and-key).

## 4. Datenumfang und belegte Lücken

| Bereich | Bestehendes FCA | Mit Rclone grundsätzlich zusätzlich möglich / Grenze |
|---|---|---|
| Google-Dateien | „Meine Ablage“, Unterordner, verfügbare Metadaten, Binärdownloads | Geteilte Laufwerke und „Mit mir geteilt“ ausdrücklich getrennt inventarisieren; bloß `supportsAllDrives=true` erreicht nicht automatisch alle Wurzeln. |
| Google Workspace | Docs→DOCX, Sheets→XLSX, Slides→PPTX, Drawings→PDF | Export als abgeleitete Datei kennzeichnen; Name, ID, MIME, Version/Zeitstempel, Exportformat und tatsächliche Größe sichern. SHA-256 bezieht sich auf gespeicherte Exportbytes. `files.export` hat ein 10-MB-Limit; nicht unterstützte Typen als Lücke melden. |
| OneDrive | Standardlaufwerk; Metadaten und Binärdateien | Weitere zugängliche Drives und SharePoint-Bibliotheken brauchen eigene Ermittlung. Verknüpfte und Paketobjekte werden heute ausgelassen; keine Vollständigkeit behaupten. |
| Kalender | Vorhandene Google-/Microsoft-REST-Exporte; Outlook mit definiertem Zeitraum | Die Rclone-Dateibackends ersetzen diese Exporte nicht. |
| iCloud | Anmeldung, 2FA, Drive-/Fotos-Inventar und Downloads; kombinierter Modus implementiert | Vollständige Echtkonto-Abnahme weiterhin offen. Kein Zugriff auf nicht von Apple/Adapter bereitgestellte Backups, Originalvarianten oder geschützte Bereiche zusagen. |

[Google Exporte](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/export), [Rclone Drive](https://rclone.org/drive/), [Microsoft Hashes](https://learn.microsoft.com/en-us/graph/api/resources/hashes?view=graph-rest-1.0).

**Für Stufe B bestätigte Befunde, noch nicht behoben:**

1. `WebProvider.error()` stuft jedes HTTP 403 als wiederholbar ein. Lokaler Test mit Microsoft `accessDenied` bestätigt das. Anbieterfehler nach Grund unterscheiden: Zugriff verweigert/fehlende Claims nicht wie `rateLimitExceeded`/429 behandeln; Retry-After und Backoff nur passend anwenden. [Google Fehlergründe](https://developers.google.com/workspace/drive/api/guides/handle-errors), [Microsoft Fehler](https://learn.microsoft.com/en-us/graph/errors).
2. Ein vorgegebener falscher OneDrive-SHA1 im synthetischen Dateimetadatum wird heute nicht zurückgewiesen. `eTag` und lokale SHA-256 ersetzen keinen Quellhashvergleich. Verfügbare QuickXorHash-/SHA1-Werte im passenden Format vergleichen, fehlende Werte dokumentieren; QuickXorHash nicht als kryptografischen Herkunftsnachweis darstellen.
3. `limitations` sind bislang überwiegend Textlisten; getrennte Zustände/Zähler für „nicht zugänglich“, „nicht unterstützt“, „Übertragungsfehler“ und „Inventar offen“ fehlen im Kontobericht. Aktuelle `bytes_done` enthalten auch Teilübertragungen. Erfolgreich gesicherte Bytes müssen separat über abgeschlossene Dateien summiert werden.
4. Bekannte Bereiche werden derzeit nicht systematisch als untersuchter/nicht untersuchter Umfang bilanziert. Rclone allein macht aus einem gewählten Standardlaufwerk keine vollständige Kontosicherung.
5. Höhere Parallelität scheitert derzeit an festen Grenzwerten in API, Schema und Pools. Spätere Serverprofile brauchen konsistente, begrenzte Ressourcenparameter; die Laborwerte bleiben unverändert.

Erforderliche Berichtsbilanz: je Bereich untersuchte Schnittstelle, tatsächlich gewährte Scopes, Inventar abgeschlossen/offen, erkannte Dateien und Größen (unbekannt ausdrücklich markieren), erfolgreiche Dateien/Bytes, Fehler, unzugängliche/ausgelassene Objekte, unverfügbare Kategorien, Originalmetadaten, Exportformat und SHA-256. Abschluss bezieht sich ausschließlich auf den bilanzierten Umfang.

## 5. Reproduzierbare Testmethode

`scripts/stage_a_probe.py` ist ein isoliertes Prüfskript, kein Windows-Anmeldehelfer und kein Produktionsadapter. Es nutzt einen separaten temporären Ordner, bindet nur Loopback und verbindet keine echten Konten. Benötigt Python 3.12 mit der vorhandenen Cryptography-Abhängigkeit sowie eine geprüfte Rclone-1.75.2-Binärdatei für das lokale Betriebssystem. Das verwendete macOS-Archiv wurde gegen die über HTTPS bezogene offizielle SHA256SUMS-Datei geprüft. Es wird nicht ins Repository aufgenommen.

```sh
PYTHONPATH=. python3 scripts/stage_a_probe.py \
  --rclone /pfad/zur/geprueften/rclone-binaerdatei \
  --output .local/stage-a/results.json --repeats 2
```

Erfasst werden zwei echte Rclone-Prozesse gegen simulierte OAuth-Endpunkte, Ablehnung eines falschen State und Portbelegung; bestehende FCA-OAuth-/Verschlüsselungsfunktionen ohne Datenbankzugriff; die beiden bekannten Providerlücken als **Befundprüfungen**. Ihr Bestehen bedeutet, dass die Lücke reproduziert ist, nicht dass sie behoben wäre.

Die Übertragungsmatrix verwendet 18 synthetische Dateien pro simuliertem Konto, 0 Byte bis 8 MiB, zusammen 41.094.144 Byte. Je zwei Wiederholungen mit 1/2 Konten und 1/2/4/8 Rclone-Transfers. Der lokale HTTP-Server wartet künstlich 2 ms pro 64 KiB; diese Werte simulieren keine reale Providerleitung. CPU-Zeit der Kindprozesse, gesampelter Rclone-RSS und Wandzeit werden erfasst. Finaldateien werden vollständig mit SHA-256 verglichen. Die Prüfung umfasst keine FCA-PostgreSQL-Warteschlange; dafür liegen die früheren getrennten Integrationstests vor.

Ein zusätzlicher Lauf injiziert HTTP 429 und einen TCP-Abbruch. Ein weiterer Versuch beendet einen laufenden Rclone-Prozess und wiederholt die Kopie gegen denselben synthetischen Zielordner. Vorher fertige Dateien müssen unverändert bleiben. Wiederholung/Integrität des allgemeinen HTTP-Backends beweist nicht das exakte Retry-After-Verhalten der Google-/Microsoft-Backends. Der bestehende FCA-Parser wurde zusätzlich mit Retry-After=37 geprüft. Echte API-Drosselung und Browser-/Windows-/Providerabnahme bleiben offen.

Die VM wurde nur lesend über Schema-/Aggregatabfragen, Containerstatus und das vorhandene Ressourcenskript geprüft. Keine Lasttests, Dateien, Konfigurationen, Datenbankzustände, Zugangsdaten oder Beweisdaten auf der VM wurden angelegt oder verändert.

Die Messwerte stehen separat unter [Stufe-A-Messwerte](stufe-a-messwerte.md); maschinenlesbar unter [synthetische Ergebnisse](test-results/stufe-a-synthetic.json).

## 6. Erster freigegebener Kontotest – erst nach Entscheidung

**Google:** Variante auswählen; Administrator richtet dafür den eigenen Client, API und das vorbereitete Testkonto ein. Erst nach separater Login-Freigabe Fall öffnen, Google-Konto hinzufügen, Browseranmeldung durchführen und die angezeigte Kontokennung prüfen. Den vorher definierten kleinen synthetischen Drive-Bestand sichern; Dateiliste, Exporte, tatsächlich geschriebene Größen, SHA-256, Rechtefehler und Wiederaufnahme vergleichen. Keine Tokens manuell kopieren. Die domainlose Variante ist noch nicht in FCA verfügbar.

**OneDrive:** eigener lesender Client oder ausdrücklich freigegebene Rclone-Registrierung; zunächst vorbereitetes Privatkonto, anschließend gesondert Microsoft-365-Testmandant. Nach Login-Freigabe denselben FCA-Ablauf nutzen und die vom Anbieter gelieferten Hashes mit den lokalen Dateien vergleichen. SharePoint/geteilte Inhalte erhalten eine eigene Umfangsbilanz. Ausbleibende Tenant-Zustimmung ist eine Zugriffsbeschränkung, kein erfolgreich leer gesichertes Konto.

**Anhalten:** Keine Umsetzung dieser Punkte, keine neuen Dienste, Tunnelkonten oder Helper, keine Entfernung alter Komponenten und keine Echtkonto-Anmeldung ohne Stufe-B-/Kontotest-Freigabe.
