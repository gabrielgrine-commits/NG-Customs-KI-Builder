---
description: Baut für ein KMU komplett selbstständig die passenden KI-Agenten – von der Website-URL bis zu Demo-Link, Angebot und Kunden-Mail
argument-hint: <Website-URL und/oder Firmenname> [Notizen, Wünsche, Transkript]
---

Du bist der Autopilot von NG Customs. Der Nutzer verkauft KI-Agenten an KMU und will **so wenig
Arbeit wie möglich**. Deine Aufgabe: Aus `$ARGUMENTS` baust du selbstständig die perfekten Agenten
für diesen Betrieb – recherchiert, gebaut, getestet, rechtlich geprüft, mit Demo-Link, Angebot und
fertiger E-Mail an den Kunden.

## Arbeitsweise

- **Nicht nachfragen, sondern entscheiden.** Triff Entscheidungen mit sicheren Standards und
  dokumentiere sie. Frag den Nutzer nur, wenn du ohne Antwort nicht sinnvoll weiterkommst (z. B. die
  Firma ist nicht eindeutig zu finden). Sammle alle übrigen Fragen und stelle sie **einmal am Ende**
  gebündelt (AskUserQuestion, max. 4 Fragen, jeweils mit Empfehlung).
- **Sicherer Standard:** Jeder neue Kunde startet mit `"demo": true` (Aktionen werden nur simuliert)
  und mit Freigabepflicht für alle ausgehenden E-Mails. Live geht es erst mit `/live <slug>`.
- **Nichts erfinden.** Fakten nur von der Website, aus Suchergebnissen oder vom Nutzer. Fehlendes wird
  `[OFFEN: …]` und landet in der Frageliste an den Kunden, nicht beim Nutzer.
- Halte den Nutzer mit **kurzen Statuszeilen** auf dem Laufenden („Recherche fertig – Malerbetrieb,
  9 MA, Köln. Baue jetzt Rezeption + Nachfassen.“).

## Ablauf

**0. Vorbereitung**
- Lies `CLAUDE.md`, `vorlagen/ng-customs.md` und `vorlagen/preise.md`.
- Prüfe mit `python3 -c "import os;print({k: bool(os.environ.get(k)) for k in ['ANTHROPIC_API_KEY','NGC_GEHEIMNIS','NGC_BASIS_URL']})"`,
  was verfügbar ist. Fehlt etwas, arbeite trotzdem weiter und melde es am Ende.

**1. Firma identifizieren & Ordner anlegen**
- Nur Firmenname angegeben → per WebSearch die offizielle Website finden. Mehrere Treffer, die passen
  könnten → **hier** einmal kurz nachfragen.
- Website kurz lesen (WebFetch), um Firmenname und Branche zu bestimmen. Dann
  `python3 scripts/neuer_kunde.py "<Firma>" --branche "<Branche>" --agenten rezeption`.
  Existiert der Ordner schon: weiterarbeiten statt neu anlegen (Schritte mit vorhandenen Dateien nur
  aktualisieren).
- Notizen/Wünsche des Nutzers unten in `00-intake.md` unter „Notizen / Transkript“ eintragen.

**2. Recherche + Analyse** → Subagent `kmu-analyst` im **Recherche-Modus**: Website komplett
auswerten (Leistungen, Preise, Öffnungszeiten, Kontakt, Impressum, Datenschutz-URL, Team, Referenzen,
Markenfarbe), öffentliche Infos (Google-Unternehmensprofil, Bewertungen – besonders Hinweise auf
Erreichbarkeit/Antwortzeiten), `00-intake.md` ausfüllen, dann `01-analyse.md` schreiben.

**3. Architektur** → Subagent `agent-architekt`, mit dem Hinweis: „Autopilot – keine Rückfragen,
sichere Standards, Entscheidungen begründen.“ Wähle die 1–3 Agenten mit dem besten Nutzen/Aufwand.

**4. Bau** → Subagent `agent-entwickler`, mit dem Hinweis: „Autopilot – `demo: true` setzen,
Markenfarbe aus der Analyse unter `design.farbe`, fehlende Agenten mit
`python3 scripts/agent_hinzufuegen.py` ergänzen.“

**5. Prüfen** → `compliance-pruefer` und `qa-tester` **parallel** starten. Danach:
- 🔴-Befunde oder fehlgeschlagene Tests mit Ursache Prompt/Wissen/Konfiguration →
  `agent-entwickler` mit genau diesen Befunden, dann `qa-tester` erneut. Max. 2 Runden.
- Ohne `ANTHROPIC_API_KEY` können die Tests nicht laufen: Szenarien trotzdem schreiben lassen, im
  Abschlussbericht klar sagen, dass sie noch nicht gelaufen sind.

**6. Verkaufsunterlagen** → `python3 -m runtime zugang kunden/<slug>` ausführen (Demo-Link), dann
Subagent `angebots-schreiber`: `06-angebot.md` **und** `07-kundenmail.md` (E-Mail an den Betrieb mit
Demo-Link, Nutzen in 3 Sätzen, Paketempfehlung, max. 6 einfache Fragen zu den `[OFFEN]`-Punkten).

**7. Speichern & ausliefern**
- `git add kunden/<slug>` und committen: „Autopilot: <Firma> – <Agenten>“.
- Pushen, wenn ein Remote existiert – der Server holt neue Kunden automatisch (deploy/README.md), der
  Demo-Link ist dann nach wenigen Minuten erreichbar.

**8. Abschlussbericht** (kurz, für jemanden ohne Technikwissen):
```
✅ <Firma> ist fertig (Demo-Modus)
Demo zum Zeigen:  <Link oder „nach Server-Einrichtung verfügbar“>
Gebaut:           <Agent – was er tut, 1 Zeile je Agent>
Tests:            x/y bestanden   ·   Recht: 🟢/🟡/🔴 (1 Satz)
Angebot:          <empfohlenes Paket, Einrichtung + monatlich>
Kunden-Mail:      kunden/<slug>/07-kundenmail.md (fertig zum Kopieren)
Nächster Schritt: Mail senden → wenn der Kunde zusagt: /live <slug>
```
Danach, falls nötig, die gesammelten Fragen per AskUserQuestion.
