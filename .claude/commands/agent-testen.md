---
description: Testszenarien für einen Kunden-Agenten erzeugen/ausführen und Fehler beheben lassen
argument-hint: <kunden-slug> [Fokus, z. B. "nur Terminbuchung"]
---

Teste die Agenten von `kunden/$ARGUMENTS` (erstes Wort = Slug, Rest = Testfokus).

1. Subagent `qa-tester`: Szenarien in `05-tests.json` ergänzen/aktualisieren (mit Fokus, falls
   angegeben) und `python3 scripts/run_tests.py kunden/<slug>` ausführen.
2. Bei Fehlern mit Ursache Prompt/Wissen/Konfiguration: Subagent `agent-entwickler` mit den
   Befunden korrigieren lassen, dann Tests erneut ausführen (max. zwei Runden).
3. Berichte x/y bestanden, was korrigiert wurde und was offen bleibt.
