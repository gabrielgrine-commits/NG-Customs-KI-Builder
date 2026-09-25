"""Laden und Prüfen der Kunden-Konfiguration (kunden/<slug>/agent/config.json)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WERKZEUG_GRUPPEN = {
    "kalender": [
        "kalender_freie_termine",
        "kalender_termin_buchen",
        "kalender_termine_suchen",
        "kalender_termin_stornieren",
    ],
    "crm": ["crm_lead_speichern", "crm_leads_suchen", "crm_lead_aktualisieren"],
    "email": ["email_senden"],
    "team": ["team_benachrichtigen"],
    "web": ["web_suche", "web_abruf"],
}
ALLE_WERKZEUGE = {w for gruppe in WERKZEUG_GRUPPEN.values() for w in gruppe}
KANAELE = {"chat", "email", "webhook", "zeitplan", "cli", "telefon"}
WOCHENTAGE = ["mo", "di", "mi", "do", "fr", "sa", "so"]
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
LAENDER = {"DE", "AT"}
# Telefon: Vapi akzeptiert nur Modelle aus seiner eigenen Liste (Stand 09/2026, api.vapi.ai/api-json →
# AnthropicModel); die Plattform-ID "claude-opus-5" lehnt es mit HTTP 400 ab.
VAPI_MODELLE = {
    "claude-sonnet-5", "claude-opus-4-6", "claude-sonnet-4-6", "claude-opus-4-5-20251101",
    "claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001",
}
VAPI_STANDARD_MODELL = "claude-sonnet-5"  # schnell genug für Gespräche ohne spürbare Pausen


class KonfigFehler(Exception):
    pass


@dataclass
class KundenKonfig:
    kunden_dir: Path
    daten: dict[str, Any]

    @property
    def agent_dir(self) -> Path:
        return self.kunden_dir / "agent"

    @property
    def daten_dir(self) -> Path:
        return self.kunden_dir / "daten"

    @property
    def firma(self) -> dict[str, Any]:
        return self.daten["firma"]

    @property
    def land(self) -> str:
        return self.daten.get("land", "DE")

    @property
    def zeitzone(self) -> str:
        return self.daten.get("zeitzone", "Europe/Vienna" if self.land == "AT" else "Europe/Berlin")

    @property
    def modell(self) -> str:
        return self.daten.get("modell", "claude-opus-5")

    def agent(self, name: str) -> dict[str, Any]:
        agenten = self.daten["agenten"]
        if name not in agenten:
            raise KonfigFehler(f"Agent '{name}' nicht in config.json. Vorhanden: {', '.join(agenten)}")
        return agenten[name]

    def werkzeuge_fuer(self, agent_name: str) -> list[str]:
        namen: list[str] = []
        for gruppe in self.agent(agent_name).get("werkzeuge", []):
            namen.extend(WERKZEUG_GRUPPEN[gruppe])
        return namen

    def text_datei(self, relativ: str) -> str:
        return (self.agent_dir / relativ).read_text(encoding="utf-8")


def laden(kunden_dir: str | Path) -> KundenKonfig:
    kunden_dir = Path(kunden_dir).resolve()
    pfad = kunden_dir / "agent" / "config.json"
    if not pfad.exists():
        raise KonfigFehler(f"{pfad} fehlt")
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise KonfigFehler(f"{pfad}: ungültiges JSON ({e})") from e
    konfig = KundenKonfig(kunden_dir, daten)
    fehler = pruefen(konfig)
    if fehler:
        raise KonfigFehler("Konfiguration ungültig:\n- " + "\n- ".join(fehler))
    return konfig


def pruefen(k: KundenKonfig) -> list[str]:
    """Gibt eine Liste verständlicher Fehlermeldungen zurück (leer = alles gut)."""
    d = k.daten
    fehler: list[str] = []

    firma = d.get("firma")
    if not isinstance(firma, dict):
        return ["'firma' fehlt oder ist kein Objekt"]
    for feld in ("name", "branche", "datenschutz_url"):
        if not firma.get(feld):
            fehler.append(f"firma.{feld} fehlt")

    if d.get("land", "DE") not in LAENDER:
        fehler.append(f"land muss eines von {sorted(LAENDER)} sein")

    farbe = (d.get("design") or {}).get("farbe")
    if farbe is not None and not re.fullmatch(r"#[0-9a-fA-F]{3,8}", str(farbe)):
        fehler.append("design.farbe muss eine Hex-Farbe sein, z. B. #1f6feb")

    if d.get("effort") and d["effort"] not in EFFORTS:
        fehler.append(f"effort muss eines von {sorted(EFFORTS)} sein")

    for datei in d.get("wissen", []):
        if not (k.agent_dir / datei).exists():
            fehler.append(f"Wissensdatei agent/{datei} fehlt")

    agenten = d.get("agenten")
    if not isinstance(agenten, dict) or not agenten:
        fehler.append("'agenten' fehlt oder ist leer")
        return fehler

    brauchte_kalender = brauchte_email = False
    for name, a in agenten.items():
        p = f"agenten.{name}"
        if not a.get("prompt"):
            fehler.append(f"{p}.prompt fehlt")
        elif not (k.agent_dir / a["prompt"]).exists():
            fehler.append(f"{p}: Prompt-Datei agent/{a['prompt']} fehlt")
        for g in a.get("werkzeuge", []):
            if g not in WERKZEUG_GRUPPEN:
                fehler.append(f"{p}.werkzeuge: unbekannte Gruppe '{g}' (erlaubt: {', '.join(WERKZEUG_GRUPPEN)})")
        brauchte_kalender |= "kalender" in a.get("werkzeuge", [])
        brauchte_email |= "email" in a.get("werkzeuge", []) or "email" in a.get("kanaele", [])
        for w in a.get("freigabe_erforderlich", []):
            if w not in ALLE_WERKZEUGE:
                fehler.append(f"{p}.freigabe_erforderlich: unbekanntes Werkzeug '{w}'")
        for kanal in a.get("kanaele", []):
            if kanal not in KANAELE:
                fehler.append(f"{p}.kanaele: unbekannter Kanal '{kanal}' (erlaubt: {', '.join(sorted(KANAELE))})")
        if "zeitplan" in a.get("kanaele", []):
            zp = a.get("zeitplan") or {}
            if not a.get("auftrag"):
                fehler.append(f"{p}: Kanal 'zeitplan' braucht einen 'auftrag' (Daueraufgabe)")
            if not zp.get("uhrzeit"):
                fehler.append(f"{p}.zeitplan.uhrzeit fehlt (Format HH:MM)")
            for tag in zp.get("tage", []):
                if tag not in WOCHENTAGE:
                    fehler.append(f"{p}.zeitplan.tage: '{tag}' ungültig (mo..so)")
        if a.get("effort") and a["effort"] not in EFFORTS:
            fehler.append(f"{p}.effort ungültig")

    if brauchte_kalender:
        kal = d.get("kalender") or {}
        if not kal.get("arbeitszeiten"):
            fehler.append("kalender.arbeitszeiten fehlt (ein Agent nutzt Kalender-Werkzeuge)")
        for tag, fenster in (kal.get("arbeitszeiten") or {}).items():
            if tag not in WOCHENTAGE:
                fehler.append(f"kalender.arbeitszeiten: '{tag}' ist kein Wochentag (mo..so)")
            elif not all(isinstance(f, list) and len(f) == 2 for f in fenster):
                fehler.append(f"kalender.arbeitszeiten.{tag}: Liste von [\"HH:MM\", \"HH:MM\"] erwartet")
    if brauchte_email and not d.get("email", {}).get("absender"):
        fehler.append("email.absender fehlt (ein Agent nutzt E-Mail)")

    return fehler
