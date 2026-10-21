# Test- und Nachweisstand

Stand 21.10.2026: **45 Prüfungen bestanden: 11 Infrastruktur-, 21 API-/PostgreSQL-, 5 Chromium-Browser- und 8 rclone-Offline-Vertragstests.**

Aktuelle [Phase-2-Abnahme und klare Trennung synthetischer/echter Nachweise](phase-2-icloud.md).

```sh
python3 -m unittest discover -s tests -p test_infrastructure.py -v
```

Die Anwendungstests werden auf der VM oder einem isolierten CI-Runner über
`scripts/run_phase1_tests.sh` ausgeführt. Sie erstellen ausschließlich
`fca_test_phase1`, verwenden synthetische Daten und entfernen die Testdatenbank.
Getrennte Compose-Testcontainer enthalten festgeschriebene API- und Browser-
Abhängigkeiten. Die bisherigen Browserprüfungen umfassen den vollständigen Ablauf mit
nativer Dialogverschachtelung, erhaltenen Feldern bei Anmeldung, direktem
Fallstart, vier Cloud-Konten (zweimal iCloud), Umbenennung/Persistenz nach
Neuladen, deaktivierten Anbieteraktionen, separaten Admin-Einstellungen,
Logout-Datenbereinigung, Viewer-Sperren und Tastaturbedienung bei 390 px.
Sie sprechen die unveränderte echte API über Chromium auf vertrauenswürdigem
Loopback im Testcontainer an; keine API-Mocks und keine Arbeitsdaten.

- [Phase-0-Abnahme, Restore und Ressourcen](phase-0-completion.md)
- [Phase-1-Tests, HTTPS, Rechte und Neustart](phase-1-status.md)
- [GitHub Actions](https://github.com/hnslng/forensic-cloud-acquisition/actions)

Die GitHub-Pipeline prüft Infrastruktur, Migrationen, isolierte API- und Browsertests
und den tatsächlichen Loopback-Zugriff auf die bereitgestellte API. Ein Erfolg
auf GitHub ersetzt keine reale VM-Abnahme; diese wurde gesondert durchgeführt.

Die reale HTTPS-Abnahme lief mit explizit vertrauter Labor-CA, ohne Ausschalten
der Zertifikatsprüfung. Die Anmeldeseite wurde zusätzlich in einer statischen
Layoutvorschau auf Desktop- und Mobilbreite geprüft. Die neue Oberfläche wird
zusätzlich automatisiert mit echtem Chromium und PostgreSQL geprüft. Ein angemeldeter Browser-
End-to-End-Test gegen das echte HTTPS-Ziel steht bis zur gezielten Einrichtung
des CA-Vertrauens im Laborbrowser aus.

Noch offen sind sämtliche echten Cloud-Integrationen sowie die in Phase 6
vorgesehenen Download-, Wiederanlauf-, Speichererschöpfungs- und Provider-
Sitzungstests. Simulierte oder lokale Tests werden nicht als realer Cloud-Test
gewertet. Keine Freigabe für echte Beweisdaten.
