# Test- und Nachweisstand

## Nachweistypen

- Reale Lesetests: bestehender SSH-Zugang zu Proxmox, Proxmox-Abfragen,
  GitHub-SSH-Identität und private Repository-Sichtbarkeit.
- Automatisierte synthetische Tests: Ressourcenreserven, belegte VM-ID,
  unvollständige Inventare, SSH-Alias-Validierung. Diese Tests booten keine VM.
- CI-Infrastrukturtest: Compose-Start, PostgreSQL-Migration und Ablehnung eines
  zweiten Bootstrap-Laufs auf einem wegwerfbaren GitHub-Runner.
- Noch offen: alle realen FCA-VM-Tests aus `installation.md`, Last-/Neustarttests
  der späteren Anwendung sowie sämtliche echten Cloud-Integrationen.

## Lokale Ausführung

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_vm_plan.py .local/proxmox-inventory.json infrastructure/proxmox/lab-plan.json
```

Ergebnisse am 21.10.2026: **11/11 lokale Tests bestanden**. Die zehn
festgelegten Leseabfragen des Inventarlesers waren nach Korrektur der
Storage-Content-Abfrage vollständig erfolgreich. Das geprüfte Rohinventar
liegt lokal in `.local/proxmox-inventory-verified.json` (14:36 UTC / 16:36 CEST).
Die Ressourcenprüfung für 2 vCPU, 2 GiB RAM und 32 + 32 GiB Disks bestand
einschließlich 1,5 GiB RAM- und 24 GiB Storage-Reserve. Sie ist eine
Momentaufnahme und weder Ressourcenreservierung noch VM-Freigabe.
Docker ist auf dem lokalen Entwicklungsrechner nicht im verfügbaren Pfad;
es wird für diese Vorbereitung kein bestehender lokaler Containerdienst verändert.
Ein erfolgreicher CI-Lauf ist separat vom noch offenen VM-Nachweis zu benennen.

Der erste [GitHub-Actions-Lauf](https://github.com/hnslng/forensic-cloud-acquisition/actions/runs/39618375109)
bestand am 21.10.2026: lokale Tests auf dem Runner, Compose-Validierung,
realer PostgreSQL-Containerstart, Bootstrap-Migration und erwartete Ablehnung
einer wiederholten Bootstrap-Migration. Laufzeit 31 Sekunden. Die dabei
angezeigte Node-20-Abkündigung wurde durch Umstellung auf den festgeschriebenen
aktuellen Checkout-v6-Stand behoben. Dieser CI-Test erfolgte auf einem
GitHub-Runner und weist weder die FCA-VM noch eine Cloud-Integration nach.

## Spätere Abdeckung

Phasen 1–6 ergänzen Fälle und Fallrechte, mehrere gleiche Providerkonten,
Umbenennung ohne Pfadwechsel, parallele Worker, Browser-/Netzverlust,
Worker-/Serverneustart, Fortsetzen, fehlerhafte und abgelaufene Anmeldung,
Speichererschöpfung, Hash- und Manifestprüfung, mehrere Benutzer und Restore.
Nur synthetische Daten automatisiert verwenden; echte Providerzugriffe mit
freigegebenen Testkonten separat praktisch prüfen und protokollieren.
