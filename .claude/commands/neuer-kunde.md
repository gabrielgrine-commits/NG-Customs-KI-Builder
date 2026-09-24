---
description: Neuen KMU-Kunden anlegen und das Erstgespräch auswerten
argument-hint: <Firmenname> [Branche] [Notizen/Transkript oder Pfad]
---

Lege einen neuen Kunden für NG Customs an: $ARGUMENTS

1. Leite Firmenname, Branche und – falls genannt – gewünschte Agenten aus den Argumenten ab. Fehlt
   die Branche, schließe sie aus Namen/Notizen oder frag kurz nach.
2. Wähle vorläufige Agententypen aus `vorlagen/agenten/katalog.json` (Standard: `rezeption`) und
   führe aus: `python3 scripts/neuer_kunde.py "<Firma>" --branche "<Branche>" --agenten <typen>`.
3. Wurden Notizen, ein Transkript oder ein Dateipfad mitgegeben: übertrage alle Informationen in
   die passenden Abschnitte von `kunden/<slug>/00-intake.md` (Notizen/Transkript zusätzlich
   unten anhängen). Steht eine Website im Material, lies sie mit WebFetch und ergänze Leistungen,
   Öffnungszeiten, Kontakt, Datenschutz-URL.
4. Zeige dem Nutzer: angelegter Ordner, welche Intake-Felder noch leer sind (als kurze Liste von
   Fragen, die er dem Kunden stellen kann), und den nächsten Schritt `/agent-bauen <slug>`.
