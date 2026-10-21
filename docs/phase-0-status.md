# Phase 0 – Prüfstand und Freigabevorschlag

Stand: 21.10.2026, Europe/Vienna. **Zwischenbericht, kein Phasenabschluss.**
Der Projektordner war anfangs leer. Aktive Zugriffsdokumente unter
`~/.infra_work/README.md` und `ZUGRIFFE-AKTIV.md` wurden gelesen; der dort
ausgewiesene SSH-Alias `proxmox` wurde erfolgreich verwendet. Keine
Zugangsdaten werden in diesem Repository gespeichert.

## AP0.1 – Lesende Bestandsaufnahme

| Bereich | Feststellung |
|---|---|
| Proxmox | pve-manager 9.2.11, Kernel 7.0.14-12-pve, ein Node `pve` |
| CPU | Intel i5-4258U, 2 physische Kerne, 4 Threads |
| RAM | 7,66 GiB physisch; ca. 3,9 GiB verfügbar bei Erhebung |
| Swap | 7,66 GiB, bei Erhebung unbenutzt; kein Ersatz für RAM |
| `local` | Verzeichnis-Storage, ca. 45,4 GiB verfügbar |
| `local-lvm` | 138 GiB Thin-Pool, ca. 40,2 GiB belegt und 97,8 GiB physisch frei |
| Netzwerk | Aktive Bridge `vmbr0`, privates LAN; kein separates FCA-VLAN geprüft |
| Nächste freie ID | 105, durch Clusterabfrage und Konfigurationspfade geprüft |
| Vorhandene Images | Debian 13.6 netinst; Debian-13-LXC-Template; kein Debian-Cloud-VM-Template |
| Backups | Keine Jobs in `/cluster/backup`; dies schließt externe Backups nicht aus |
| Neustarts | Aktiver nächtlicher Host-Neustart ca. 04:30 Uhr mit Zufallsverzögerung |

Vorhandene Gäste:

| ID | Typ | Dienst | Zustand | RAM-Zuweisung |
|---|---|---|---|---|
| 100 | VM | Home Assistant | läuft | 2 GiB |
| 101 | LXC | AdGuard | läuft | 512 MiB |
| 102 | LXC | Uptime Kuma | läuft | 512 MiB |
| 103 | VM | forensic-triage | gestoppt | 2 GiB |
| 104 | LXC | HA Proxy | läuft | 256 MiB |

Es wurden weder Gäste gestartet/gestoppt noch Konfigurationen, Timer,
Snapshots oder Storage-Pools geändert. Die TRIAGE-VM bleibt unberührt.
Rohdaten einschließlich Netzwerkdetails liegen ausschließlich lokal unter
`.local/` und werden nicht committed.

## AP0.2 – Konkreter Vorschlag zur Freigabe

| Einstellung | Vorschlag |
|---|---|
| VM-ID / Name | 105 / `forensic-cloud-acquisition` |
| Betriebssystem | Aktuelles offizielles Debian 13 Stable, amd64 Generic Cloud |
| CPU | 2 vCPU; portables CPU-Modell statt Host-Passthrough |
| RAM | 2048 MiB fest; zunächst kleiner Testbetrieb |
| Systemdisk | 32 GiB auf `local-lvm` |
| Testdatendisk | Separate 32-GiB-Disk auf `local-lvm`, Mount `/srv/fca/evidence` |
| Geräte | VirtIO-Netzwerk, VirtIO-SCSI, QEMU Guest Agent, serielle Konsole |
| Netzwerk | `vmbr0`, DHCP; tatsächliche Adresse nach Boot ermitteln |
| Autostart | Ja, nach vorhandenen Diensten |
| Zugriff | SSH-Schlüssel; HTTPS später nur aus privatem LAN |
| Parallelität | Zunächst ein Worker; spätere Erhöhung nur nach Lasttest |

Die ursprünglich vorgeschlagenen 4 vCPU / 8 GB RAM sind auf diesem Host
nicht sinnvoll. Auch 80 GiB Systemdisk plus Datendisk würden den gemeinsamen
Storage unnötig einengen. Für den Vorschlag werden mindestens 1,5 GiB aktuell
verfügbarer RAM und 24 GiB physischer Thin-Pool-Speicher als Reserve gefordert.
Die Prüfung reserviert diese Ressourcen nicht. Vor Erstellung erneut prüfen.
Bestehende Snapshots können zusätzlich wachsen. Das gleichzeitige Starten der
gestoppten VM 103 erfordert eine neue Speicherbewertung. Für große Exporte ist
ein größerer Host bzw. zusätzlicher Datenspeicher erforderlich.

Die separate virtuelle Datendisk ist kein separates physisches Ausfallmedium
und kein Backup. Speicherverschlüsselung samt Entsperrung nach Neustart ist
vor echten Beweisdaten verbindlich zu entscheiden und zu testen.

**Freigabe ausstehend:** neue VM samt beiden Disks erzeugen, starten, Debian
und Grundlagen installieren sowie ausschließlich diese neue VM für die Abnahme
neu starten. Keine Änderung vorhandener Gäste, kein Host-Neustart, keine
öffentliche Portfreigabe.

## AP0.4 / AP0.5 – Repository und Struktur

`hnslng/forensic-cloud-acquisition` wurde über die bestehende GitHub-Sitzung
privat erstellt. SSH authentifiziert erfolgreich als `hnslng`. Es wurden keine
neuen GitHub-Tokens oder SSH-Schlüssel angelegt. Die verlangte modulare Struktur
ist angelegt; noch nicht entwickelte Module sind ausdrücklich so gekennzeichnet.

## AP0.6 – Verbleibende Abnahme

- [x] Proxmox-Zugriff, Ressourcen, Gäste, Storage und Bridge lesend geprüft.
- [x] GitHub-Repository privat angelegt und SSH-Zugriff geprüft.
- [x] Lokale Struktur, Dokumentation, Tests und CI-Konfiguration vorbereitet.
- [x] 11 lokale Tests und erste Compose-/PostgreSQL-CI-Abnahme bestanden.
- [ ] VM-Erstellung freigegeben und durchgeführt.
- [ ] Debian-Boot, DHCP/DNS, SSH, Zeitsynchronisierung geprüft.
- [ ] Firewall und private Erreichbarkeit einschließlich IPv6 geprüft.
- [ ] Docker Engine / Compose installiert und praktisch getestet.
- [ ] PostgreSQL-Persistenz, Migration, Backup und Restore getestet.
- [ ] Neue VM neu gestartet; Mounts und Dienste wieder verfügbar.
- [ ] Bestehende Dienste nachher unverändert verfügbar.
- [ ] Abschlussbericht erstellt; erst dann Phase 1 beginnen.
