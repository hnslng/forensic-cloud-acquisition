Die Infrastruktur liegt in `compose.yaml`: PostgreSQL intern, API im Profil
`application` mit Loopback-Port 8000. Der HTTPS-Proxy ist ein Debian-nginx-Dienst
auf der privaten VM. `bootstrap-debian.sh` ist die geprüfte einmalige
Gast-Grundeinrichtung; sie verweigert erneutes Formatieren bestehender Daten.
`configure-https.sh` richtet die Labor-CA und den privaten Proxy ein.
Das Dockerfile trennt Runtime und isolierte Tests. Worker folgen in Phase 3.
