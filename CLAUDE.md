# NG Customs – KI-Agenten-Builder für KMUs

Dieses Repository ist die Werkstatt von **NG Customs**. NG Customs verkauft Websites und **autonome
KI-Agenten** an kleine und mittlere Unternehmen (KMU) im deutschsprachigen Raum. Hier wird für
jeden Kunden ein eigenes Agenten-Team geplant, gebaut, getestet, angeboten und betrieben.

Sprache im Projekt: **Deutsch** (Kundendokumente per „Sie“).

## Was ein Kunden-Agent hier ist

Kein reiner Chatbot, sondern ein Agent, der **selbstständig Arbeit erledigt**: Er wird durch
Chat, eingehende E-Mails, Webhooks (Formulare) oder einen Zeitplan ausgelöst und handelt mit
Werkzeugen – Termine buchen, Leads im CRM anlegen und nachfassen, E-Mails schreiben, im Web
recherchieren, das Team benachrichtigen. Riskante Aktionen laufen über eine Freigabe-Warteschlange.

Agententypen (Katalog: `vorlagen/agenten/katalog.json`, Prompts: `vorlagen/agenten/<typ>/prompt.md`):

| Typ | Aufgabe |
|---|---|
| `rezeption` | Digitale Rezeption 24/7 per Chat, E-Mail, Formular **und Telefon (Vapi)**: Fragen, Terminbuchung/-absage, Anfragen aufnehmen, Weiterleitung |
| `lead-generierung` | Recherchiert B2B-Neukunden im Web, bewertet, legt im CRM an, bereitet Erstansprache vor |
| `lead-nachfassen` | Qualifiziert Anfragen, fasst automatisch nach, bringt Interessenten zum Termin |
| `posteingang` | Sortiert und beantwortet E-Mails, leitet Sonderfälle an Menschen weiter |
| `angebots-assistent` | Erstellt Angebotsentwürfe aus Anfrage + Preisliste |

## Kundenordner

```
kunden/<slug>/
├── 00-intake.md        # Erstgespräch (Fragebogen: vorlagen/kunden-fragebogen.md)
├── 01-analyse.md       # kmu-analyst
├── 02-architektur.md   # agent-architekt
├── 04-compliance.md    # compliance-pruefer
├── 05-tests.json       # qa-tester: Szenarien  → 05-testergebnis.md
├── 06-angebot.md       # angebots-schreiber
├── agent/              # agent-entwickler: config.json, <typ>.md (Prompts), wissen.md
└── daten/              # Laufzeitdaten (CRM, Termine, Freigaben, Protokoll) – NIE committen
```

## Pipeline in Claude Code

| Befehl | Zweck |
|---|---|
| `/neuer-kunde <Firma> [Branche] [Notizen]` | Kundenordner anlegen, Erstgespräch auswerten |
| `/agent-bauen <slug>` | Analyse → Architektur → **Freigabe durch dich** → Bau → Compliance + Tests |
| `/agent-testen <slug>` | Testszenarien erzeugen, gegen den echten Agenten laufen lassen, Fehler beheben |
| `/angebot <slug>` | Angebot mit Paketen, Preisen (`vorlagen/preise.md`) und ROI |

Subagenten: `.claude/agents/`. Branchenwissen: Skill `kmu-branchen-blueprints`.
Ein Hook prüft jede Änderung an `kunden/*/agent/` automatisch (`scripts/validate_config.py`).

## Laufzeit (runtime/) – `python -m runtime <befehl> kunden/<slug> …`

`pruefen` · `chat <agent>` · `nachricht <agent> "…"` · `auftrag <agent>` (Daueraufgabe jetzt
ausführen) · `freigaben` / `freigeben <id>` / `ablehnen <id>` · `leads` · `termine` · `berichte` ·
`server` (Chat-Widget, Webhooks, Kalender-Feed) · `zeitplan` (Daueraufgaben nach Plan) ·
`email <agent>` (Posteingang überwachen).

**Telefon (Vapi):** Kanal `telefon` in config.json → `python scripts/vapi_assistent.py kunden/<slug> <agent>
--server-url https://…` erzeugt `agent/vapi-assistent.json` → mit dem Vapi-MCP (`.mcp.json`, braucht
`VAPI_TOKEN`) den Assistenten anlegen/aktualisieren und eine Nummer zuweisen. Vapi ruft für Werkzeuge
`POST /vapi/<agent>` auf; nach jedem Anruf bearbeitet unser Agent das Transkript nach.

Benötigt `pip install -r requirements.txt` und `ANTHROPIC_API_KEY`. Standardmodell `claude-opus-5`.

## Regeln für die Arbeit in diesem Repo

1. **Nichts erfinden.** Preise, Zeiten, Leistungen kommen nur aus Intake, Kunden-Website oder vom
   Kunden. Fehlendes als `[OFFEN: …]` markieren und melden.
2. **Transparenz:** Agenten geben sich als KI zu erkennen (EU AI Act Art. 50).
3. **Datensparsamkeit (DSGVO)**, keine Gesundheits-/Zahlungsdaten im Chat.
4. **Kaltakquise nur B2B** mit konkretem Bezug, Widerspruchsmöglichkeit und menschlicher Freigabe
   (UWG §7). Nie Privatpersonen kalt anschreiben.
5. **Freigabe zuerst:** Neue Agenten starten mit Freigabe für ausgehende E-Mails; Autonomie wird
   erst nach bestandenen Tests und Testphase erhöht.
6. Neue Werkzeuge/Integrationen gehören in `runtime/werkzeuge.py` + `runtime/config.py`
   (`WERKZEUG_GRUPPEN`) – dann stehen sie allen Kunden zur Verfügung.
7. **Vapi-Konto:** Assistenten/Nummern über das Vapi-MCP nur nach ausdrücklicher Zustimmung des Nutzers
   anlegen, ändern oder löschen – das kostet Geld und betrifft echte Telefonnummern.
8. **Keine fremden Binärdateien/Installer** ins Repo holen oder ausführen (siehe `SICHERHEITSHINWEIS.md`).
