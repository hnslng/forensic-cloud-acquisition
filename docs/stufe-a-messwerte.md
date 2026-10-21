# Stufe A – Messwerte und Grenzen

Stand: 21.10.2026. Keine Echtkonto-Anmeldung und kein Lasttest auf der VM.

## Lokaler synthetischer Vergleich

Rclone 1.75.2 auf macOS ARM64, lokaler HTTP-Server; künstlich 2 ms Wartezeit je 64 KiB. Pro Pool 18 Dateien mit insgesamt 41.094.144 Byte. Zwei getrennte Prozesse modellieren zwei Konten, ohne echte Cloud-Konten oder FCA-Warteschlange. Je Einstellung zwei Wiederholungen; kurze Läufe erlauben keine belastbare Langzeitprognose.

| Pools | Transfers je Pool | Gesamtdurchsatz Median (MiB/s) | Bereich (MiB/s) | Max. gemessener RSS (MiB) | CPU-Zeit Median (s) |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 19.02 | 19.00–19.03 | 55.6 | 0.274 |
| 1 | 2 | 31.25 | 31.02–31.48 | 56.0 | 0.218 |
| 1 | 4 | 49.43 | 49.41–49.45 | 56.3 | 0.152 |
| 1 | 8 | 87.44 | 86.95–87.94 | 55.7 | 0.118 |
| 2 | 1 | 37.67 | 37.49–37.86 | 109.8 | 0.456 |
| 2 | 2 | 75.04 | 70.36–79.72 | 111.5 | 0.273 |
| 2 | 4 | 104.88 | 90.20–119.57 | 110.4 | 0.233 |
| 2 | 8 | 161.57 | 145.04–178.11 | 112.1 | 0.208 |

Durchsatz ist die Summe aller Pools, einschließlich Prozessanlauf. RSS wird etwa alle 100 ms abgetastet und kann Spitzen verpassen; er umfasst die Rclone-Prozesse, nicht den Python-Testserver. CPU-Zeit ist die gemessene Kindprozesszeit einschließlich Hilfsabfragen, keine VM-Auslastung. `max_http_gets` enthält auch Verzeichnis-/Metadatenabfragen und ist kein Zähler ausschließlich aktiver Dateidownloads. Die 8er-Konfiguration ist nur ein lokaler Vergleich und keine Empfehlung für die kleine VM.

Alle 17 Übertragungsläufe endeten mit vollständig verglichenen SHA-256-Werten und identischer Finaldateiliste. Der zusätzliche Fehlerlauf behandelte eine HTTP-429-Antwort und einen TCP-Abbruch; er beweist nicht, dass das anbieterspezifische Retry-After-Pacing korrekt ist. Ein separater Prozessabbruch mit erneutem Kopierlauf erhielt sieben bereits fertige Dateien unverändert; danach waren alle 18 Dateien geprüft und keine temporären Reste vorhanden. Dies ersetzt keinen PostgreSQL-/VM-Neustarttest.

Die beiden OAuth-Abläufe wurden nur mit lokalen simulierten Endpunkten ausgeführt. Falscher State und Portkonflikt wurden nachgewiesen. FCA-Zuordnungs-, Ablauf-, Replay- und Verschlüsselungsprüfungen bestanden. 11 bestehende Infrastrukturtests bestanden lokal. Zwei Befundprüfungen bestätigen ausdrücklich noch bestehende Fehler: pauschale 403-Wiederholung und fehlender OneDrive-Quellhashvergleich.

[Maschinenlesbare Ergebnisse samt Prüfskript- und Rclone-Archivhash](test-results/stufe-a-synthetic.json). Reproduktion und Grenzen: [technischer Bericht](stufe-a-technik.md#5-reproduzierbare-testmethode).

## FCA-Test-VM – ausschließlich lesende Momentaufnahme

Zeitpunkt: 21.10.2026, 21:06:37 UTC / 23:06:37 Europe/Vienna. Debian 13, zwei vCPU, ca. 2 GiB RAM, keine Swapdatei.

| Messgröße | Momentaufnahme |
|---|---:|
| RAM verfügbar | 1,34 GiB |
| Sicherungsdatenträger frei | 30,73 GiB |
| Abzüglich bestehender 2-GiB-Reserve nutzbar | 28,73 GiB |
| Systemdatenträger frei | 6,50 GiB |
| Container-RAM API / Worker / PostgreSQL | 49,87 / 30,99 / 83,24 MiB |
| Container-Limit API / Worker / PostgreSQL | 384 / 512 / 512 MiB |
| Momentane Container-CPU API / Worker / PostgreSQL | 46,14 / 1,03 / 0,94 % |

Der CPU-Schnappschuss während der Abfragen ist kein Leerlaufmittel oder Download-Lastprofil. Bestehende Einstellung: vier Dateien je Konto, zwei aktive Konten. Unverändert belassen.

Ein bestehender iCloud-Drive-Lauf ist pausiert; das Inventar ist offen. 260 Dateiobjekte: 49 abgeschlossen, eines fehlgeschlagen und 210 in der Warteschlange. Über abgeschlossene Dateien summiert: **142.874.467 Byte**. Der Auftragszähler meldet **352.360.291 Byte einschließlich Teilübertragungen**; diese Werte dürfen nicht gleichgesetzt werden. Der Pausehinweis nennt knappen Arbeitsspeicher. Das ist ein früherer Zustand und kein Beleg für derzeitigen Speichermangel oder einen in Stufe A ausgeführten Lasttest.

**Realistische Cloud-Geschwindigkeit auf dieser VM ist noch nicht gemessen.** Dafür braucht es nach Freigabe eine kontrollierte Testreihe auf der VM mit synthetischem Cloud-Bestand, längerem Lauf, beiden Konten, CPU/RAM-/Speicherverlauf sowie echten Providerlimits. Vier Transfers und zwei Konten bleiben bis dahin bestehen. Stufe A hat keine Dateien, Konfigurationen oder Datenbankzustände auf der VM verändert.
