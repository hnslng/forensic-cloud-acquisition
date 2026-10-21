# Verbindliches FCA-Design – Abnahme

21.10.2026. Frontendstand 0.4.0. Die freigegebene dunkelblaue Vorlage ersetzt die
frühere visuelle TRIAGE//BOX-Gestaltung; deren Fall-/Modalablauf bleibt erhalten.
Nach dieser Abnahme erfolgen keine eigenständigen weiteren Designänderungen.

## Umsetzung

| Element | Festgelegter Wert / Verhalten |
|---|---|
| Seite | `#101A2A` |
| Cloud-Karten | `#19283C` |
| Symbolflächen | `#263B55` |
| Rahmen | `#304B69` |
| Primärfarbe / aktiver Fortschritt | `#60A5FA` |
| Heller / sekundärer Text | `#F1F6FF` / `#91A4BE` |
| Erfolg / Warnung / Fehler | `#47B881` / Orange / Rot |
| Schrift | Systemschrift; Monospace ausschließlich für technische Kennungen und Protokolle |
| Fall | Aktive Übersicht oben, Fallsteuerung und eigene Einstellungen erhalten |
| Konten | Genau eine horizontale Karte je Zeile, stets volle verfügbare Breite |
| Karte | Symbol, Kontobezeichnung und Anbieter links; Verbindungsstatus rechts; Sicherungsinformation, breite Fortschrittsspur, Messwerte und Aktionen innerhalb der Karte |
| Nicht verbundene Konten | „Nicht verbunden“, nächster Schritt Authentifizierung; Anbieteranmeldung und Sicherung noch deaktiviert |
| Unbekannter Fortschritt | Leere Spur ohne Prozent, ohne gefüllten Balken und ohne vorgetäuschte Bytes/Geschwindigkeit/Restzeit |
| Separater Auftragsbereich | Vollständig entfernt |

Die Laboroberfläche enthält keine synthetischen Downloadwerte. Fotos-/Drive-
Untertitel benennen Anbieterbereiche, keine bereits implementierten Fähigkeiten.
Erfolgsfarben und Fortschrittsfüllung sind vorbereitet, werden aber erst durch
spätere echte Auftragsdaten aktiviert. Derzeit wird keine Sicherung behauptet.

## Praktische Abnahme

17 API-/PostgreSQL-Integrationstests, vier echte Chromium-Browserabläufe und
elf Infrastrukturtests bestanden. Browser nutzen die echte API und ausschließlich
`fca_test_phase1` mit synthetischen Benutzern und Fällen; keine API-Mocks.

- Desktop: 1920 × 1080 und 1440 × 900, zusätzlich 1280 × 900.
- Mobil: 390 × 844; kein horizontaler Seitenüberlauf.
- Alle Konten exakt so breit wie ihre Liste und vertikal untereinander.
- Exakte Hintergrund-/Kartenfarbe, keine fingierten Fortschrittswerte.
- Fallanlage, Anmeldung mit erhaltenen Feldern, unmittelbarer Fallstart.
- Vier Konten einschließlich zweier iCloud-Konten, Umbenennung und Persistenz.
- Benutzer tatsächlich angelegt; Viewer-Recht erteilt und wieder entzogen.
- Lesezugriff, Schreibsperren, getrennte Einstellungen und Logout-Bereinigung.
- Desktop-/Mobilaufnahmen und Dialoge visuell geprüft; Bilder nur mit Testdaten.

Die geprüften drei Frontenddateien wurden auf VM 105 bereitgestellt. Reales
privates HTTPS mit ausdrücklich vertrauter Labor-CA und Datei-SHA-256 stimmen
mit diesem Quellstand überein; API-Healthcheck erfolgreich. Die API blieb dabei
unverändert in Betrieb; keine Migration und kein API-/VM-/Host-Neustart.

## Bestandsschutz

Vorheriges vollständiges DB-Backup und Zeilenprüfsummen wurden rootgeschützt
unter `/var/backups/fca/ui-final-blue` abgelegt, ebenso das vorherige Frontend
und Testprotokoll. Nach Bereitstellung sind sämtliche zuvor vorhandenen Zeilen
in `users`, `cases`, `case_members`, `cloud_accounts`, `sessions`, `login_limits`,
`audit_events` und `phase0_probe` unverändert vorhanden. Keine bestehenden
Berechtigungen, Kennwörter, Kontozuordnungen oder Audit-Einträge wurden geändert.

Bildschirmnachweise liegen auf der VM unter `/var/lib/fca/validation/browser`
und lokal außerhalb von Git unter `.local/final-ui-validation`.

Der finale Designstand ist im [GitHub-Testlauf 8](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39643334427) erfolgreich geprüft. Funktionale Erweiterungen für iCloud-Anmeldung und Bereichsübersicht sind getrennt unter [Phase 2](phase-2-icloud.md) dokumentiert; Farben und Kartenlayout bleiben unverändert.
