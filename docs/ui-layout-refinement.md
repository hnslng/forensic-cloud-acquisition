# FCA – Lesbarkeit und Desktopproportionen

Gezielte Layoutüberarbeitung nach dem ersten TRIAGE//BOX-Umbau. Fallanlage,
Anmeldung, Fallwechsel, Rechte, Kontoverwaltung und sämtliche API-Aufrufe bleiben
erhalten. Backend, Datenbankschema und gespeicherte Daten werden nicht verändert.

| Bereich | Anpassung |
|---|---|
| Schrift | Klare Monospace-Schrift mit explizitem Liberation-Mono-Fallback; Grundschrift und Eingaben 16 px, Kontoüberschriften 20 px, Aktionen 14 px, Status mindestens 13 px |
| Kontrast | Hellere sekundäre Schrift; deaktivierte Aktionen bleiben lesbar und sind zusätzlich durch gestrichelte Rahmen erkennbar |
| Bildschirmbreite | Arbeitsbereich bis 1840 statt 1480 px, auf Desktop 24 px seitlicher Abstand |
| Cloud-Karten | Mindestbreite 360 statt 255 px, flexible Spalten, 16 px Zwischenraum; keine künstliche feste Kachelhöhe |
| Fallleiste | Kompakte neutrale Leiste mit zurückgenommenen Aktionen statt dominanter grüner Fläche |
| Anbieter | iCloud, Google und OneDrive mit Text, eigenem Kürzel und unterschiedlich gefärbter Kennzeichnung; Erkennung nicht allein über Farbe |
| Karteninhalt | Anbieter und Erfassungsstatus oben, freie Kontobezeichnung, Anbindungs-/Sicherungsstatus als eigene Gruppe, Aktionen unten |
| Aufträge | Eigener leerer Bereich „Sicherungsaufträge & Downloads“; keine simulierten Aufträge, Fortschritte oder neuen Funktionen |

Die dunklen Grün-/Schwarzflächen, helle Statusleiste, säuregrünen Hauptakzente,
eckigen Rahmen, Wortmarke und nativen Dialoge bewahren den TRIAGE//BOX-Charakter.
Anmeldung beim Anbieter und Sicherung bleiben ausdrücklich deaktiviert.

Die bestehenden echten Browserabläufe werden weiterverwendet und um
Desktopprüfungen bei 1280, 1440 und 1920 px sowie den mobilen Arbeitsbereich bei
390 px ergänzt. Geprüft werden insbesondere lesbare Aktionsschrift, breite,
maßvolle Karten, kompakte Fallleiste, der leere Auftragsbereich und fehlender
horizontaler Seitenüberlauf. Bildschirmnachweise enthalten nur synthetische Daten.

## Abnahme

17 API-/PostgreSQL-Integrationstests und alle vier bestehenden Chromium-
Bedienabläufe bestanden. Die zusätzlichen Layoutprüfungen bei 1280/1440/1920 px
und der mobile Arbeitsbereich bei 390 px sind erfolgreich. Karten, Fallleiste,
Dialoge, Anbietermarkierungen und der leere Auftragsbereich wurden zusätzlich
an den synthetischen Browseraufnahmen visuell geprüft.

Die Bereitstellung betrifft ausschließlich `index.html`, `styles.css` und die
Darstellung der Cloud-Karten in `app.js`. Keine Migration, kein API-/VM-Neustart
und keine Änderung bestehender Konten, Fallrechte oder Cloud-Datensätze nötig.
Die vorherigen ausgelieferten Frontend-Dateien werden außerhalb des Repositories
rootgeschützt gesichert. Die private HTTPS-Auslieferung wird mit explizit
vertrauter Labor-CA und Dateiprüfsummen gegen diesen Quellstand kontrolliert.
