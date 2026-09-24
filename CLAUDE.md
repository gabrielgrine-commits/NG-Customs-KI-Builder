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
| `lead-generierung` | Recherchiert B2B-Neukunden im Web, bewertet, legt im CRM an, bereitet Anruf-Leitfaden + Brief vor |
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
├── 07-kundenmail.md    # angebots-schreiber: Mail an den Betrieb (Demo-Link, Fragen)
├── 08-uebergabe.md     # /live: Übergabe-Mail (Cockpit-Link, Einbau-Code)
├── agent/              # agent-entwickler: config.json, <typ>.md (Prompts), wissen.md
└── daten/              # Laufzeitdaten (CRM, Termine, Freigaben, Protokoll) – NIE committen
```

## Pipeline in Claude Code

Der Nutzer will möglichst wenig Arbeit: **Standardweg ist `/autopilot`** (bzw. `/demo` für eine
schnelle Vorführung, `/live` nach Zusage). Entscheidungen mit sicheren Standards selbst treffen,
Fragen gesammelt am Ende stellen.

| Befehl | Zweck |
|---|---|
| `/demo <Website>` | Schnelle Vorführ-Version mit Demo-Link + kurze Mail an den Betrieb |
| `/autopilot <Website/Firma> [Notizen]` | Alles automatisch: Recherche → Agenten → Tests → Recht → Angebot → Kunden-Mail |
| `/live <slug> [Antworten des Kunden]` | Checkliste, Demo-Modus aus, Übergabe-Mail mit Cockpit-Link |
| `/neuer-kunde <Firma> [Branche] [Notizen]` | Kundenordner anlegen, Erstgespräch auswerten |
| `/agent-bauen <slug>` | Analyse → Architektur → **Freigabe durch dich** → Bau → Compliance + Tests |
| `/agent-testen <slug>` | Testszenarien erzeugen, gegen den echten Agenten laufen lassen, Fehler beheben |
| `/angebot <slug>` | Angebot mit Paketen, Preisen (`vorlagen/preise.md`) und ROI |

Subagenten: `.claude/agents/`. Branchenwissen: Skill `kmu-branchen-blueprints`.
Ein Hook prüft jede Änderung an `kunden/*/agent/` automatisch (`scripts/validate_config.py`).

## Plattform & Betrieb

- **Produktion:** `python -m runtime plattform kunden` – alle Kunden unter `/k/<slug>/` (demo, cockpit,
  widget.js, chat/, webhook/, vapi/, kalender.ics). Lädt geänderte Kunden automatisch neu.
  Deployment: `deploy/` (Docker + Caddy, `einrichten.sh`, Auto-Update per `git pull`).
- **Tokens/Links:** aus `NGC_GEHEIMNIS` + `NGC_BASIS_URL` abgeleitet (`runtime/geheimnisse.py`);
  `python -m runtime zugang kunden/<slug>` zeigt alle Links.
- **`"demo": true`** in config.json: Aktionen nur simuliert, keine Zeitpläne/Postfächer. Neue Kunden
  starten so; `/live` schaltet ab.
- **Cockpit:** Der Betrieb gibt Freigaben selbst frei (nur Betreff/Text editierbar), sieht Leads,
  Termine, Berichte, Kennzahlen. Neue Freigaben → Benachrichtigung mit Cockpit-Link.

## Laufzeit-CLI – `python -m runtime <befehl> kunden/<slug> …`

`pruefen` · `chat <agent>` · `nachricht <agent> "…"` · `auftrag <agent>` (Daueraufgabe jetzt
ausführen) · `freigaben` / `freigeben <id>` / `ablehnen <id>` · `leads` · `termine` · `berichte` ·
`server` (Chat-Widget, Webhooks, Kalender-Feed) · `zeitplan` (Daueraufgaben nach Plan) ·
`email <agent>` (Posteingang überwachen) · `zugang` (Links/Tokens).

**Telefon (Vapi):** Kanal `telefon` in config.json → `python scripts/vapi_assistent.py kunden/<slug> <agent>
--server-url https://…` erzeugt `agent/vapi-assistent.json` → mit dem Vapi-MCP (`.mcp.json`, braucht
`VAPI_TOKEN`) den Assistenten anlegen/aktualisieren und eine Nummer zuweisen. Vapi ruft für Werkzeuge
`POST /vapi/<agent>` auf; nach jedem Anruf bearbeitet unser Agent das Transkript nach.
**Ohne MCP (bevorzugt):** `python scripts/vapi_einrichten.py kunden/<slug> <agent> [--nummer <id>]` legt den
Assistenten direkt per Vapi-API an bzw. aktualisiert ihn (braucht `VAPI_TOKEN`, `NGC_BASIS_URL`, `NGC_GEHEIMNIS`).
Deutsche Nummern gibt es nicht direkt bei Vapi → bei Twilio/Telnyx/Vonage kaufen und in Vapi importieren.

Benötigt `pip install -r requirements.txt` und `ANTHROPIC_API_KEY`. Standardmodell `claude-opus-5`.

## Regeln für die Arbeit in diesem Repo

1. **Nichts erfinden.** Preise, Zeiten, Leistungen kommen nur aus Intake, Kunden-Website oder vom
   Kunden. Fehlendes als `[OFFEN: …]` markieren und melden.
2. **Transparenz:** Agenten geben sich als KI zu erkennen (EU AI Act Art. 50).
3. **Datensparsamkeit (DSGVO)**, keine Gesundheits-/Zahlungsdaten im Chat.
4. **Kaltakquise nur B2B und nie per E-Mail** (UWG § 7 Abs. 2 Nr. 3: E-Mail-Werbung braucht auch bei Firmen
   ausdrückliche Einwilligung). Erlaubt: Anruf bei Firmen mit konkretem Bezug (mutmaßliche Einwilligung)
   und Briefe – vorbereitet vom Agenten, ausgeführt von Menschen. Nie Privatpersonen kalt ansprechen.
5. **Freigabe zuerst:** Neue Agenten starten mit Freigabe für ausgehende E-Mails; Autonomie wird
   erst nach bestandenen Tests und Testphase erhöht.
6. Neue Werkzeuge/Integrationen gehören in `runtime/werkzeuge.py` + `runtime/config.py`
   (`WERKZEUG_GRUPPEN`) – dann stehen sie allen Kunden zur Verfügung.
7. **Vapi-Konto:** Assistenten/Nummern über das Vapi-MCP nur nach ausdrücklicher Zustimmung des Nutzers
   anlegen, ändern oder löschen – das kostet Geld und betrifft echte Telefonnummern.
8. **Keine fremden Binärdateien/Installer** ins Repo holen oder ausführen (siehe `SICHERHEITSHINWEIS.md`).
