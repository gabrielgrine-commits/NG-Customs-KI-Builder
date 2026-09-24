---
description: Schnelle Verkaufs-Demo – aus einer Website in wenigen Minuten einen vorzeigbaren KI-Assistenten mit Demo-Link bauen
argument-hint: <Website-URL> [Notizen]
---

Baue so schnell wie möglich eine **Vorführ-Version** für den Betrieb aus `$ARGUMENTS`, damit der
Nutzer sie im Verkaufsgespräch zeigen oder per Mail schicken kann. Keine Rückfragen – außer die
Website ist nicht erreichbar und es gibt keine Notizen.

1. Website lesen (WebFetch: Startseite, Leistungen/Preise, Kontakt/Impressum, Öffnungszeiten).
   Firmenname, Branche, Markenfarbe bestimmen.
2. `python3 scripts/neuer_kunde.py "<Firma>" --branche "<Branche>" --agenten rezeption --land <DE|AT>`
   (existiert der Ordner schon: nur aktualisieren).
3. Selbst (ohne Subagenten, für Tempo) ausfüllen:
   - `agent/wissen.md` – nur Fakten von der Website, Rest `[OFFEN: …]`
   - `agent/rezeption.md` – Branchenhinweise aus `.claude/skills/kmu-branchen-blueprints/`
   - `agent/config.json` – Firmendaten, `"demo": true`, `design.farbe`, realistische Arbeitszeiten
     laut Website; Kanal `telefon` entfernen, falls kein Telefon-Demo gewünscht.
   - `00-intake.md` – was du herausgefunden hast.
4. `python3 scripts/validate_config.py kunden/<slug>`, Fehler beheben.
5. Falls `ANTHROPIC_API_KEY` gesetzt: kurzer Test mit
   `python3 -m runtime nachricht kunden/<slug> rezeption "Was bieten Sie an und wann haben Sie Zeit?"`
   – Antwort prüfen (nichts erfunden?), ggf. nachbessern.
6. `python3 -m runtime zugang kunden/<slug>` → Demo-Link. Schreibe `kunden/<slug>/07-kundenmail.md`:
   kurze, persönliche Mail (max. 120 Wörter) an den Betrieb mit Demo-Link und einer Frage nach einem
   15-Minuten-Gespräch; Absender aus `vorlagen/ng-customs.md`.
7. Committen („Demo: <Firma>“) und pushen, wenn ein Remote existiert.

Abschluss in 4 Zeilen: Demo-Link · was der Assistent schon weiß · wichtigste offene Punkte ·
„Für die Vollversion: /autopilot <slug>“.
