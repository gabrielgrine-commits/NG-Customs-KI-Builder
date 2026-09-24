"""Hintergrund-Auslöser: Zeitplan (Daueraufgaben) und E-Mail-Posteingang.

Die Bausteine faellige_agenten() und email_abrufen() nutzt sowohl der Einzelbetrieb
(`python -m runtime zeitplan|email`) als auch die Plattform für alle Kunden (runtime/plattform.py).
"""

from __future__ import annotations

import email
import imaplib
import os
import time
from datetime import datetime
from email.header import decode_header, make_header
from email.utils import parseaddr
from zoneinfo import ZoneInfo

from .config import WOCHENTAGE, KundenKonfig
from .engine import Agent, AgentFehler
from .store import JsonStore


def faellige_agenten(konfig: KundenKonfig) -> list[str]:
    """Agenten, deren Zeitplan jetzt (diese Minute) dran ist. Jeder Lauf wird nur einmal vergeben –
    auch wenn mehrere Prozesse gleichzeitig prüfen."""
    if konfig.daten.get("demo"):
        return []  # Demo-Kunden arbeiten nicht von selbst
    store = JsonStore(konfig.daten_dir)
    jetzt = datetime.now(ZoneInfo(konfig.zeitzone))
    stempel = f"{jetzt:%Y-%m-%d %H:%M}"
    faellig = []
    for name, a in konfig.daten["agenten"].items():
        zp = a.get("zeitplan") or {}
        if "zeitplan" not in a.get("kanaele", []) or not zp.get("uhrzeit"):
            continue
        if WOCHENTAGE[jetzt.weekday()] not in zp.get("tage", WOCHENTAGE[:5]) or f"{jetzt:%H:%M}" != zp["uhrzeit"]:
            continue
        schluessel = f"{name}@{stempel}"

        def vormerken(laeufe: list[str], schluessel: str = schluessel) -> bool:
            if schluessel in laeufe:
                return False  # anderer Prozess hat diesen Lauf schon gestartet
            laeufe.append(schluessel)
            del laeufe[:-200]
            return True

        if store.aendern("zeitplan_laeufe", [], vormerken):
            faellig.append(name)
    return faellig


def daueraufgabe_starten(konfig: KundenKonfig, agent_name: str) -> None:
    print(f"[{datetime.now():%H:%M}] {konfig.kunden_dir.name}: starte Daueraufgabe {agent_name}", flush=True)
    try:
        ergebnis = Agent(konfig, agent_name).daueraufgabe()
        print(f"  {konfig.kunden_dir.name}/{agent_name}: {len(ergebnis.aktionen)} Aktionen erledigt", flush=True)
    except AgentFehler as e:
        print(f"  FEHLER {konfig.kunden_dir.name}/{agent_name}: {e}", flush=True)


def zeitplan_schleife(konfig: KundenKonfig, einmal_jetzt: str | None = None) -> None:
    """Einzelbetrieb. Alternative ohne Dauerprozess: Cron ruft `python -m runtime auftrag …` auf."""
    if einmal_jetzt:
        daueraufgabe_starten(konfig, einmal_jetzt)
        return
    geplant = {n: a.get("zeitplan") for n, a in konfig.daten["agenten"].items() if "zeitplan" in a.get("kanaele", [])}
    print(f"Zeitplaner aktiv für: {', '.join(f'{n} ({z})' for n, z in geplant.items()) or 'keine Agenten'}")
    while True:
        for name in faellige_agenten(konfig):
            daueraufgabe_starten(konfig, name)
        time.sleep(20)


def _dekodieren(wert: str | None) -> str:
    return str(make_header(decode_header(wert))) if wert else ""


def _textinhalt(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for teil in msg.walk():
            if teil.get_content_type() == "text/plain" and "attachment" not in str(teil.get("Content-Disposition")):
                return teil.get_payload(decode=True).decode(teil.get_content_charset() or "utf-8", "replace")
        return "[Kein Textinhalt – nur HTML/Anhänge]"
    return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")


def imap_zugang(konfig: KundenKonfig) -> tuple[str, str] | None:
    e = konfig.daten.get("email", {})
    benutzer = os.environ.get(e.get("benutzer_env", ""), "")
    passwort = os.environ.get(e.get("passwort_env", ""), "")
    if e.get("imap_host") and benutzer and passwort and not konfig.daten.get("demo"):
        return benutzer, passwort
    return None


def email_abrufen(konfig: KundenKonfig, agent: Agent) -> int:
    """Bearbeitet alle ungelesenen E-Mails einmal. Gibt die Anzahl bearbeiteter Mails zurück."""
    zugang = imap_zugang(konfig)
    if not zugang:
        return 0
    e = konfig.daten["email"]
    eigene = {e.get("absender", "").lower(), zugang[0].lower()}
    anzahl = 0
    with imaplib.IMAP4_SSL(e["imap_host"], int(e.get("imap_port", 993))) as imap:
        imap.login(*zugang)
        imap.select("INBOX")
        _, ids = imap.search(None, "UNSEEN")
        for mid in ids[0].split():
            _, daten = imap.fetch(mid, "(RFC822)")
            msg = email.message_from_bytes(daten[0][1])
            absender = parseaddr(msg.get("From", ""))[1]
            if absender.lower() in eigene or msg.get("Auto-Submitted", "no") != "no":
                continue  # keine Schleifen mit eigenen/automatischen Mails
            betreff = _dekodieren(msg.get("Subject"))
            text = _textinhalt(msg)[:20000]
            auftrag = (f"Neue E-Mail im Posteingang.\nVon: {_dekodieren(msg.get('From'))} <{absender}>\n"
                       f"Betreff: {betreff}\n\n<email_inhalt>\n{text}\n</email_inhalt>\n\n"
                       "Bearbeite diese E-Mail vollständig gemäß deiner Rolle. Antworte der Person per "
                       f"email_senden an {absender} (Betreff mit 'Re: ' beginnen), sofern eine Antwort sinnvoll "
                       "ist. Spam, Werbung und Newsletter nicht beantworten.")
            try:
                ergebnis, _ = agent.ausfuehren(auftrag, kanal="email")
                anzahl += 1
                print(f"[{datetime.now():%H:%M}] {konfig.kunden_dir.name}: Mail von {absender} → "
                      f"{len(ergebnis.aktionen)} Aktionen", flush=True)
            except AgentFehler as ex:
                print(f"FEHLER bei Mail von {absender}: {ex} – bleibt ungelesen", flush=True)
                imap.store(mid, "-FLAGS", "\\Seen")
    return anzahl


def email_schleife(konfig: KundenKonfig, agent_name: str, intervall_s: int = 120, einmal: bool = False) -> None:
    """Einzelbetrieb: Posteingang regelmäßig abrufen."""
    if not imap_zugang(konfig):
        raise SystemExit("IMAP nicht konfiguriert: email.imap_host sowie die Umgebungsvariablen aus "
                         "email.benutzer_env / email.passwort_env setzen (Demo-Kunden rufen keine Mails ab).")
    agent = Agent(konfig, agent_name)
    while True:
        email_abrufen(konfig, agent)
        if einmal:
            return
        time.sleep(intervall_s)
