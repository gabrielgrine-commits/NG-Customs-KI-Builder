"""Zugangs-Tokens und Links pro Kunde – abgeleitet aus EINEM Master-Geheimnis.

Statt für jeden Kunden eigene Tokens zu verwalten, wird alles aus der Umgebungsvariable
NGC_GEHEIMNIS berechnet (HMAC über Kunden-Slug + Zweck). Dasselbe Geheimnis auf dem Server und
lokal in Claude Code ergibt dieselben Tokens – nichts muss gespeichert oder kopiert werden.

Zwecke:
  api      – Webhooks, Vapi-Telefon, Kalender-Feed
  cockpit  – Kunden-Cockpit (Freigaben, Leads, Termine)

NGC_BASIS_URL ist die öffentliche Adresse der Plattform (z. B. https://agents.ng-customs.de);
jeder Kunde liegt darunter unter /k/<slug>/.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from .config import KundenKonfig


def slug(konfig: KundenKonfig) -> str:
    return konfig.kunden_dir.name


def token(konfig: KundenKonfig, zweck: str) -> str:
    """Leerer String = kein Token konfiguriert (Endpunkt bleibt gesperrt)."""
    if zweck == "api":  # Alt-Variante: eigener Token pro Kunde per Umgebungsvariable
        env = konfig.daten.get("server", {}).get("token_env")
        if env and os.environ.get(env):
            return os.environ[env]
    geheimnis = os.environ.get("NGC_GEHEIMNIS", "")
    if len(geheimnis) < 16:
        return ""
    return hmac.new(geheimnis.encode(), f"{slug(konfig)}:{zweck}".encode(), hashlib.sha256).hexdigest()[:40]


def basis_url() -> str:
    return os.environ.get("NGC_BASIS_URL", "").rstrip("/")


def kunden_url(konfig: KundenKonfig) -> str:
    """Öffentliche Adresse des Kunden auf der Plattform ('' wenn NGC_BASIS_URL fehlt)."""
    basis = basis_url()
    return f"{basis}/k/{slug(konfig)}" if basis else ""


def cockpit_link(konfig: KundenKonfig) -> str:
    url, t = kunden_url(konfig), token(konfig, "cockpit")
    return f"{url}/cockpit#t={t}" if url and t else ""


def zugaenge(konfig: KundenKonfig) -> dict[str, str]:
    """Alle Links/Snippets für einen Kunden (für CLI, Autopilot und Kundenmail)."""
    url = kunden_url(konfig)
    api = token(konfig, "api")
    erster_chat_agent = next((n for n, a in konfig.daten["agenten"].items() if "chat" in a.get("kanaele", [])), "")
    farbe = konfig.daten.get("design", {}).get("farbe", "#1f6feb")
    daten = {
        "kunden_url": url,
        "demo": f"{url}/demo" if url else "",
        "cockpit": cockpit_link(konfig),
        "api_token": api,
    }
    if url and erster_chat_agent:
        daten["widget_snippet"] = (
            f'<script src="{url}/widget.js" data-agent="{erster_chat_agent}" '
            f'data-titel="{konfig.agent(erster_chat_agent).get("bezeichnung", "Assistent")}" data-farbe="{farbe}" '
            f'data-datenschutz="{konfig.firma.get("datenschutz_url", "")}" defer></script>')
    if url and api:
        daten["kalender_abo"] = f"{url}/kalender.ics?token={api}"
        for name, a in konfig.daten["agenten"].items():
            if "webhook" in a.get("kanaele", []):
                daten[f"webhook_{name}"] = f"{url}/webhook/{name}  (Header X-Token: {api})"
            if "telefon" in a.get("kanaele", []):
                daten[f"vapi_{name}"] = f"{url}/vapi/{name}"
    return daten
