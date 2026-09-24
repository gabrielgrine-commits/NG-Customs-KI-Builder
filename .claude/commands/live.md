---
description: Kunden-Agenten nach Zusage des Kunden live schalten (Demo-Modus aus) inkl. Übergabe-Mail
argument-hint: <kunden-slug> [neue Infos vom Kunden, z. B. Antworten auf die offenen Fragen]
---

Schalte die Agenten von `kunden/$ARGUMENTS` live (erstes Wort = Slug, Rest = neue Infos).

1. **Neue Infos einarbeiten:** Hat der Nutzer Antworten/Unterlagen des Kunden mitgegeben →
   Subagent `agent-entwickler` trägt sie ein (Wissensbasis, Prompts, Arbeitszeiten, Kontakte).
2. **Checkliste** – alles prüfen, erst dann weiter:
   - `python3 scripts/validate_config.py kunden/<slug>` → keine Fehler, **keine `[OFFEN]`-Punkte**
     in Wissensbasis/Firmendaten (Preise, Datenschutz-URL, Kontakt).
   - `04-compliance.md` ohne 🔴 (sonst `compliance-pruefer` erneut, nachdem Punkte erledigt sind).
   - Tests: `python3 scripts/run_tests.py kunden/<slug>` (falls API-Key vorhanden) → alle bestanden.
   - E-Mail-Kanal genutzt? Dann müssen Postfach-Zugangsdaten auf dem Server gesetzt sein (Namen der
     Variablen aus `email.benutzer_env`/`passwort_env`) – den Nutzer danach fragen, nicht raten.
   Fehlt etwas: eine kurze Liste „Das fehlt noch“ mit konkreten Fragen an den Kunden ausgeben und
   **nicht** live schalten.
3. **Live schalten:** In `config.json` `"demo": false` setzen. Freigabepflicht für ausgehende E-Mails
   bleibt (Testphase 2 Wochen, laut Preisliste).
4. **Übergabe-Mail** `kunden/<slug>/08-uebergabe.md` an den Betrieb: Cockpit-Link (aus
   `python3 -m runtime zugang kunden/<slug>`) mit Erklärung „Hier geben Sie E-Mails frei, sehen Leads
   und Termine“, Einbau-Code für die Website (bzw. Angebot, ihn selbst einzubauen), Kalender-Abo-Link,
   ggf. Rufumleitung auf die Telefon-Nummer, Ansprechpartner bei NG Customs.
   Hinweis: Der Cockpit-Link ist wie ein Schlüssel – nicht weiterleiten.
5. Committen („Live: <Firma>“) und pushen.
6. Abschluss: 3 Zeilen – was jetzt live ist, Übergabe-Mail-Pfad, was der Kunde noch tun muss
   (z. B. Einbau-Code, Rufumleitung).
