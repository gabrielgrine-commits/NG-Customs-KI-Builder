# Marketing-Skills (übernommen aus coreyhaines31/marketingskills)

- **Quelle:** https://github.com/coreyhaines31/marketingskills, Stand Commit `5b2c000` (2026-09-04), Plugin-Version 2.11.1
- **Lizenz:** MIT, © 2025 Corey Haines – siehe `MARKETINGSKILLS-LICENSE`
- **Übernommen:** 49 Skills nach `.claude/skills/<name>/` (u. a. `copywriting`, `cro`, `seo-audit`, `ai-seo`,
  `schema`, `site-architecture`, `pricing`, `offers`, `lead-magnets`, `referrals`, `social`, `emails`,
  `prospecting`, `marketing-plan`, `product-marketing`) und die Tool-Dokumentation (nur Markdown) nach
  `.claude/tools/`, damit die Verweise `../../tools/…` in den Skills funktionieren.
- **Bewusst weggelassen:**
  - `cold-email` – Kalt-E-Mails sind bei uns verboten (UWG § 7 Abs. 2 Nr. 3, TKG 2021 § 174).
  - `evals/` in jedem Skill – Testdaten des Originalprojekts, zur Laufzeit nicht nötig.
  - `tools/clis/*.js` und alle anderen Skripte – keine fremden ausführbaren Dateien im Repo
    (siehe `SICHERHEITSHINWEIS.md`).
- **Geprüft vor der Übernahme:** nur Markdown/JSON/CSV/HTML; keine versteckten Zeichen, keine eingebetteten
  Anweisungen; das HTML-Template (`ad-creative/assets/`) rendert nur lokale JSON-Daten.
- **Grundlagen-Datei:** Die Skills lesen `.agents/product-marketing.md` (Positionierung, Zielgruppe, Preise
  von NG Customs). Aktualisieren mit dem Skill `product-marketing`.

## Vorrang unserer Regeln

Die Skills sind für den US-Markt und SaaS geschrieben. Bei Widersprüchen gilt `CLAUDE.md`:

- **Kaltakquise:** nie per E-Mail, SMS oder Messenger. In Österreich auch keine Werbeanrufe – nur
  persönlicher Besuch. Das betrifft vor allem `prospecting`, `sms`, `emails` und `sales-enablement`.
- **Recht:** DSGVO, UWG, TKG 2021 und ECG statt CAN-SPAM, TCPA oder CASL. E-Mail- und SMS-Werbung nur mit
  vorheriger Einwilligung (Double-Opt-in).
- **Nichts erfinden:** keine erfundenen Zahlen, Kundenstimmen oder Referenzen – Fehlendes als `[OFFEN: …]`.
- **Sprache:** Texte für Kunden auf Deutsch in der Sie-Form.

## Aktualisieren

Neue Version holen, wieder nur `skills/` (ohne `cold-email` und `evals/`) und `tools/**/*.md` kopieren,
vorher auf Skripte und eingebettete Anweisungen prüfen und den Commit oben nachtragen.
