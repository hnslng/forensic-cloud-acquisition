# Änderungen

## Signierter Online-Bootstrap – 0.6.0-rc.1 – 2026-10-22

- Feste signierte Releaseversion aus dem bestehenden GitHub-Repository, ohne GitHub-Anmeldung am Zielserver.
- Ein-Befehl-Start mit vorgelagerter Bootstrap-Prüfsumme, Archivsignatur und Integritätskontrolle.
- Geführte Einrichtung mit optionaler neuer Labor-CA und ausdrücklich bestätigtem leerem Laborordner; kein Partitionieren oder Formatieren.
- Unveränderter Offlineweg; getrennte Updates und Erhalt bestehender Daten.
- Veröffentlichung ohne privaten Signierschlüssel in CI; erfolgreiche zusätzliche frische VM-Abnahme über den tatsächlichen öffentlichen GitHub-Befehl.

## Installation und Update – Entwicklungszweig – 2026-10-22

- Interaktiver Debian-13-Paketinstaller und getrennte Updates; vorhandene Laborinstallation wird nicht übernommen.
- Signierte Offlinepakete mit SHA-256, festen Container-IDs und vollständigem Debian-Abhängigkeitssatz.
- Diagnose für Dateiintegrität, Dienste, Ressourcen, Berechtigungen, Datenträger und privates HTTPS.
- Konsistente Backups mit Restoreprobe und bestätigter Programmrollback ohne Zurückschreiben von Beweisdaten.
- Neue isolierte Debian-VM-Abnahme einschließlich unterbrochener Installation, Updatefehler, Datenerhalt und Neustart.
- Keine Bereitstellung oder Neuinstallation auf der bestehenden FCA-VM.

## Stufe B – Entwicklungszweig – 2026-10-22

- Vorhandenen OAuth-/PKCE-Ablauf zusätzlich an Sitzung, Anbieter, Client und Rückkehradresse gebunden.
- Google-/OneDrive-Dateitransport über isoliertes Rclone mit getrennten verschlüsselten Konfigurationen und Erhalt erneuerter Tokens; REST-Inventar und Kalender weiterverwendet.
- Google-ID-Download für gleichnamige Dateien; OneDrive-ID-, Versions- und verfügbare Quellhashprüfung.
- Berechtigungsfehler von API-Drosselung getrennt; genauere Umfangs- und Bytebilanz, eindeutige Benutzerpause und künftige Speicher-Auslösewerte.
- Migration 0009 für begrenzte Serverprofile; Laborstandard bleibt 4 Dateien / 2 Konten.
- Parametrisierter HTTPS-Prüfplan und Administrations-/Testanleitung, ohne DNS-/Zertifikatsänderungen.
- Synthetische PostgreSQL-, Browser-, Rclone- und Ressourcenprüfungen; bestehender Lauf und Beweisdaten erhalten.
- Geprüfte Codeversion b8ac146 nach erfolgreicher CI in die Laborcontainer übernommen; keine Echtkonto-Abnahme.

## Flachere Cloud-Karten – 2026-10-21

- Status und Pausengrund rechts im Kartenkopf; alle Mengen- und Fortschrittsangaben unter dem Balken.
- Weniger vertikale Abstände bei unveränderter Bildschirmbreite und unverändertem Sicherungsverhalten.

## Kompakte Sicherungsverwaltung – 2026-10-21

- Doppelte Mengen-/Prüfangaben entfernt, niedrigere Karten und weniger Aktionen während laufender Sicherung.
- MD5 als sichtbare Prüfsumme; SHA-256 bleibt im Nachweis erhalten. Additive Migration 0008.
- Gemeinsame iCloud-Auswahl für Drive und Fotos mit getrennten Datenordnern und gemeinsamem Downloadlimit.
- Freigebbarer Dateicache zählt nicht als belegter Anwendungsspeicher; sichere Wiederaufnahme nach Pausen und unerwartetem Taskende.

## Anbieterkennzeichnung – 2026-10-21

- Lokale Apple-, Google- und Microsoft-Logos in Cloud-Karten und Anbieterwahl.
- Eigene Anbieterakzente bei unveränderter dunkelblauer Oberfläche und unveränderten Statusfarben.

## Live-Downloads – 2026-10-21

- Echte iCloud-Zwischenstände während großer Dateiübertragungen und geglättete Gesamtgeschwindigkeit.
- Freie Downloadplätze werden fortlaufend nachbesetzt; Anzeige der belegten und konfigurierten Plätze sowie vorübergehender Drosselung.

## Laborbereinigung – 2026-10-21

- Historische Fallreferenzen bleiben unabhängig von der aktiven Fallverwaltung erhalten. Eine ausdrücklich angeforderte administrative Entfernung von Testfällen verändert bestehende Audit-Einträge nicht.

## Ergänzung – 2026-10-21 – Erfassung und Übertragung parallel

- Laufend aktualisierter Dateizähler und verständliche Unterscheidung zwischen Erfassung und Übertragung.
- Bereits erfasste Dateien werden während der weiteren Suche heruntergeladen. Gesamtfortschritt erst bei abgeschlossenem Inventar.
- Erfassungsfehler verhindern eine Erfolgsmeldung; Dienstneustarts erhalten Warteschlange und geprüfte Dateien.

## 0.5.0 – 2026-10-21 – Dauerhafte Cloud-Sicherungen

- Separater Worker mit PostgreSQL-Warteschlange; maximal zwei Konten und vier Dateien je Konto, konfigurierbar innerhalb der VM-Grenzen.
- Eigene Fall-/Konto-/Laufordner, temporäre Übertragung, atomare Übernahme ohne Überschreiben, SHA-256 und geschützte Berichte.
- Wiederaufnahme fertiger Dateien nach Prozessneustart; unfertige Dateien werden sicher neu übertragen.
- iCloud-Downloadadapter sowie offizielle OAuth-/REST-Adapter für Google Drive/Kalender und Microsoft OneDrive/Outlook-Kalender.
- Deutsches Bedienvokabular, echte Fortschritte und Sicherungsläufe innerhalb der freigegebenen Oberfläche.
- Synthetische Sicherheits-, Parallelitäts-, Abbruch-/Neustart- und Browserprüfungen; echte Anbieterabnahmen und App-Registrierungen bleiben ausdrücklich offen.

## Phase 2 – iCloud-Anmeldung vorbereitet

- iCloud-SRP-Anmeldung, 2FA und explizite Drive-/Fotos-Bereichsübersicht.
- Verschlüsselte Konfiguration je Fall/Konto, unabhängiger Hauptschlüssel.
- Serverrechte, CSRF, Anmeldebegrenzung und Audit ohne Zugangsdaten.
- Echte fixierte rclone-Laufzeit und isolierte Offline-Vertragstests.
- Freigegebenes finales Design beibehalten; keine fingierten Downloadwerte.
- Echte Testkonto-Abnahme steht bis zur persönlichen Anmeldung aus.


## 0.4.0 – 2026-10-21 – Verbindliches finales UI

- Freigegebene dunkelblaue Palette und Standardschrift umgesetzt.
- Genau eine volle horizontale Cloud-Karte pro Zeile auf allen Bildschirmbreiten.
- Integrierte Status-/Fortschritts-/Messwertbereiche; keine fingierten Sicherungen.
- Separaten Auftragsbereich entfernt; Fallablauf und Einstellungen erhalten.
- Desktop-/Mobilabnahme, Benutzeranlage und Fallrechte praktisch getestet.
- Vollständiges Backup und bestätigter Erhalt sämtlicher vorhandener Daten.


## 2026-10-21 – Layoutnachbesserung

- Größere, klarere Schrift und höherer Kontrast im bestehenden TRIAGE//BOX-Stil.
- Breiterer Desktoparbeitsbereich und großzügigere, klar gegliederte Cloud-Karten.
- Kompakte Fallleiste; Anbieter über Kürzel, Namen und Farbakzente unterscheidbar.
- Eigener leerer Bereich für spätere Sicherungsaufträge und Downloads.
- Fallablauf, Sicherheitsfunktionen, API und Datenbank unverändert.
- Bestehende Browserabnahme um Desktopproportionen und mobile Arbeitsansicht ergänzt.

## 0.3.0 – 2026-10-21 – TRIAGE//BOX-Bedienkonzept

- Tatsächliches TRIAGE//BOX alpha 82 vor dem Umbau mit FCA verglichen.
- Verschwommener Startbildschirm, Fallmodal, direkter Fallstart und Fallarchiv.
- Originalnahe Kopfzeile, Statusleiste, Falldock, Panels und verschachtelte Dialoge.
- Cloud-Katalog je Fall mit drei Anbietern, freien Namen, mehreren gleichartigen
  Konten und versionsgeprüfter Umbenennung; Anbieteraktionen bleiben deaktiviert.
- Benutzer, Rechte, Sitzung und Technik in separate Einstellungen verschoben.
- Ausschließlich additive Migration; Sicherheitsprüfungen bleiben erhalten.
- Browserabläufe gegen echte API und isolierte PostgreSQL-Datenbank ergänzt.

## 0.2.0 – 2026-10-21 – Phase 1

- Persönliche Anmeldung mit Argon2id, persistenten Sitzungen, CSRF und Rate-Limits.
- Fallverwaltung, persönliche Zuordnung, Fallrechte und API-seitig geschütztes Audit.
- Administrative Benutzerverwaltung und Erteilen/Entziehen einzelner Fallrechte.
- Versionskonflikte bei konkurrierenden Änderungen erkannt.
- Deutsches, responsives Frontend und privates HTTPS auf VM 105 bereitgestellt.
- Minimale API-DB-Rolle und getrennte Migrationen; Abhängigkeiten festgeschrieben.
- 15 echte PostgreSQL-Integrationstests, HTTPS- und weitere Neustartabnahme bestanden.
- Noch keine Cloud-Authentifizierung oder Sicherungsfunktion.

## 0.1.0 – 2026-10-21 – Phase 0 abgeschlossen

- Freigegebene VM 105 mit Debian 13.7, 2 vCPU, 2 GiB und zwei 32-GiB-Disks installiert.
- Docker/Compose, Chrony, private Firewall und eingeschränkten SSH-Zugang eingerichtet.
- Offizielles Debian-Image geprüft; PostgreSQL-Image auf Digest festgeschrieben.
- Reale VM-Neustart-, Persistenz-, SHA-256- und PostgreSQL-Restoretests bestanden.
- Ressourcenmessungen und unveränderte Host-/Bestandskonfiguration dokumentiert.

## 0.0.1 – 2026-10-21 – Phase 0 in Vorbereitung

- Privates, eigenständiges Repository eingerichtet.
- Proxmox ausschließlich lesend inventarisiert; bestehende Dienste unverändert.
- Ressourcenangepassten VM-Vorschlag und Abnahmekriterien dokumentiert.
- Aktuellen TRIAGE//BOX-Quellstand und Dokumentation untersucht.
- Wiederholbare SSH-Inventarisierung und konservative Ressourcenprüfung ergänzt.
- PostgreSQL-Compose-Grundlage ohne veröffentlichte Ports vorbereitet.
- Automatisierte Infrastrukturtests und GitHub-Actions-Workflow vorbereitet.
- VM-Erstellung, Installation und Laufzeittests stehen noch aus.
