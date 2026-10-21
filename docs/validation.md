# Test- und Nachweisstand

Stand 21.10.2026: **11 Infrastrukturtests und 15 PostgreSQL-Integrationstests bestanden**.

```sh
python3 -m unittest discover -s tests -p test_infrastructure.py -v
```

Die Anwendungstests werden auf der VM oder einem isolierten CI-Runner über
`scripts/run_phase1_tests.sh` ausgeführt. Sie erstellen ausschließlich
`fca_test_phase1`, verwenden synthetische Daten und entfernen die Testdatenbank.
Der Compose-Testcontainer enthält die festgeschriebenen Testabhängigkeiten.

- [Phase-0-Abnahme, Restore und Ressourcen](phase-0-completion.md)
- [Phase-1-Tests, HTTPS, Rechte und Neustart](phase-1-status.md)
- [GitHub Actions](https://github.com/hnslng/forensic-cloud-acquisition/actions)

Die GitHub-Pipeline prüft Infrastruktur, Migrationen, isolierte Anwendungstests
und den tatsächlichen Loopback-Zugriff auf die bereitgestellte API. Ein Erfolg
auf GitHub ersetzt keine reale VM-Abnahme; diese wurde gesondert durchgeführt.

Die reale HTTPS-Abnahme lief mit explizit vertrauter Labor-CA, ohne Ausschalten
der Zertifikatsprüfung. Die Anmeldeseite wurde zusätzlich in einer statischen
Layoutvorschau auf Desktop- und Mobilbreite geprüft. Ein angemeldeter Browser-
End-to-End-Test gegen das echte HTTPS-Ziel steht bis zur gezielten Einrichtung
des CA-Vertrauens im Laborbrowser aus.

Noch offen sind sämtliche echten Cloud-Integrationen sowie die in Phase 6
vorgesehenen Download-, Wiederanlauf-, Speichererschöpfungs- und Provider-
Sitzungstests. Simulierte oder lokale Tests werden nicht als realer Cloud-Test
gewertet. Keine Freigabe für echte Beweisdaten.
