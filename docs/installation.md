# FCA auf einem vorbereiteten Debian-13-Server installieren

Diese Anleitung betrifft den neuen Paketinstaller. Die bestehende FCA-Labor-VM
wird damit **nicht** neu installiert oder automatisch übernommen. Ihr bisheriger
Aufbau bleibt unter [historische Laborinstallation](laborinstallation-historisch.md)
dokumentiert. Abnahme und Einschränkungen: [Installertests](installer-tests.md).

## Empfohlene Ausstattung

| Einsatz | CPU / RAM | Systemdisk | Sicherungsdisk |
|---|---|---|---|
| Kleines Labor | mindestens 2 vCPU / 2 GiB, empfohlen 4 GiB | 64 GiB empfohlen | eigener eingebundener Datenträger |
| Zwei aktive Cloud-Konten | empfohlen 4 vCPU / 8 GiB | 64 GiB | Umfang + temporäre Dateien + Reserve |
| Behördenbetrieb | Ausgangspunkt 8 vCPU / 16 GiB, empfohlen 32 GiB | 64–128 GiB SSD | bedarfsgerecht, getrenntes Backupziel |

Dies sind Planungswerte, keine zugesicherte Cloud-Durchsatzleistung. Bei 2 GiB
bleiben Containergrenzen und standardmäßig vier Dateien je Konto / zwei aktive
Konten konservativ. Größere Profile erhöhen diese Werte nicht automatisch.
FCA-Einstellungen steuern die tatsächliche Parallelität innerhalb der installierten
Grenzen. Weitere Messungen: [Stufe-B-Validierung](stufe-b-validierung.md).

Zunächst unterstützt: Debian 13 **amd64**, systemd, vorhandenes Python 3, iproute2,
ein dedizierter Server bzw. eine eigene VM. Debian-Cloud-Images erfüllen diese
Grundlage. Der Installer verändert keine Proxmox-Konfiguration und formatiert
keinen Datenträger. Einrichtung von VM, Netzwerk, WireGuard, DNS, Firewall und
Datenträgerverschlüsselung bleibt beim Administrator.

## Vorbereiten

1. Privaten Serverzugang und Zeitsynchronisation prüfen. Debian-Sicherheitsupdates
   kontrolliert einspielen. Kein öffentlicher Zugriff und keine Routerfreigaben.
2. Separate Datendisk selbst vorbereiten und dauerhaft z. B. unter
   `/srv/fca/evidence` einbinden. Ein vollständig leerer Datenträger ist für die
   Erstinstallation erforderlich; ein leeres `lost+found` ist erlaubt. Der Installer
   hinterlegt eine eindeutige Kennung und verweigert bei fehlendem/falschem Mount
   den Start. Ein automatischer Fallback auf die Systemdisk ist ausgeschlossen.
3. Administrativ freigegebene Zertifikatskette, privaten Schlüssel (root, 0600)
   und vertrauenswürdige CA-Kette bereitstellen. Kein Schlüssel wird versendet.
   Der Installer erstellt keine CA, fordert kein Zertifikat an und ändert kein DNS.
4. Geprüftes, signiertes Versionspaket und **unabhängig erhaltenen** öffentlichen
   Release-Prüfschlüssel auf den Server übertragen. Version ausdrücklich wählen;
   niemals `latest`, `git pull` oder ein Online-Skript direkt ausführen.
   Vor dem ersten Start auch die mitgelieferten Installationswerkzeuge anhand des
   freigegebenen Gesamtpakets prüfen: ein manipuliertes Prüfprogramm kann seine
   eigene Echtheit nicht beweisen. Der Prüfschlüssel darf nicht aus demselben
   unbestätigten Download als neuer Vertrauensanker übernommen werden.

### Privates Labor

Vorhandene private IPv4-Adresse und interne CA verwenden. Das Zertifikat muss
die tatsächlich verwendete IP als IP-SAN enthalten. Browser vertrauen gezielt der
internen CA. Mit IP-Zugriff sind nicht alle Google-OAuth-Szenarien möglich.

### Behördenbetrieb über WireGuard

Vorhandene private WireGuard-/Server-IPv4, internen HTTPS-Namen und ausdrücklich
zugelassene private Quellnetze verwenden. Der Browser muss den Namen intern
auflösen und der Zertifikatskette vertrauen. WireGuard wird durch FCA weder
installiert noch umkonfiguriert. Für OAuth zusätzlich die Anforderungen des
Anbieters an Name, Zertifikat, Registrierung und Scopes prüfen; ein interner
Fantasiename allein garantiert keine Google-Freigabe. Siehe
[private HTTPS-/OAuth-Konfiguration](private-https-oauth.md).

## Installieren

Aus den vorher geprüften Werkzeugen, als Administrator:

```sh
sudo ./install.sh --package /root/fca-0.6.0 --trusted-key /root/fca-release.pub
```

Abgefragt werden Betriebsart, vorhandene IP/HTTPS-Adresse, erlaubte Netze,
Sicherungs- und Backup-Speicher, Ressourcenprofil und vorhandene TLS-Dateien.
Keine Cloud-Zugangsdaten oder Tokens eingeben. Die Zusammenfassung vor der
Installation prüfen. Für reproduzierbare Administrationsabläufe gibt es eine
JSON-Antwortdatei (`--config`); das synthetische Schema steht in
`tests/installer/answers.json`. `--yes` ist für vorab geprüfte automatisierte
Abläufe gedacht und überspringt keine Sicherheitsprüfungen.

Der Installer prüft Release-Signatur und SHA-256 aller Dateien, lädt ausschließlich
enthaltene Images mit fixierter Inhalts-ID und installiert die enthaltenen,
versionsgebundenen Debian-Pakete ohne Netzwerkdownload. Fehlende Pakete werden
installiert; ältere auf den geprüften Stand aktualisiert. Neuere abweichende
Pakete werden nicht heruntergestuft: hier ist ein neuer geprüftes Paket bzw.
ein administrativer Abgleich nötig. Fremde Paketquellen werden nicht hinzugefügt.

FCA läuft als Dienst `fca`, mit API und Worker als Benutzer 10001 und PostgreSQL
im internen Docker-Netz. Nur nginx bindet HTTPS an die ausgewählte private IP,
mit Quellnetzbegrenzung. API ausschließlich `127.0.0.1:8000`, keine öffentliche
Datenbank. Vorhandene Webserverkonfigurationen werden nicht übernommen.

## Ablage und Erstzugang

| Inhalt | Ort |
|---|---|
| Unveränderliche Versionen | `/opt/fca-releases/<Version>` |
| Aktive Programmversion | `/opt/fca-current` |
| Installation und Compose-Konfiguration | `/etc/fca` |
| Unabhängig bestätigter Release-Prüfschlüssel | `/etc/fca/release.pub` |
| Passwortdateien und Cloud-Hauptschlüssel | `/etc/fca/secrets` |
| Datenbank und verschlüsselter Cloud-Zustand | `/var/lib/fca` |
| Beweisdaten | konfigurierter, geprüfter Sicherungsmount |
| Vollständige Wartungsbackups | konfigurierter geschützter Backupordner |

Startbenutzer: `admin`. Das zufällige Initialpasswort ist nur lokal in
`/etc/fca/secrets/initial_admin_password` verfügbar. Am autorisierten Server
abrufen, direkt über privates HTTPS anmelden und das Passwort ändern. Danach
die Initialpasswortdatei kontrolliert entfernen. Kein Passwort in Tickets,
Screenshots oder Befehlsargumente kopieren. Bestehende Geheimnisse werden bei
Wiederholung und Update nicht neu erzeugt.

Google-/Microsoft-App-Einstellungen bleiben unter den administrativen
FCA-Einstellungen nachträglich pflegbar. Kein persönlicher GitHub-Zugang und
keine API-Schlüssel pro Ermittler nötig. Echte Cloud-Anmeldungen erst im
separat genehmigten Test durchführen.

## Prüfen und aktualisieren

```sh
sudo python3 /opt/fca-current/scripts/fca_admin.py diagnose
sudo ./update.sh --package /root/fca-0.6.1 --trusted-key /root/fca-release.pub
```

Die Diagnose prüft erneut Signatur und Dateiinhalt der installierten Version und meldet Mount/Kennung, Dienste und Healthchecks, Datenbankschema,
Schlüsselrechte, Schreibrechte, CPU/RAM/Speicher und HTTPS-Vertrauen. Sie gibt
keine Geheimnisse aus und verändert keine Betriebseinstellungen. Zusätzlich
Firewall und Erreichbarkeit aus einem **nicht zugelassenen** Netz prüfen;
eine lokale Prüfung ersetzt diese externe Netzabnahme nicht.

Ein wiederholter Installationsaufruf prüft dieselbe Installation und verändert
keine Daten. Abgebrochene Erstinstallationen lassen sich mit demselben signierten
Paket und derselben Konfiguration fortsetzen. Eine andere Version wird nur über
`update.sh` installiert. Der alte Laboraufbau wird ausdrücklich verweigert.

Updates stoppen API/Worker für ein konsistentes vollständiges Backup, prüfen eine
Datenbankwiederherstellung, migrieren anschließend und schalten atomar die
Programmversion um. Browser sind während der Wartung nicht verfügbar. Laufende
Downloads werden kontrolliert gestoppt und über die bestehende dauerhafte
Warteschlange wiederaufgenommen; manuell pausierte Aufträge bleiben pausiert.
Keine Cloud-Anmeldung oder Sicherung wird durch den Installer neu angelegt.

Updates verändern keine Betriebssystemabhängigkeiten nebenbei. Falls diese vom
neuen Paket abweichen, muss der Administrator die Plattformwartung separat
planen. Alte Programmstände und Backups bleiben erhalten; kein automatisches
Pruning von Sicherungen oder Images.

[Backup, Wiederherstellung und Rollback](backup-restore-rollback.md) ·
[Releaseerstellung und Behördenempfehlung](release-packages.md)
