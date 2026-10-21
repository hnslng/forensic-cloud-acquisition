# Frontend

Deutsche HTML/CSS/JS-Oberfläche nach dem tatsächlichen TRIAGE//BOX-alpha-82-
Bedienkonzept: Start-Overlay, Fallmodal, unmittelbarer Fallstart, nachgeordnetes
Fallarchiv und Cloud-Karten. Der konkrete Vorhervergleich und die übernommenen
Layoutstellen stehen in `docs/ui-triagebox-comparison.md`.

Sitzung, Benutzer, Fallrechte und Technik liegen im eigenen Einstellungsmodal.
Mehrere Cloud-Konten desselben Anbieters sind möglich; Anmeldung und Sicherung
bleiben ausdrücklich deaktiviert. Persönliche Anmeldung und API-Fallrechte sind
unverändert erforderlich. Benutzerdaten werden als Textknoten gerendert; keine
Tokens im Local Storage. Ein aktiver Fall wird nicht global zwischen Benutzern
geteilt und beim Neuladen nicht automatisch geöffnet.
