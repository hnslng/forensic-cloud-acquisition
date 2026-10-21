# Vergleich vor dem Umbau: TRIAGE//BOX und FCA

Untersuchung am 21.10.2026, vor Änderungen am FCA-Frontend.

Referenz: `hnslng/forensic-triage`, `main` erneut abgefragt, Commit
`df307e9877721d4d61c85cc9193bb02d3dcdeb86` (Release alpha 82).
FCA-Ausgangsstand: `b3353b651b4b418cfced0a15caee238e83ff42cf`.
Das TRIAGE-Repository wurde nur gelesen; keine Referenzdatei verändert.

## Konkrete Unterschiede

| Bereich | Tatsächliche TRIAGE//BOX | FCA vor Umbau | Umsetzung für FCA |
|---|---|---|---|
| Einstieg | `startOverlay`: abgedunkelter Hintergrund, 7,5-px-Blur, mittige Wortmarke/BEREIT/Fallaktion | Alleinstehende Login-Karte ohne sichtbares Arbeitsdashboard | Entsprechender Start-Overlay mit „Fall anlegen“ über dem leeren, nicht bedienbaren Dashboard |
| Hauptaufbau | Schmale `masthead`, aktiver Fall rechts, helle `rulebar`, `case-dock`, Medienpanel | Große Kopfzeile, linke Seitennavigation, Kennzahlen, Falltabelle und Detailpanel | Gleiche Hierarchie wie TRIAGE; Cloud-Panel anstelle des Medienpanels, keine dauernde Seitenleiste |
| Fallanlage | `auftragModal.showModal()`, gegliederte Fall-/Sitzungsbereiche, eigene Startaktion | Neues Fallformular erzeugt Fall, danach Rückkehr zur Fallübersicht | Modal mit Geschäftszahl, Fallbezeichnung und Kürzel; „Fall starten“ führt direkt in den neuen Arbeitsbereich |
| Bestehende Fälle | Separates Fallarchiv aus der Fallanlage erreichbar | Falltabelle ist permanent im Vordergrund | Archiv als nachgeordnetes Modal, bestehende Fall-IDs und Rechte bleiben gültig |
| Arbeitsobjekte | Kompakte Medienkarten innerhalb des aktiven Falls | Noch kein fachlicher Arbeitsbereich | Cloud-Karten je Fall mit Anbieter, freier Bezeichnung und ehrlich deaktiviertem Anbindungs-/Sicherungsstatus |
| Dialoge | Native `<dialog>`, dünne grüne Rahmen, kompakte `modal-head`, Blur-Backdrop; verschachtelte Dialoge ohne gestapelte Abdunklung | Native Dialoge, aber unabhängige große Formularkarten | TRIAGE-Kopfzeile, Größen, Abstände, Fußaktionen und konsistente verschachtelte Dialoge |
| Einstellungen | Zahnrad in Statusleiste und Start-Overlay; eigenes Modal mit Reitern | Benutzerverwaltung, Passwort und Abmeldung ständig in Seitenleiste; Fallrechte im Arbeitsbereich | Separater Einstellungsdialog für Sitzung, Benutzer, Fallrechte und Technik |
| Stil | Monospace, Arial Black/Impact-Wortmarke, `#0b0d0a`/`#121610`, Akzent `#c9f252`, eckige Panels, dezente Scanlines | Ähnliche Farben, aber eigenständige Typografie, Kennzahlen und Anordnung | Konkrete TRIAGE-Tokens, Wortmarkenproportionen, Panel-/Dialogaufbau und kompakte Bedienflächen übernehmen |

Geprüfte Referenzstellen: `web/index.html` (Kopf/Overlay/Falldock ab Zeile 12,
`auftragModal` ab 255, Einstellungen ab 375), `web/styles.css`
(`start-overlay`, `masthead`, `rulebar`, `case-dock`, `action-body`,
`case-session-footer`, Dialoge ab ca. 685) und `web/app.js`
(`updateStartOverlay`, `openAuftrag`, Fallstart und verschachtelte Dialoge).

## Sicherheitsgrenze und bewusste fachliche Anpassungen

TRIAGE verwendet eine gemeinsame Gerätesitzung; diese ist keine Anmeldung.
FCA behält persönliche Anmeldung, sichere Cookies, CSRF/Origin-Prüfung,
serverseitige Fallrechte und Audit. Der Startbildschirm kann vor der Anmeldung
erscheinen, enthält dann aber keine vertraulichen Falldaten. Ein Fallstart
erfordert weiterhin eine gültige Arbeitssitzung. Die Anmeldung wird bei Bedarf
aus dem Fallmodal geöffnet; eingegebene Falldaten bleiben dabei erhalten.

Der ausgewählte Arbeitsfall bleibt browserbezogen, niemals global für alle
Benutzer. Das Verlassen des Arbeitsbereichs löscht oder archiviert keinen Fall.
Neue Cloud-Konten sind zunächst ausschließlich persistente Verwaltungsobjekte:
keine Providerzugriffe, keine Passwortabfragen, keine simulierten Downloads.
Mehrere Konten desselben Anbieters sind erlaubt, technische Identität über UUID.

Die Cloud-Verwaltung benötigt eine ausschließlich additive Migration für eine
neue Tabelle. Bestehende Tabellen, Konten, Fälle und Protokolle werden nicht
zurückgesetzt. Vor Bereitstellung wird ein geschütztes Datenbank-Backup erzeugt
und anschließend der Erhalt sämtlicher vorhandener Zeilen überprüft.

## Abnahmeplan

- Browser: Start-Overlay, Fallmodal, erforderliche Anmeldung, direkter Fallstart.
- Browser: drei Anbieter, zwei gleiche Anbieter, freie Bezeichnungen, Umbenennen,
  Neuöffnen eines bestehenden Falls und dauerhaft deaktivierte Provideraktionen.
- Browser: Einstellungen getrennt vom Arbeitsbereich, Escape/verschachtelte
  Dialoge, Formularfehler, schmale Bildschirmbreite und DOM-Datenbereinigung.
- PostgreSQL: Persistenz, Konten-/Falltrennung, Viewer-/Fremdfall-Verweigerung,
  CSRF, stabile IDs, Audit und unveränderte bisherige Sicherheitsregressionen.

## Umsetzung und Browserabnahme

Die beschriebenen Änderungen sind als Version 0.3.0 umgesetzt. Native Dialoge,
Originalfarben/-abstände, Wortmarkenproportionen, Start-Overlay und Falldock
wurden anhand des tatsächlichen Quellstands übernommen und an Cloud-Karten
angepasst. Anmeldung und persönliche Fallrechte bleiben Voraussetzung.

11 Infrastruktur-, 17 PostgreSQL- und 4 echte Chromium-Browsertests bestanden.
Die Browserabnahme verwendet echte API/DB mit ausschließlich synthetischen
Konten in `fca_test_phase1`. Desktop 1440 × 1000 und Mobil 390 × 844 wurden
visuell geprüft; Bildschirmnachweise liegen außerhalb von Git auf der VM.
Ein angemeldeter Browser-Test gegen das reale HTTPS-Laborziel wird dadurch
nicht behauptet; hierfür muss der Laborbrowser der eigenen CA vertrauen.

Vor der additiven Migration wurde ein geschütztes vollständiges Datenbank-
Backup angelegt und erfolgreich in einer separaten Wegwerf-Datenbank
wiederhergestellt. Zeilenprüfsummen sämtlicher vorhandener öffentlicher
Datentabellen dienen der Kontrolle des unveränderten Bestands bei Bereitstellung.
