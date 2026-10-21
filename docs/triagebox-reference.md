# TRIAGE//BOX – geprüfte Referenz

Am 21.10.2026 separat nach `~/.cache/fca-reference/forensic-triage` geklont.
Quelle: https://github.com/hnslng/forensic-triage

Untersuchter Commit: `df307e9877721d4d61c85cc9193bb02d3dcdeb86`
(06.10.2026, „Release alpha 82 dashboard polish“). Der lokale Quellstand ist
neuer als die beim Webabruf angezeigte README-Fassung mit Alpha 59. Einzelne
Dokumentationsabschnitte nennen ebenfalls ältere Alphas; entscheidend ist der
festgehaltene Commit. Das Originalprojekt und seine VM wurden nicht geändert.

| Thema / geprüfte Quellen | Übernahme für FCA |
|---|---|
| `web/styles.css`, `index.html`, `app.js` | Kompakte Panels, dunkles Grün, monospace, kräftige Wortmarke, eindeutiger Fallkontext, native Dialoge |
| CSS-Farben | Hintergrund `#0b0d0a`, Panel `#121610`, Text `#e8eadf`, Akzent `#c9f252`, Warnung `#ffb44a`, Fehler `#ff685f` als Gestaltungsreferenz |
| `casefiles.py`, `docs/case-archive.md`, Architektur | Verständliche Fallexporte und erfasster Bearbeiter; für FCA unveränderliche UUIDs und PostgreSQL statt geräteweiter Sitzung |
| `casefiles.py` Audit und Manifest | UTC-Ereignisse, JSON-Zeilen, Hashmanifeste; für große Cloud-Dateien blockweise Hashberechnung statt `read_bytes()` |
| `scan_process.py`, Web-Koordinator | Worker-Prozessisolation, separate Zeitlimits und klare Fehlerzustände; zusätzlich dauerhafte Queue und Wiederaufnahme erforderlich |
| Statusdarstellung | Zustand und Zähler sichtbar; bei unbekannter Gesamtmenge keine erfundenen Prozentwerte oder Restzeiten |
| `scripts/install_debian.sh`, `docs/installation.md` | Konfiguration außerhalb Git, Voraussetzungen prüfen, Tests vor Aktivierung, bestehende Daten erhalten |
| `docs/offline-updates.md`, Updatepfade | Vorbereitete Releases, signierte Manifeste, Integritätsprüfung und kontrollierter Wechsel; FCA benötigt zusätzlich DB-Migrations- und Restorekonzept |

Die in TRIAGE verwendete gemeinsame Gerätesitzung samt Kürzel ist ausdrücklich
keine Benutzeranmeldung. Prozesslokale Locks und Statusdaten reichen für
mehrere FCA-Benutzer und einen Serverneustart nicht aus. Ein Dateimanifest
allein ist weder Manipulationsschutz gegen Administratoren noch Nachweis einer
vollständigen Cloud-Sicherung. Datenbank-Audit, unabhängige Exporte und später
geeignete Signatur-/Archivierungsmaßnahmen sind getrennt zu behandeln.

Das Referenzprojekt besitzt eine restriktive Lizenznotiz. Hier wurden Konzepte
analysiert und neue Infrastrukturwerkzeuge erstellt; kein Quellmodul oder
Installer wurde in FCA kopiert. Betriebsspezifische Raspberry-Pi-, USB-,
Hotspot- und Root-Updater-Funktionen werden nicht übernommen.
