# Versionierte FCA-Installationspakete

## Empfehlung für Behörden

FCA als **signiertes, versioniertes Offlinepaket** ausliefern: geprüfte
Containerimages, Frontend, Migrationen, Verwaltungswerkzeuge und vollständiger
Debian-Abhängigkeitssatz. Installation benötigt weder Git noch persönliche
GitHub-Schlüssel. Das Paket kann von einer zentralen Administrationsstelle aus
einem privaten GitHub Release bezogen, geprüft und intern verteilt werden.
Alternativ bietet sich später eine interne Paket-/OCI-Ablage an. Ein natives
`.deb` kann künftig diesen geprüften Paketinhalt kapseln; es ist für den
jetzigen reproduzierbaren Installationsweg nicht erforderlich.

Auf Behördenservern niemals automatisch `main`, ein bewegliches Tag oder
`latest` beziehen. GitHub Release dient als Transport, nicht als Vertrauensanker.
Die Behörde hinterlegt einen unabhängig geprüften Ed25519-Public-Key; jede
konkrete Version wird anhand ihrer Signatur und SHA-256 geprüft. Das Aktualisieren
des vertrauenswürdigen Schlüssels ist ein eigener administrativer Vorgang.

## Releaseprozess

1. Konkreten Commit mit vollständiger Backend-/Browser-/Installer-CI prüfen.
2. Auf sauberem Debian-13-amd64-Builder den festgelegten Abhängigkeitssatz
   herunterladen. `scripts/collect_install_dependencies.py --output <Ordner>`
   löst direkte, versionsgebundene Pakete über signiertes Debian-APT auf und
   sammelt deren fehlende transitive Abhängigkeiten. Dies geschieht **nur beim
   Releasebau**, niemals auf einem Behördenserver. Das Ausgangsimage muss dem
   dokumentierten frischen Testimage entsprechen. Sicherheitsaktualisierungen
   der Lockdatei erfordern erneute Abnahme; keine unsignierten APT-Quellen.
3. Runtimeimage aus dem geprüften Commit bauen. Basisimages sind auf Digests
   fixiert. Die Python-Versionslocks sind vorhanden; deren Einzelartefakte sind
   noch nicht als unabhängiger Wheel-Hashlock hinterlegt. Deshalb wird beim
   Betreiber **nicht** erneut aus diesen Quellen gebaut: getestet und signiert
   wird das fertige Image mit seiner unveränderlichen Inhalts-ID. Für einen
   gehärteten zentralen Buildprozess zusätzlich Wheel-Hashes/SBOM einführen.
4. Mit dem getrennt verwahrten Freigabeschlüssel signieren:

```sh
python3 scripts/build_install_package.py \
  --version 0.6.0 \
  --app-image sha256:VOLLSTAENDIGE_GEPRUEFTE_IMAGE_ID \
  --debs /geschuetzter-builder/debs \
  --output /geschuetzter-builder/fca-0.6.0 \
  --signing-key /freigabestelle/release-signing.key \
  --trusted-key /freigabestelle/release.pub
```

5. Das **genau signierte Paket** in einer neuen Debian-VM installieren, wiederholt
   installieren, aktualisieren und restaurieren. Quellen, Compiler-/Image-IDs,
   Manifest und Testergebnisse zur Version archivieren.
6. Freigabe erteilen und Paket als versioniertes GitHub Release / internes Paket
   verteilen. Private Releasezugriffe erfolgen zentral beim Administrator;
   keine persönlichen GitHub-Zugänge auf Behördenserver kopieren.

`manifest.json` erfasst Version, Quellcommit, Architektur, Datenbankschema,
Image-IDs, Debian-Paketversionen und Größe/SHA-256 jeder Datei.
`manifest.sig` ist die Ed25519-Signatur über die exakten Manifestbytes.
Kein produktiver Freigabeschlüssel wurde erzeugt oder auf GitHub hinterlegt.
Die CI-Testschlüssel gelten ausdrücklich nicht als Behördenfreigabe.

Erstverteilung der ausführbaren Installationswerkzeuge: Paket/Archiv als Ganzes
über eine unabhängig vertrauenswürdige Prüfumgebung bestätigen, bevor darin
enthaltener Code mit root-Rechten gestartet wird. Die interne Manifestprüfung
schützt Updates und Nutzdaten, ersetzt aber diese anfängliche Vertrauensbildung
nicht. Für produktive Releases einen extern signierten Archivhash mitliefern.

## Bewusste Grenzen der ersten Paketversion

Nur Debian 13 amd64, private IPv4-Listener, vorhandenes Python 3/iproute2/systemd,
vorhandenes administrativ freigegebenes HTTPS. Kein automatischer Betrieb einer
CA, kein DNS-/WireGuard-/Firewallmanagement, keine automatische Übernahme des
historischen Laboraufbaus und keine automatischen Schema-Downgrades.
