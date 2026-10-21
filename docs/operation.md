# Laborbetrieb – Zugang und Administration

Aktuelle Sicherungsbedienung und Anbietergrenzen: [Cloud-Sicherungen 0.5.0](cloud-acquisition.md).
Der neue Worker wird zusammen mit dem API-Profil `application` gestartet. Nach Migration/Update bestehende Fallordner einmalig mit `docker compose --env-file /etc/fca/compose.env exec -T api python -m backend.initialize_evidence` ergänzen. Dies bearbeitet ausschließlich neue Verzeichniszuordnungen, keine bisherigen Falldaten.

## Zugriff

Aktuelles Laborziel: **https://10.0.1.189/**. DHCP ist freigegeben und aktiviert;
bei Adressänderung müssen Ziel, `FCA_PUBLIC_ORIGIN`, nginx und Zertifikat bewusst
angepasst werden. Keine Router-Portweiterleitungen einrichten.

Das HTTPS-Zertifikat wird von der eigenen **FCA Private Lab CA** ausgestellt.
Der öffentliche CA-Nachweis liegt auf der VM in `/etc/fca/tls/lab-ca.crt` und auf
dem Entwicklungsrechner lokal in `.local/fca-lab-ca.crt`. Nur dieses konkrete
Zertifikat nach Fingerprintprüfung am vorgesehenen Laborbrowser als vertrauenswürdig
einrichten. Browser-Zertifikatswarnungen nicht pauschal umgehen; es wurde kein
Vertrauensanker im Betriebssystem des Entwicklungsrechners installiert.

```text
CA SHA-256:
77:6C:AC:1F:A2:37:A4:B8:19:84:ED:BE:C7:A4:62:31:EF:83:98:B0:32:80:85:7F:4F:BF:AB:D0:2A:76:C4:EC
```

Startkonto: `admin`. Das zufällig erzeugte Initialpasswort liegt ausschließlich
als geschützte Secret-Datei unter `/etc/fca/secrets/initial_admin_password`.
Es wird weder im Chat noch in Git dokumentiert. Ein autorisierter Administrator
kann es über den verifizierten SSH-Zugang lokal auslesen. Nach der ersten
Anmeldung über „Passwort ändern“ ein eigenes Passwort setzen (mindestens 14
Zeichen); dabei werden alle Sitzungen widerrufen. Die initiale Passwortdatei
danach kontrolliert entfernen; sie ändert das neue Passwort nicht automatisch.

Der vorbereitete lokale SSH-Zugang verwendet:

```sh
ssh -F .local/fca-ssh-config fca-lab
```

Die Datei und der verifizierte Hostschlüssel bleiben absichtlich außerhalb von
Git. Keine persönlichen privaten SSH-Schlüssel auf die VM kopieren.

Initialpasswort bei Bedarf ausschließlich lokal anzeigen:

```sh
ssh -F .local/fca-ssh-config fca-lab 'sudo cat /etc/fca/secrets/initial_admin_password'
```

## Bedienung

1. Der Startbildschirm zeigt „Fall anlegen“ über dem verschwommenen Arbeitsbereich.
2. „Fall anlegen“ öffnet Geschäftszahl, Fallbezeichnung und Bearbeiterkürzel.
   Bei Bedarf „Arbeitssitzung anmelden“ öffnen; die Falldaten bleiben erhalten.
3. „Fall starten“ legt den Fall an und öffnet unmittelbar seinen Arbeitsbereich.
   Bestehende Fälle über „Fallarchiv öffnen“ auswählen.
4. „+ Cloud hinzufügen“ öffnet die Auswahl iCloud, Google oder OneDrive und die
   freie Kontobezeichnung. Mehrere Konten auch desselben Anbieters sind möglich.
   „Bezeichnung bearbeiten“ ändert den Namen unter Beibehaltung der Konto-ID.
   Für iCloud öffnet „Authentifizieren“ die Apple-Anmeldung mit 2FA. Nach
   erfolgreicher Anmeldung lassen sich Drive und Fotos ausdrücklich öffnen.
   Google-/OneDrive-Anmeldung und Sicherung sind weiterhin deaktiviert.
5. Das Zahnrad öffnet den getrennten Einstellungsbereich: Sitzung/Passwort,
   Fallbezeichnung/Status, administrative Benutzer- und Fallrechte sowie Technik.
   Bearbeiter sehen keine administrativen Reiter; Viewer können nur lesen.
6. „Arbeitsbereich verlassen“ kehrt zum Start zurück und verändert den Fall nicht.
   Abmelden beendet die serverseitige Sitzung. Ein geschlossenes Browserfenster
   ersetzt die Abmeldung nicht; Sitzungen enden nach acht Stunden.
7. iCloud-Zugangsdaten ausschließlich im privaten HTTPS-Dialog eingeben, nie
   im Chat oder in Befehlsargumenten. Details: [iCloud-Betrieb](phase-2-icloud.md).
8. Bei Konfliktmeldung den Fall neu öffnen und den aktuellen Stand prüfen.

Die Fallübersicht liefert derzeit höchstens 500 zugeordnete Fälle; eine
serverseitige Suche/Paginierung folgt vor größeren Beständen.

## Dienste und Konfiguration

Auf der VM als autorisierter Administrator:

```sh
sudo docker compose --project-directory /opt/fca --env-file /etc/fca/compose.env --profile application ps
sudo systemctl status nginx chrony fca-firewall qemu-guest-agent
sudo python3 /opt/fca/scripts/resource_snapshot.py
```

nginx läuft als Debian-Systemdienst und liefert das getrennte Frontend aus
`/var/www/fca`. API und PostgreSQL laufen in Compose. Die bewusste Abweichung
vom komplett containerisierten Proxy erleichtert private Firewall- und TLS-
Verwaltung auf der kleinen VM. Der API-Port ist nur auf `127.0.0.1:8000`
veröffentlicht. Der Datenbank-Port bleibt unveröffentlicht.

Quellcodeänderungen erfordern einen geprüften Build, DB-Migrationen und den
bewussten Wechsel. Python-Basisimage und PostgreSQL sind auf Digests fixiert;
direkte Anforderungen und vollständig aufgelöste Python-Locks liegen unter
`backend/`. Lock-Updates erfordern erneute Tests. Kein automatisches
`git pull` oder ungeprüftes Online-Skript auf der VM.

## Tests und Wiederherstellung

```sh
sudo bash /opt/fca/scripts/run_phase1_tests.sh
```

Das führt API-Integrationstests und echte Chromium-Browserabläufe aus. Der
Browser läuft ausschließlich im begrenzten Testcontainer gegen Loopback und
synthetische Daten. Produktives HTTPS und sichere Cookies bleiben unverändert.
Synthetische Bildschirmnachweise liegen unter `/var/lib/fca/validation/browser`
außerhalb des Repositories. Der Test erzeugt und entfernt ausschließlich
`fca_test_phase1`; keine Anwendungstests
gegen echte Arbeitsdaten ausführen. Die einmalige Phase-0-Erstabnahme darf
nicht erneut als Bootstrap über die bestehende Datenbank ausgeführt werden.
`validate_phase0_after_reboot.sh` ist dagegen eine lesende Persistenzprüfung
mit Healthcheck und geeignet für den erhaltenen synthetischen Nachweis.

`/var/backups/fca/phase0.dump` ist die geprüfte **synthetische Restoreprobe**,
kein aktuelles vollständiges Betriebsbackup. Für ein aktuelles Backup sind DB,
Beweisdaten, Konfiguration und benötigte Schlüssel getrennt und konsistent zu
sichern. Vor produktivem Betrieb ist ein unabhängiges verschlüsseltes Ziel
einzurichten und wiederholt praktisch zu restaurieren. Root- und DB-Administratoren
können weiterhin technische Daten verändern; das Audit ist kein WORM-Speicher.
