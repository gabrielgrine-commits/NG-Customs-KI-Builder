---
name: grill-me
description: Den Nutzer unerbittlich zu einem Plan oder Entwurf befragen, bis ein gemeinsames Verständnis erreicht ist, und dabei jeden Zweig des Entscheidungsbaums klären. Nutzen, wenn der Nutzer einen Plan auf Herz und Nieren prüfen, seinen Entwurf durchlöchern lassen will oder „grill me“, „grill mich“, „lös mich aus“, „nimm meinen Plan auseinander“ oder „hinterfrag meinen Plan“ sagt.
---

<!-- Quelle: https://github.com/RobMitt/grill-me-skill (Commit 31d61d6, keine Lizenzangabe im Repo), ins Deutsche übersetzt. -->

# Grill me – Plan auf Herz und Nieren prüfen

Befrage den Nutzer unerbittlich zu jedem Aspekt seines Plans, bis ihr ein gemeinsames Verständnis
erreicht habt. Gehe jeden Zweig des Entscheidungsbaums durch und kläre Abhängigkeiten zwischen
Entscheidungen eine nach der anderen.

## Wie du fragst

Stelle **jede** Frage mit dem **AskUserQuestion-Werkzeug**. Stelle Fragen nie als reinen Text in
deiner Antwort – nutze immer das Auswahlfenster, damit der Nutzer schnell eine Antwort wählen oder
eine eigene eintippen kann.

Stelle **eine Frage auf einmal**. Warte auf die Antwort, bevor du zur nächsten Frage übergehst. So
bleibt das Gespräch fokussiert und niemand wird überfordert.

Gib zu jeder Frage 2–4 konkrete Antwortmöglichkeiten vor, die die wahrscheinlichsten Antworten oder
Richtungen abbilden. Überlege, was der Nutzer realistisch wählen würde – allgemeine Optionen wie
„Ja“ / „Nein“ helfen nur, wenn die Frage wirklich nur zwei Antworten kennt. Das Feld „Sonstiges“
steht dem Nutzer immer für eine eigene Antwort offen.

## Ablauf

1. Nach jeder Antwort die Entscheidung kurz bestätigen (höchstens 1–2 Sätze), dann sofort die
   nächste Frage per AskUserQuestion stellen.
2. Wenn sich eine Frage durch einen Blick in den Code oder die Dateien beantworten lässt, schau
   selbst nach, statt den Nutzer zu fragen.
3. Weitermachen, bis alle Zweige des Entscheidungsbaums geklärt sind.
4. Zum Schluss eine knappe Zusammenfassung aller getroffenen Entscheidungen geben.

## Hinweis für NG Customs

Dieser Skill ist die bewusste Ausnahme von „Fragen gesammelt am Ende stellen“ (`CLAUDE.md`): Er
läuft nur, wenn der Nutzer ausdrücklich befragt werden will. Die Regeln aus `CLAUDE.md` gelten
weiter – vor allem: nichts erfinden (Offenes als `[OFFEN: …]` festhalten), DSGVO/UWG/TKG beachten.
