---
description: Komplette Pipeline – Analyse, Architektur, Bau, Compliance, Tests – für einen Kunden
argument-hint: <kunden-slug> [Wünsche/Änderungen]
---

Baue die KI-Agenten für den Kunden `kunden/$ARGUMENTS` (erstes Wort = Slug, Rest = zusätzliche
Wünsche des Nutzers, die in jedem Schritt Vorrang haben).

Prüfe zuerst, ob `kunden/<slug>/00-intake.md` existiert (sonst: auf `/neuer-kunde` verweisen) und
welche Schritte schon erledigt sind (vorhandene Dateien 01–05). Erledigte Schritte nicht neu machen,
außer der Nutzer wünscht es oder die Eingaben haben sich geändert.

1. **Analyse** → Subagent `kmu-analyst` (schreibt 01-analyse.md).
2. **Architektur** → Subagent `agent-architekt` (schreibt 02-architektur.md).
3. **STOPP – Freigabe durch den Nutzer.** Zeige kompakt:
   - welche Agenten, was jeder autonom erledigt, Kanäle/Zeitplan
   - Freigabe-Matrix (was braucht menschliche Freigabe)
   - Integrationen außerhalb der Plattform + offene Fragen
   Frage: „Soll ich so bauen, oder etwas ändern?“ und warte auf die Antwort.
4. **Bau** → Subagent `agent-entwickler` (agent/-Dateien, Validierung).
5. **Compliance** und **Tests** parallel → Subagenten `compliance-pruefer` und `qa-tester`.
6. Gibt es 🔴-Befunde oder fehlgeschlagene Tests, deren Ursache Prompt/Wissen/Konfiguration ist:
   `agent-entwickler` mit den konkreten Befunden beauftragen, danach `qa-tester` erneut laufen
   lassen. Höchstens zwei Korrekturrunden, danach verbleibende Punkte an den Nutzer melden.
7. **Telefon (nur wenn ein Agent den Kanal `telefon` hat):** Liegt `agent/vapi-assistent.json` vor
   und sind die Vapi-MCP-Werkzeuge (`mcp__vapi-mcp__…`) verfügbar, frag den Nutzer, ob der Assistent
   bei Vapi angelegt bzw. aktualisiert werden soll (kostet Geld, echte Nummern). Erst nach dem Ja:
   anlegen/aktualisieren (bestehende `telefon.vapi_assistent_id` → aktualisieren statt neu anlegen),
   die ID in config.json unter `telefon.vapi_assistent_id` speichern und nach Wunsch eine Nummer
   zuweisen. Fehlt das MCP oder `VAPI_TOKEN`, erkläre die Einrichtung (README, Abschnitt Telefon).
8. **Abschlussbericht** an den Nutzer:
   - Agenten + Autonomiestufen, Testergebnis x/y, Compliance-Ampel
   - Offene Punkte, die der Kunde liefern muss
   - Nächste Schritte zum Livegang:
     `python -m runtime chat kunden/<slug> <agent>` zum Ausprobieren,
     `python -m runtime server kunden/<slug>` + Widget-Snippet, E-Mail/Zeitplan-Worker,
     und das Angebot mit `/angebot <slug>`.
