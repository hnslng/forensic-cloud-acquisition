# Stufe B – Validierung und Ressourcen

> Historischer Entwicklungs-/Prüfbericht. Die nachfolgende Domain- und Google-Einrichtung sowie der aktuelle Anbieterstatus stehen im [Betriebsstand vom 22.10.2026](betriebsstand-2026-10-22.md).

Stand: 22.10.2026 (Europe/Vienna). Entwicklungsstand mit kontrollierter Bereitstellung der geprüften Codeversion b8ac146 auf der Labor-VM. Keine echte Google-/Microsoft-Anmeldung.

## Automatisierte Prüfung

| Prüfung | Ergebnis |
|---|---|
| PostgreSQL-/Backend einschließlich OAuth, Queue, Hashes und Migration 0009 | 73 Tests erfolgreich |
| Chromium: vorhandene Bedienabläufe und je zwei Google-/Microsoft-Konten | 10 Tests erfolgreich |
| Zusätzliche Rückkehr nach tatsächlich geladener fremder simulierten Anbieterseite | 2 Tests erfolgreich |
| Pause-/Speichergrund und Berichtsbilanz einschließlich bekannter Inventar-/Fehlergrößen | 4 Tests erfolgreich |
| Gepinnter Rclone/iCloud offline, ohne Netzwerk | 10 Tests erfolgreich |
| Infrastruktur/Speicherkapazität | 11 Tests erfolgreich |
| Neues Testimage mit gepinnten Abhängigkeiten | Build erfolgreich; 31 Offline-Tests im neu gebauten Image erfolgreich |
| GitHub CI | [b8ac146 erfolgreich, Run 39685332126](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39685332126); weitere Prüfungen siehe [PR #1](https://github.com/hnslng/forensic-cloud-acquisition/pull/1/checks) |

Ein früherer CI-Lauf zeigte einen unvollständig isolierten Testaufbau; dieser wurde korrigiert. Der oben verlinkte Lauf ist erfolgreich. Tests auf der VM verwenden ausschließlich getrennte Container und die wegwerfbare Datenbank `fca_test_phase1`. Bestehende Rollen werden genutzt; keine Produktionsdaten als Testfixture. Migrationen 1–9 werden in der Testdatenbank angewendet. Migration 0009 ändert nur Grenzwertbedingungen und behält bestehende Einstellwerte. Vier Transfers und zwei Konten gelten weiter.

Rclone-Konfiguration, Unix-Authentifizierung, tatsächliche lokale Kopien, parallele Konten, Quellhashfehler und Erhalt erneuerter Tokens wurden mit echten Rclone-Prozessen geprüft. Google-ID-/OneDrive-Pfadabfragen nutzen simulierte Providerantworten; kein tatsächlicher Google-API-/Microsoft-Refresh-/Downloaddienst wurde verwendet. Gleichnamige Google-Dateien werden über ID adressiert. QuickXor wurde zusätzlich gegen 70 Vektoren der gepinnten Rclone-Referenz abgeglichen.

Der vorbereitete Nginx-Plan wurde mit dem vorhandenen Nginx und ausschließlich lesend verwendeten Laborzertifikatdateien syntaktisch geprüft. Kein Reload, kein neues Zertifikat, keine DNS-Anfrage/-Änderung. Ein nicht zugewiesenes Beispiel-IP-Listen konnte auf der VM erwartungsgemäß nicht gebunden werden; Syntaxprüfung erfolgte deshalb mit deren bestehender privater Adresse. Domainvertrauen und Providerakzeptanz bleiben Echtkonto-Abnahme.

## iCloud-Befund – bestehender Lauf unverändert

Auftraggeber weist auf eine möglicherweise selbst ausgelöste Pause hin. Gespeichert ist der alte Text „Arbeitsspeicher knapp. Sicherung pausiert.“. Die Pause entstand um 22:03 Uhr Ortszeit vor dem letzten Start der API-/Worker-Container um 22:17 Uhr. Deren gegenwärtige Peaks erklären den damaligen Zustand deshalb nicht rückwirkend. Die beim Laufstart gespeicherten Werte waren ca. 1,34 GiB verfügbarer Host-RAM und 147 MiB Containerbelegung bei 512 MiB Limit; Werte direkt zum Pauseauslöser fehlen. Ursache daher **nicht abschließend belegt**, keine automatische Wiederaufnahme.

Momentaufnahme 21.10.2026 23:28 Uhr: kein OOM-Kill, keine Container-Neustarts seit deren aktueller Erstellung; Worker ca. 34,3 MiB cgroup-Belegung, Peak 59,5 MiB. API-Limit 384 MiB, Worker/PostgreSQL jeweils 512 MiB; Host ohne Swap, ca. 1,34 GiB verfügbar. Sicherungsdatenträger 30,73 GiB frei (28,73 GiB nach Reserve), Systemdatenträger 6,50 GiB frei. Kein Beleg für aktuell erschöpften RAM.

Keine ungebremste Dateieinlesung im Downloadpfad gefunden; Streaming, begrenzte Pools und serverseitiger Manifest-Cursor bestehen. Rclone-RC-Jobs und Statistiken können Ressourcen behalten; Statistikgruppen wurden begrenzt und Transferpuffer ausdrücklich auf 256 KiB gesetzt. Pagecache wird im Speicherschutz bereits abgezogen. Speichermangel-Pausen erfassen künftig ihre Auslösewerte. Benutzerpausen bekommen einen eindeutigen eigenen Grund. Der historische Lauf wurde dafür nicht bearbeitet.

Ein Speicherleck ist durch Codeprüfung und drei Minuten synthetischen Betrieb weder nachgewiesen noch sicher ausgeschlossen. Ein langer echter Lauf mit großem Inventar bleibt erforderlich und wird erst nach gesonderter Freigabe begonnen.

## Synthetische Vergleichsmessung auf der VM

Isolierter Container: 512 MiB, eine CPU, kein Netzwerk, zwei lokale Rclone-Sitzungen; künstliche Obergrenze 8 MiB/s je Sitzung, 1-MiB-Dateien, Streaming ohne lokale Schnellkopie. Temporäre Testdaten auf separatem tmpfs, SHA-256 für jede Kopie. Die Standardmatrix umfasst je einen 15-Sekunden-Lauf; keine statistische Langzeitprognose. Werte betreffen Testprozess und Rclone, nicht PostgreSQL/API oder echte Cloud.

| Kontositzungen | Dateien je Sitzung | Gesamtdurchsatz MiB/s | Peak RAM MiB | CPU-Anteil eines Kerns |
|---:|---:|---:|---:|---:|
| 1 | 1 | 2.07 | 47.07 | 4.0 % |
| 1 | 2 | 4.59 | 51.50 | 8.7 % |
| 1 | 4 | 7.44 | 57.56 | 14.4 % |
| 2 | 1 | 3.96 | 73.31 | 8.0 % |
| 2 | 2 | 7.33 | 77.91 | 13.5 % |
| 2 | 4 | 13.27 | 86.95 | 23.5 % |

**180-Sekunden-Lauf mit 2 × 4:** 2.496 Dateien / 2.496 MiB übertragen und per SHA-256 geprüft, 13,87 MiB/s unter der künstlichen Begrenzung, 107,64 MiB Peak, etwa 23,5 % eines CPU-Kerns, keine OOM-Ereignisse. Speicher nach 30/60/90/120/150/180 Sekunden: 86,1 / 91,1 / 97,7 / 98,1 / 98,4 / 99,6 MiB. Das frühe Wachstum flacht ab; dies ist kein Nachweis dauerhafter Leckfreiheit. Die Messung belastet den lokalen Streamingpfad und tmpfs, **nicht** Netzwerkbandbreite, Providerdrosselung oder den echten Sicherungsdatenträger.

Ein zusätzlicher 60-Sekunden-Versuch prüfte 840 Dateien, Peak 100,95 MiB. Die allgemeinen Backendtests erreichten im beobachteten Abschnitt 183,94 MiB ohne OOM; mindestens 1.153,5 MiB Host-RAM waren dort verfügbar. CPU- und cgroup-Messwerte sind in [maschinenlesbaren Nachweisen](test-results/stufe-b-validation.json) zusammengefasst. Reproduktion: `scripts/measure_synthetic_worker.py`, nur im separaten Testcontainer mit begrenztem tmpfs verwenden.

Keine Aussage über tatsächliche Google-/OneDrive-/iCloud-MB/s. HTTP-429/Retry-After und TCP-Abbruch werden synthetisch geprüft; anbieterspezifisches echtes Pacing, WAN-Unterbrechungen und mehrstündige Laufzeit bleiben offen. Keine Änderung der Laborparallelität aus diesen Messungen.

## Ressourcenempfehlung – Planung, keine gemessene Kapazitätszusage

| Einsatz | Knappe Untergrenze | Empfehlung |
|---|---|---|
| Kleines Labor, ein kleiner Auftrag | 2 vCPU / 2 GiB RAM | 2 vCPU / 4 GiB RAM |
| Zwei aktive Konten mit 4 Dateien je Konto | 2 vCPU / 4 GiB RAM | 4 vCPU / 8 GiB RAM |
| Mehrere Ermittler, zunächst höchstens zwei aktive Konten | 4 vCPU / 8 GiB RAM | 8 vCPU / 16 GiB RAM |
| Behördenserver, mehrere größere Aufträge | 8 vCPU / 16 GiB als Startprofil | 8–16 vCPU / 32 GiB RAM; anschließend nach Lastprofil dimensionieren |

Diese Werte sind vorsichtige Planungsgrößen aus Komponenten, Limits und Sicherheitsreserve. Ermittlerzahl allein bestimmt die Last nicht; entscheidend sind aktive Konten, Inventargröße und Übertragungsplätze. Die aktuelle 2-GiB-VM reicht für die bisherigen begrenzten synthetischen Versuche, ist aber keine langfristig verlässlich dimensionierte Mehrkonto-Umgebung. Keine VM-Ressourcen geändert. Vor Erhöhung RAM, Containerlimits, CPU und Hostreserven gemeinsam prüfen.

Systemdisk für Labor mindestens 32 GiB, empfohlen 64 GiB wegen Images/Updates/Prüfartefakten. Sicherungsdisk nach autorisiertem Datenumfang zuzüglich temporärem Downloadbedarf und unabhängiger Backups dimensionieren; die bisherige 32-GiB-Testdisk ist nur für kleine Bestände geeignet. Technische 2-GiB-Reserve ersetzt keine Kapazitätsplanung. SSD empfohlen; echte Lese-/Schreiblast noch nicht gemessen.

## Datenerhalt, Restore und Freigabe

Neue Sicherung vor Tests unter einem privaten rootgeschützten Backupverzeichnis: PostgreSQL-Dump, vollständiges Sicherungsverzeichnis und externe Zugangskonfiguration. Wiederherstellung in getrennte Prüfdatenbank: alle 16 Tabellen identisch. Nach den Tests erneut verglichen: Originaldatenbank vollständig identisch; Archivvergleich der Sicherungsdaten und Zugangskonfiguration identisch. Bestehender Lauf unverändert pausiert, 260 Objekte / 49 abgeschlossen / eines fehlgeschlagen / 210 wartend.

Die laufenden Laborcontainer wurden nach erfolgreicher CI kontrolliert auf den geprüften Code b8ac146 und Schema 9 umgestellt. Erneutes vollständiges Backup und Restore aller 16 Tabellen vor der Übernahme erfolgreich. Danach 15 bestehende Fachtabellen identisch; nur Schema-Migrationsstand ergänzt. Sicherungsdaten und Zugangskonfigurationen entsprechen weiterhin ihren Archiven. API/Worker gesund, Startseite/App/OAuth-Rückkehrskript über bestehendes privates HTTPS mit geprüftem Zertifikat erreichbar. Weitere Codekorrekturen erhalten vor Übernahme einen eigenen grünen CI-Nachweis im PR. Keine echten Anmeldungen, DNS-/Zertifikatsänderungen oder Wiederaufnahme des iCloud-Laufs. Für Google sind konkrete Domain und externe App-Einrichtung später separat freizugeben.
