# Google – aktueller FCA-Stand

Implementiert ist ein lesender REST-Adapter für „Meine Ablage“, unterstützte Workspace-Exporte und Google-Kalender. Die Webanmeldung verwendet den vorhandenen FCA-OAuth-Ablauf mit PKCE; Anbieterregistrierung und passende Rückkehradresse werden einmalig administriert. Der reguläre Ermittlerablauf enthält keine manuelle Tokenübertragung.

**Automatisiert getestet:** synthetische API-Antworten, Exporte, Seitenwechsel, sichere Ablage und Fall-/Benutzerbindung. **Echtkonto-Abnahme:** noch offen.

Die domainlose Desktop-/Loopback-Anmeldung und Rclone als Google-Dateiadapter wurden in [Stufe A](../../docs/stufe-a-machbarkeit.md) bewertet, sind aber **nicht in FCA integriert**. Für die gemeinsame Rclone-Google-Client-ID ist die angekündigte Einstellung 2026 zu berücksichtigen. Eine eigene App und deren Freigabestatus bleiben erforderlich; keine unverifizierte breite Einsatzfähigkeit behaupten.

[Unterstützter Umfang und Grenzen](../../docs/cloud-acquisition.md) · [Technische Stufe-A-Befunde](../../docs/stufe-a-technik.md).
