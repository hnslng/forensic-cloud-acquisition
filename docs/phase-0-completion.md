# Phase 0 – erfolgreich abgeschlossen

21.10.2026, Abnahme ca. 16:54 Uhr Europe/Vienna. Freigabe durch den Auftraggeber
für VM 105 liegt vor. VM 103 wurde zuvor vom Auftraggeber entfernt; FCA hat
keine bestehenden Gäste gelöscht oder verändert.

## Installierter Stand

- VM 105 `forensic-cloud-acquisition`, Debian 13.7 amd64, 2 vCPU, 2048 MiB RAM.
- Portables CPU-Modell `x86-64-v2-AES`, VirtIO-SCSI, QEMU Guest Agent.
- Zwei getrennte virtuelle Disks mit je 32 GiB und eindeutigen Seriennummern
  `FCA105SYSTEM` und `FCA105EVIDENCE`. Systemdisk wurde erfolgreich erweitert.
- Testdaten als ext4 unter `/srv/fca/evidence`, UUID-basiert und mit
  `nodev,nosuid,noexec` eingehängt. Nur diese zuvor leere Disk wurde formatiert.
- Bridge `vmbr0`, DHCP, Autostart nach vorhandenen Diensten konfiguriert.
  Aktuelle LAN-Adresse lokal dokumentiert; DHCP ist keine feste Adresszusage.
- Cloud-Init über eigenes NoCloud-ISO ohne Änderung der Host-Storage-Konfiguration.
  Nach Erstinstallation ISO aus dem virtuellen Laufwerk entfernt; Gastneustart
  anschließend erfolgreich. Bootreihenfolge nach Geräteänderungen geprüft.
- Administrator `fcaadmin` mit vorhandenem autorisiertem SSH-Schlüssel und sudo.
  Root-Login, Passwort- und Keyboard-Interactive-Anmeldung deaktiviert.
- Docker Engine 29.9.2, Compose 5.6.1, PostgreSQL 17.11.
- Chrony synchronisiert, persistentes Journal mit Größenlimit, Firewall für
  SSH und später HTTPS nur aus privatem LAN. Keine öffentlichen Portfreigaben.
- Konfiguration `/etc/fca`, Geheimnisse `/etc/fca/secrets` (Passwortdatei 0600),
  PostgreSQL-Daten `/var/lib/fca/postgres`, Quellstand `/opt/fca`.

## Image-Herkunft und Integrität

Offizielles Debian-Image, festgelegter Build `20261017-2634`:
https://cloud.debian.org/images/cloud/trixie/20261017-2634/debian-13-genericcloud-amd64-20261017-2634.qcow2

Über geprüftes HTTPS bezogen. SHA-512-Vergleich mit Debians `SHA512SUMS`
erfolgreich. Eine zusätzliche unabhängige Signatur wurde nicht angeboten und
wird nicht als geprüft behauptet.

```text
SHA-256: 87211f082e2983a1c2209a2626f9f6762073a92c6a63a8ce321608ca496c3b02
SHA-512: ec584ccabfef7120b4c4f7482adf0e615894d9292cedec446b64194b951ebe5dd97c336b5dcbae458333764b0edd516334506017f33c4f2020ef8d38b569ffe3
```

Das PostgreSQL-Image ist im Compose-Stand auf einen konkreten SHA-256-Digest
festgeschrieben. Persönliche private SSH-Schlüssel wurden nicht auf die VM
kopiert. Das Repository bleibt privat.

## Praktische Abnahme

| Prüfung | Ergebnis |
|---|---|
| Erneute Host-Ressourcenprüfung vor Erstellung | Bestanden einschließlich RAM-/Storage-Reserve; erste grenznahe Momentaufnahme erneut geprüft |
| Debian-Boot, DHCP, DNS, ausgehendes HTTPS | Bestanden |
| Verifizierter SSH-Hostschlüssel und sudo | Bestanden |
| Root-/Passwortanmeldung verweigert | Bestanden |
| Fremdnetz-Zugriff auf SSH über IPv4 und IPv6 | In getrenntem temporärem Gast-Netznamespace verworfen; Namespace danach entfernt |
| Docker `hello-world`, Compose, DB-Healthcheck | Bestanden |
| Bootstrap-Migration | Erfolgreich angewandt; bereits vorhandene Migration wird nicht überschrieben |
| PostgreSQL-Persistenz | 1.000 synthetische Datensätze über VM-Neustart erhalten |
| Backup und Restore | Custom-Format-Dump in getrennte Datenbank eingespielt, 1.000 Datensätze und Inhaltsprüfsumme identisch |
| Restore-Datenbank nach Neustart | Weiterhin identisch |
| Separate Testdatendisk | 256 MiB Zufalls-Testdaten geschrieben, SHA-256 vor/nach Neustart identisch |
| VM-Neustart | Boot-ID geändert, SSH/Agent/Docker/Chrony/Firewall/Datenbank/Mount verfügbar |
| Persistentes Journal | Vorheriger und aktueller Boot nachgewiesen |
| Bestehende Systeme | Hashes der Host-Storage-/Netzwerk- und Gastkonfigurationen 100/101/102/104 unverändert |
| Host-Neustart | Keiner; Host-Boot-ID identisch |

Die Tests fanden auf der realen VM mit ausschließlich synthetischen Daten
statt. Sie belegen keine Cloud-Integration und keine Produktionsfreigabe.
Die öffentliche Debian-Webseite war zeitweise langsam erreichbar; der
wiederholbare HTTPS-Test verwendet das erreichbare Debian-Paketarchiv mit
begrenzten Zeitlimits. Die Abnahmeskripte sperren konkurrierende Testläufe.

## RAM und Speicher

Momentaufnahmen, kein Lasttest echter Cloud-Downloads:

| Messpunkt | Verfügbarer Gast-RAM | PostgreSQL-Container |
|---|---:|---:|
| Grundinstallation ohne PostgreSQL | ca. 1,65 GiB | – |
| Nach DB-/Restore-/256-MiB-Dateitest | 1,48 GiB | ca. 42 MiB |
| Nach VM-Neustart | 1,55 GiB | ca. 63 MiB |

Nach Neustart: Systemdateisystem rund 2,07 GiB belegt, 27,91 GiB verfügbar;
Testdateisystem rund 258 MiB belegt, 30,61 GiB verfügbar. Die Differenz zur
virtuellen Größe entsteht durch Dateisystem- und Reservierungsbedarf.
Die VM besitzt keinen Swap; Docker-Datenbanklimit 512 MiB.

Der gemeinsame Proxmox-Thin-Pool besitzt viele bestehende Snapshots und ist
virtuell überbucht. Proxmox meldet fehlende automatische Thin-Pool-Erweiterung.
Diese Host-Einstellungen wurden nicht geändert. Physische Pool-Auslastung und
Gast-Dateisysteme müssen unabhängig überwacht werden; freier Gastplatz allein
genügt nicht. Alte Snapshots werden von FCA nicht gelöscht.

Für die ersten kleinen Testaufträge zunächst **ein Worker**. Ein voller
32-GiB-Export passt wegen Dateisystem, Metadaten und Reserve nicht auf die
32-GiB-Datendisk. Vor größeren Downloads müssen geschätzter Umfang, freier
Datendiskplatz, physischer Thin-Pool und RAM unter tatsächlicher Providerlast
geprüft werden. Diese Phase liefert noch keine belastbare Parallelitäts- oder
Durchsatzfreigabe. Ein Backup auf derselben VM ist nur eine Restoreprobe;
ein unabhängiges verschlüsseltes Backupziel ist vor realem Einsatz erforderlich.

## Übergang zu Phase 1

Die Voraussetzungen für Phase 1 sind erfüllt. HTTPS, sicherer Basiszugang,
getrennte Identitäts-/Berechtigungslogik und Fallverwaltung werden als nächstes
implementiert. Noch keine Cloud-Anmeldungen oder echten Sicherungen.
