# Phase 1 – Basiszugang und Fallverwaltung umgesetzt

21.10.2026. Reale Bereitstellung auf der freigegebenen VM 105.

## Verfügbar

- FastAPI-Backend und separates deutschsprachiges HTML/CSS/JS-Frontend.
- Privates HTTPS mit eigener Labor-CA, geprüfter Zertifikatskette und IP-SAN.
- Lokaler Administrator und administrativ angelegte persönliche Benutzer.
- Argon2id-Passwortableitung (64 MiB, drei Durchläufe, eine Lane), begrenzte
  parallele Passwortprüfungen und begrenzte Anmeldeversuche.
- Persistente achtstündige Sitzungen, zufällige Tokens nur gehasht in der DB,
  `Secure`-/`HttpOnly`-/`SameSite=Strict`-Sitzungscookie und CSRF-/Origin-Prüfung.
- Passwortänderung widerruft alle Sitzungen. Deaktivierung widerruft Zugriff.
- Mehrere Fälle mit UUID, Geschäftszahl, optionalem Namen, UTC-Erstellung,
  Bearbeiterkürzel, Status, persönlicher Zuordnung und Fallprotokoll.
- Fallbezogene Lese-/Bearbeitungsrechte, administratives Erteilen und Entziehen.
  Administratoren haben bewusst fallübergreifenden Zugriff; Bearbeiter nur auf
  ihre zugeordneten Fälle. Ein Kürzel verändert diese Rechte niemals.
- Erkennung gleichzeitiger Änderungen über Versionsprüfung; ein veralteter
  Schreibversuch wird mit Konfliktmeldung abgewiesen.
- API-Datenbankrolle ohne Schema-/Migrationsrechte und ohne Änderungs-/Löschrecht
  auf dem Audit-Protokoll. Migrations- und Bootstrap-Zugänge sind getrennt.
- Ressourcenanzeige im Einstellungsbereich und deutliche Kennzeichnung fehlender Cloud-Funktionen.
- Originalnaher TRIAGE//BOX-Start-/Fallablauf mit Cloud-Katalog je Fall; Details
  und aktuelle UI-Abnahme unter [UI-Vergleich](ui-triagebox-comparison.md).

Die Providerabstraktion für Identitäten ist von der Fallautorisierung getrennt.
Gerätemodell A und zentrale Anmeldung C sind weiterhin Architekturvarianten,
keine aktivierten Anmeldemöglichkeiten. Vor dem produktiven Benutzerkonzept
ist die im Architekturpapier dargestellte Entscheidung erforderlich.

## Tatsächliche Abnahme

**11 Infrastrukturtests und 15 PostgreSQL-Integrationstests bestanden.**
Integrationstests laufen ausschließlich in `fca_test_phase1` mit eigenen
synthetischen Benutzern; ein Namensguard verhindert Tests gegen `fca`.
Die Testdatenbank wird nach dem Test entfernt.

Geprüft wurden sichere Sitzungs-Cookies und Hashspeicherung, fehlende Anmeldung,
fremder Origin, CSRF, fehlerhafte Anmeldung und Rate-Limit, Fallanlage,
Duplikatbehandlung, Falltrennung beim Lesen/Ändern/Audit, Rechtevergabe und
Rechteentzug, parallele Benutzer, konkurrierende Änderungen, Logout,
Sitzungsablauf, Benutzerdeaktivierung und Passwortwechsel. API-DB-Rechte wurden
praktisch gegen unerlaubte Schema-/Auditänderungen geprüft. Passwörter erscheinen
nicht in Validierungsantworten; führende/nachgestellte Leerzeichen bleiben Teil
des Passworts.

Zusätzlich direkt über **reales HTTPS auf der VM**: Zertifikatskette und
IP-Adresse, Admin-Anmeldung, synthetische Fallanlage, Änderung/Audit,
Datendiskerkennung, API-Neustart mit fortbestehender Sitzung und Fall sowie
Abmeldung geprüft. Ein weiterer VM-Neustart bestätigte automatisch gestartete
API/DB/nginx, erhaltenen Fall, Datenvolume und erneute Anmeldung. Die ursprüngliche
Phase-0-Datenbank-/Restore-/Datei-Abnahme wurde danach erneut erfolgreich geprüft.

Vom Entwicklungsrechner sind HTTPS-Seite, CSS, JavaScript und API-Healthcheck
mit explizit vertrauter Labor-CA erfolgreich abrufbar. Ports 80, 5432 und 8000
sind aus dem LAN nicht erreichbar. API-Port 8000 ist ausschließlich an Loopback
der VM gebunden; die DB veröffentlicht keinen Port. Docker-interne DB-Verbindung
und getrenntes API-Webnetz sind vorgesehen, damit der lokale Reverse-Proxy die
API erreicht. Die Firewall bleibt zusätzlich aktiv.

Die Anmeldeseite wurde in einer lokalen reinen Layoutvorschau bei Desktopbreite
und 390 px visuell geprüft. **Dies war kein angemeldeter Browser-End-to-End-Test
über das echte HTTPS-Ziel.** Die echten HTTPS-Aktionen wurden automatisiert
ausgeführt. Ein normaler Browser benötigt zuvor Vertrauen zur Labor-CA.

Ein eindeutig als synthetisch bezeichneter, archivierter Abnahmefall bleibt als
technischer Nachweis im Labor. Keine echten Fälle oder Cloud-Daten verwendet.

## Ressourcen mit laufender Anwendung

Momentaufnahme am 21.10.2026, 17:18 Uhr Europe/Vienna nach HTTPS-Abnahme:

| Größe | Beobachtung |
|---|---:|
| Gast-RAM gesamt | 1,93 GiB nutzbar bei 2 GiB VM-Zuweisung |
| Gast-RAM verfügbar | 1,47 GiB |
| API-Container | 42,34 MiB / Limit 384 MiB |
| PostgreSQL-Container | 79,38 MiB / Limit 512 MiB |
| Systemdateisystem belegt / verfügbar | 2,51 / 27,47 GiB |
| Testdatendisk belegt / verfügbar | ca. 258 MiB / 30,61 GiB |

Auf dem Proxmox-Host waren anschließend etwa 1,68 GiB RAM verfügbar;
der gemeinsame Thin-Pool hatte 95,72 GiB physisch frei (42,28 GiB belegt).
Die bestehenden Gastkonfigurationen und die Host-Boot-ID blieben auch nach
der Phase-1-Abnahme unverändert.

Das ist keine Spitzenlastmessung und kein Cloud-Durchsatztest. Builds, Logins,
Providerbibliotheken, Dateimanifeste und parallele Downloads erzeugen zusätzliche
Last. Vor größeren Sicherungen bleiben Ein-Worker-Start, Disk-/Thin-Pool-Reserve
und tatsächlicher Providerlasttest verbindlich. Siehe Phase-0-Abschlussbericht.

## Noch nicht implementiert

Provider-Authentifizierung, Sicherungsaufträge, Queue/Worker,
Cloud-Dateimanifeste und Cloud-Berichte folgen in den Phasen 2–4. Es gibt keine
simulierten Cloud-Erfolge oder erfundenen Downloadfortschritte. LDAP/AD/OIDC,
produktives Secret-Management, unabhängiges verschlüsseltes Backupziel und
Produktionsabnahme sind weiterhin offen. Die Datendisk ist im synthetischen
Labor nicht mit LUKS verschlüsselt; keine Freigabe für echte Beweisdaten.
