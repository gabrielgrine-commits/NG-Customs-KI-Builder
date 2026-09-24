# NG Customs – KI-Agenten-Builder für KMUs

Werkzeugkasten, mit dem NG Customs für kleine und mittlere Unternehmen **autonome KI-Agenten**
plant, baut, testet, anbietet und betreibt: digitale Rezeption, Lead-Generierung,
Lead-Nachfassen, Posteingangs-Assistenz und Angebots-Assistent.

Das Repo besteht aus zwei Teilen:

1. **Builder (Claude Code):** Subagenten und Befehle, die aus einem Erstgespräch einen fertigen
   Kunden-Agenten machen: Analyse → Architektur → Bau → Compliance → Tests → Angebot.
2. **Laufzeit (`runtime/`):** Die Plattform, auf der die Kunden-Agenten laufen. Sie kann mit
   Kalender, CRM, E-Mail, Web-Recherche und Team-Benachrichtigung arbeiten, hat eine
   Freigabe-Warteschlange und ein Audit-Protokoll. Ausgelöst wird ein Agent per Website-Chat,
   E-Mail-Posteingang, Webhook oder Zeitplan.

```
Erstgespräch ─► /neuer-kunde ─► /agent-bauen ─► kunden/<slug>/agent/ ─► python -m runtime …
                                   │                                     ├─ server   (Chat-Widget, Formulare)
                 kmu-analyst ──────┤                                     ├─ email    (Posteingang)
                 agent-architekt ──┤  ◄── du gibst die Architektur frei  ├─ zeitplan (Daueraufgaben)
                 agent-entwickler ─┤                                     └─ freigaben (Mensch prüft)
                 compliance-pruefer┤
                 qa-tester ────────┘ ─► /angebot ─► 06-angebot.md
```

## Schnellstart

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

# Beispielkunde (fiktiver Malerbetrieb) ausprobieren
python -m runtime pruefen kunden/beispiel-malerbetrieb
python -m runtime chat    kunden/beispiel-malerbetrieb rezeption
python -m runtime auftrag kunden/beispiel-malerbetrieb lead-generierung   # recherchiert B2B-Leads
python -m runtime leads   kunden/beispiel-malerbetrieb
python -m runtime freigaben kunden/beispiel-malerbetrieb                   # vorbereitete E-Mails prüfen
python -m runtime freigeben kunden/beispiel-malerbetrieb F-1234abcd

# Tests der Agenten (Trockenlauf, verschickt nichts)
python scripts/run_tests.py kunden/beispiel-malerbetrieb
```

## Neuen Kunden bauen (in Claude Code)

```
/neuer-kunde "Dachdeckerei Muster GmbH" Handwerk <Notizen aus dem Erstgespräch>
/agent-bauen dachdeckerei-muster
/angebot dachdeckerei-muster
```

`/agent-bauen` hält nach der Architektur an und wartet auf deine Freigabe, bevor gebaut wird.

## Kunden-Agent live schalten

1. **Server** (kleiner VPS, hinter HTTPS-Reverse-Proxy wie Caddy):
   `python -m runtime server kunden/<slug> --port 8080`
2. **Website-Chat** auf der Kunden-Website einbinden:
   ```html
   <script src="https://agent.kunde.de/widget.js" data-agent="rezeption"
           data-titel="Digitale Rezeption" data-farbe="#1f6feb"
           data-datenschutz="https://kunde.de/datenschutz" defer></script>
   ```
   Domain der Website in `server.erlaubte_origins` eintragen.
3. **Kontaktformular/Make/Zapier/Telefonie** → `POST /webhook/<agent>` mit Header `X-Token`
   (Wert aus der Umgebungsvariable in `server.token_env`).
4. **E-Mail-Posteingang:** eigenes Postfach für den Agenten (z. B. anfrage@kunde.de), Zugangsdaten
   als Umgebungsvariablen (`email.benutzer_env`/`passwort_env`), dann
   `python -m runtime email kunden/<slug> rezeption`.
5. **Daueraufgaben** (Lead-Generierung, Nachfassen): `python -m runtime zeitplan kunden/<slug>`
   als Dienst laufen lassen, oder per Cron `python -m runtime auftrag kunden/<slug> <agent>`.
6. **Telefon (Vapi):** siehe Abschnitt unten.
7. **Kalender** im Google-/Outlook-Kalender des Kunden abonnieren:
   `https://agent.kunde.de/kalender.ics?token=<TOKEN>`
8. **Benachrichtigungen** ans Team per E-Mail (`benachrichtigung.email`) oder Webhook
   (`benachrichtigung.webhook_url`, z. B. Slack/Teams/Make → WhatsApp).

Die Prozesse lassen sich z. B. als systemd-Dienste betreiben; alle teilen sich die Daten in
`kunden/<slug>/daten/` (mit Dateisperre).

## Telefon-Rezeption mit Vapi

Vapi übernimmt Telefonnummer, Spracherkennung und Sprachausgabe. Die Werkzeuge (Kalender, CRM,
Team) laufen über unsere Plattform, mit denselben Freigaberegeln und demselben Protokoll. Nach
jedem Anruf prüft unser Agent das Transkript nach: Lead angelegt? Rückruf ans Team gemeldet?
Bestätigung verschickt?

1. Vapi-Konto anlegen, API-Key (Private Key) als `VAPI_TOKEN` in der Umgebung setzen. Das Vapi-MCP ist
   in `.mcp.json` eingetragen (`npx mcp-remote https://mcp.vapi.ai/mcp`, braucht Node.js), sodass
   Claude Code Assistenten und Nummern direkt verwalten kann. **Den Key nie in `.mcp.json` schreiben.**
2. In `config.json` beim Agenten den Kanal `telefon` eintragen und den Abschnitt `telefon` pflegen
   (Begrüßung mit KI-Hinweis, Stimme, Transkription, Modell).
3. Server öffentlich per HTTPS erreichbar machen (`python -m runtime server …`) und den Token setzen
   (Umgebungsvariable aus `server.token_env`, z. B. `openssl rand -hex 24`).
4. `python scripts/vapi_assistent.py kunden/<slug> rezeption --server-url https://agent.kunde.de`
   schreibt `agent/vapi-assistent.json` (in .gitignore, da sie den Token enthält).
5. In Claude Code (bzw. `/agent-bauen`): Assistent über das Vapi-MCP anlegen, Telefonnummer
   zuweisen. Beim Kunden eine Rufumleitung auf die Nummer einrichten (z. B. bei „besetzt“, „keine
   Antwort nach 20 s“ oder nach Feierabend).

Hinweise: Stimme, Transkription und Modell sind Vorschläge. Prüfe im Vapi-Dashboard, welche
Anthropic-Modelle und deutschen Stimmen verfügbar sind. Ein schnelleres Modell verkürzt die
Antwortpausen am Telefon. Aufzeichnung und Transkription von Anrufen braucht einen Hinweis zu
Beginn des Gesprächs und in der Datenschutzerklärung (siehe `compliance-pruefer`).

## Werkzeuge der Agenten

| Gruppe | Werkzeuge | Hinweis |
|---|---|---|
| `kalender` | freie Termine, buchen, suchen, stornieren | Arbeitszeiten, Puffer, Vorlauf, Sperrtage; ICS-Feed |
| `crm` | Lead anlegen (mit Dublettenprüfung), suchen, aktualisieren | Status, Bewertung 1–10, Wiedervorlage, Historie |
| `email` | E-Mail senden | SMTP; ohne SMTP landet sie in `daten/postausgang/`; Sperrliste |
| `team` | Team benachrichtigen | E-Mail und/oder Webhook |
| `web` | Web-Suche, Webseiten lesen | Anthropic-Server-Werkzeuge |

Jedes Werkzeug kann pro Agent in `freigabe_erforderlich` stehen: Dann bereitet der Agent die
Aktion vor, und ein Mensch gibt sie frei.

**Erweiterungen** (Google Calendar API, HubSpot/Pipedrive, WhatsApp) werden in
`runtime/werkzeuge.py` ergänzt. Die Tool-Definition bleibt gleich, nur die Methode ruft dann
die externe API auf.

## Struktur

```
.claude/agents/       Subagenten des Builders
.claude/commands/     /neuer-kunde, /agent-bauen, /agent-testen, /angebot
.claude/skills/       kmu-branchen-blueprints (Branchenwissen)
.claude/hooks/        Validierung der Kunden-Konfiguration
runtime/              Agenten-Plattform (engine, werkzeuge, server, worker, widget)
scripts/              neuer_kunde.py, validate_config.py, run_tests.py
vorlagen/             Agenten-Katalog, Prompts, config-Basis, Fragebogen, Wissensbasis, Preise
kunden/               ein Ordner pro Kunde (Beispiel: beispiel-malerbetrieb, fiktiv)
```

## Wichtig

- `vorlagen/preise.md` enthält **Beispielpreise**. Bitte durch deine echten Preise ersetzen.
- Die Compliance-Prüfung ist eine fachliche Risikoprüfung, **keine Rechtsberatung**.
  Datenschutzerklärung und AV-Verträge sollte ein Anwalt oder Datenschutzbeauftragter prüfen.
- Siehe `SICHERHEITSHINWEIS.md` zur ursprünglich hochgeladenen ZIP-Datei.
