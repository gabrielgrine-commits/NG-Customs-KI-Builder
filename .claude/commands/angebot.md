---
description: Angebot von NG Customs für die KI-Agenten eines Kunden erstellen
argument-hint: <kunden-slug> [Vorgaben, z. B. "Budget 300 €/Monat", "mit Website"]
---

Erstelle das Angebot für `kunden/$ARGUMENTS` (erstes Wort = Slug, Rest = Vorgaben des Nutzers).

1. Fehlen `01-analyse.md` oder `02-architektur.md`, führe zuerst die Subagenten `kmu-analyst` bzw.
   `agent-architekt` aus.
2. Subagent `angebots-schreiber` mit den Vorgaben beauftragen.
3. Zeige dem Nutzer die Paketübersicht (Tabelle) und die ROI-Kernaussage und nenne den Pfad
   `kunden/<slug>/06-angebot.md`. Weise darauf hin, falls `vorlagen/preise.md` noch Beispielpreise
   enthält.
