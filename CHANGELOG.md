# Änderungen

## 0.1.0 – 2026-10-21 – Phase 0 abgeschlossen

- Freigegebene VM 105 mit Debian 13.7, 2 vCPU, 2 GiB und zwei 32-GiB-Disks installiert.
- Docker/Compose, Chrony, private Firewall und eingeschränkten SSH-Zugang eingerichtet.
- Offizielles Debian-Image geprüft; PostgreSQL-Image auf Digest festgeschrieben.
- Reale VM-Neustart-, Persistenz-, SHA-256- und PostgreSQL-Restoretests bestanden.
- Ressourcenmessungen und unveränderte Host-/Bestandskonfiguration dokumentiert.

## 0.0.1 – 2026-10-21 – Phase 0 in Vorbereitung

- Privates, eigenständiges Repository eingerichtet.
- Proxmox ausschließlich lesend inventarisiert; bestehende Dienste unverändert.
- Ressourcenangepassten VM-Vorschlag und Abnahmekriterien dokumentiert.
- Aktuellen TRIAGE//BOX-Quellstand und Dokumentation untersucht.
- Wiederholbare SSH-Inventarisierung und konservative Ressourcenprüfung ergänzt.
- PostgreSQL-Compose-Grundlage ohne veröffentlichte Ports vorbereitet.
- Automatisierte Infrastrukturtests und GitHub-Actions-Workflow vorbereitet.
- VM-Erstellung, Installation und Laufzeittests stehen noch aus.
