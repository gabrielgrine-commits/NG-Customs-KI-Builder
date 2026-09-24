---
name: kmu-branchen-blueprints
description: "Branchenwissen für KI-Agenten in deutschen KMU: typische Engpässe, bewährte autonome Agenten (Rezeption, Lead-Generierung, Nachfassen, Posteingang, Angebote), Werkzeuge, Freigaberegeln, Compliance-Fallen und Verkaufsargumente je Branche (Handwerk, Gesundheit/Praxen, Gastronomie/Hotel, Beauty/Friseur, Immobilien, Kanzlei/Steuerberatung, Handel/E-Commerce, B2B-Dienstleister). Nutzen bei Analyse, Architektur, Prompt-Erstellung oder Angeboten für einen KMU-Kunden sowie bei Fragen wie 'welcher Agent passt für einen Zahnarzt/Dachdecker/Makler?'."
---

# KMU-Branchen-Blueprints

Lies die Datei der passenden Branche unter `references/`. Passt keine genau, nimm die nächstliegende
und die allgemeinen Regeln unten.

| Branche | Datei |
|---|---|
| Handwerk & Bau (Maler, SHK, Elektro, Dachdecker, Tischler, Garten-/Landschaftsbau) | `references/handwerk.md` |
| Gesundheit (Arzt-, Zahnarzt-, Physio-, Therapiepraxen, Pflege) | `references/gesundheit.md` |
| Gastronomie & Hotellerie | `references/gastronomie-hotel.md` |
| Beauty, Friseur, Kosmetik, Fitness, Studios | `references/beauty-fitness.md` |
| Immobilien (Makler, Hausverwaltung) | `references/immobilien.md` |
| Kanzleien & Steuerberatung | `references/kanzlei-steuer.md` |
| Handel & E-Commerce | `references/handel-ecommerce.md` |
| B2B-Dienstleister (Agenturen, IT, Reinigung, Logistik, Ingenieurbüros) | `references/b2b-dienstleister.md` |

## Agententypen (Plattform-Katalog: `vorlagen/agenten/katalog.json`)

| Typ | Arbeitet autonom … | Typischer Nutzen |
|---|---|---|
| `rezeption` | beantwortet Fragen, bucht/verschiebt Termine, nimmt Anfragen auf – 24/7 über Chat, E-Mail, Formular und **Telefon** (Vapi) | weniger Telefonunterbrechungen, keine verlorenen Anfragen nach Feierabend |
| `lead-nachfassen` | qualifiziert neue Anfragen sofort, fasst nach, bringt zum Termin, pflegt CRM | höhere Abschlussquote, keine vergessenen Angebote |
| `lead-generierung` | recherchiert passende B2B-Firmen im Web, bewertet sie, legt CRM-Einträge an, schreibt Erstansprache (mit Freigabe) | planbarer Neukunden-Nachschub |
| `posteingang` | sortiert und beantwortet E-Mails, leitet Sonderfälle weiter | 3–10 h/Woche weniger E-Mail-Arbeit |
| `angebots-assistent` | erstellt Angebotsentwurf aus Anfrage + Preisliste | Angebot in Minuten statt Tagen |

## Allgemeine Regeln

- **Einstieg klein:** 1–2 Agenten, 2 Wochen Testphase mit Freigabe aller ausgehenden E-Mails.
- **Speed-to-Lead:** Wer innerhalb von 5 Minuten antwortet, gewinnt deutlich häufiger den Auftrag
  als nach Stunden – das stärkste Verkaufsargument für Rezeption + Nachfassen.
- **B2C-Kaltakquise ist in Deutschland verboten** (UWG §7). Lead-Generierung nur für Betriebe mit
  Geschäftskunden.
- **Gesundheitsdaten** (Praxen, Physio, teils Beauty/Fitness) sind besondere Kategorien (DSGVO Art. 9):
  Agent fragt keine Symptome/Diagnosen ab, nur Terminwunsch + Kontakt.
- Agenten ersetzen keine Fachberatung – immer klare Übergabe an Menschen.
