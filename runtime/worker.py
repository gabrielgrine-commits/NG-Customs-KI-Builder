"""Hintergrund-Auslöser: Zeitplan (Daueraufgaben) und E-Mail-Posteingang."""

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


def zeitplan_schleife(konfig: KundenKonfig, einmal_jetzt: str | None = None) -> None:
    """Startet Agenten mit Kanal 'zeitplan' zur konfigurierten Uhrzeit (Minutengenauigkeit).

    Alternative ohne Dauerprozess: System-Cron ruft `python -m runtime auftrag <kunde> <agent>` auf.
    """
    if einmal_jetzt:
        _lauf(konfig, einmal_jetzt)
        return
    store = JsonStore(konfig.daten_dir)
    geplant = {n: a["zeitplan"] for n, a in konfig.daten["agenten"].items() if "zeitplan" in a.get("kanaele", [])}
    print(f"Zeitplaner aktiv für: {', '.join(f'{n} ({z})' for n, z in geplant.items()) or 'keine Agenten'}")
    while True:
        jetzt = datetime.now(ZoneInfo(konfig.zeitzone))
        stempel = f"{jetzt:%Y-%m-%d %H:%M}"
        for name, zp in geplant.items():
            tage = zp.get("tage", WOCHENTAGE[:5])
            if WOCHENTAGE[jetzt.weekday()] in tage and f"{jetzt:%H:%M}" == zp["uhrzeit"]:
                schluessel = f"{name}@{stempel}"

                def vormerken(laeufe: list[str]) -> bool:
                    if schluessel in laeufe:
                        return False  # anderer Prozess hat diesen Lauf schon gestartet
                    laeufe.append(schluessel)
                    del laeufe[:-200]
                    return True

                if store.aendern("zeitplan_laeufe", [], vormerken):
                    _lauf(konfig, name)
        time.sleep(20)


def _lauf(konfig: KundenKonfig, agent_name: str) -> None:
    print(f"[{datetime.now():%H:%M}] Starte Daueraufgabe: {agent_name}")
    try:
        ergebnis = Agent(konfig, agent_name).daueraufgabe()
        print(f"  {len(ergebnis.aktionen)} Aktionen. Bericht:\n{ergebnis.text}\n")
    except AgentFehler as e:
        print(f"  FEHLER: {e}")


def _dekodieren(wert: str | None) -> str:
    return str(make_header(decode_header(wert))) if wert else ""


def _textinhalt(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for teil in msg.walk():
            if teil.get_content_type() == "text/plain" and "attachment" not in str(teil.get("Content-Disposition")):
                return teil.get_payload(decode=True).decode(teil.get_content_charset() or "utf-8", "replace")
        return "[Kein Textinhalt – nur HTML/Anhänge]"
    return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")


def email_schleife(konfig: KundenKonfig, agent_name: str, intervall_s: int = 120, einmal: bool = False) -> None:
    """Liest ungelesene E-Mails per IMAP und lässt den Agenten jede bearbeiten.

    Der Agent antwortet über das Werkzeug email_senden (je nach Konfiguration sofort oder nach Freigabe).
    """
    e = konfig.daten.get("email", {})
    benutzer = os.environ.get(e.get("benutzer_env", ""), "")
    passwort = os.environ.get(e.get("passwort_env", ""), "")
    if not (e.get("imap_host") and benutzer and passwort):
        raise SystemExit("IMAP nicht konfiguriert: email.imap_host sowie die Umgebungsvariablen aus "
                         "email.benutzer_env / email.passwort_env setzen.")
    agent = Agent(konfig, agent_name)
    eigene = {e["absender"].lower(), benutzer.lower()}
    while True:
        with imaplib.IMAP4_SSL(e["imap_host"], int(e.get("imap_port", 993))) as imap:
            imap.login(benutzer, passwort)
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
                    print(f"[{datetime.now():%H:%M}] {absender}: {len(ergebnis.aktionen)} Aktionen – {ergebnis.text[:120]}")
                except AgentFehler as ex:
                    print(f"FEHLER bei Mail von {absender}: {ex} – bleibt ungelesen")
                    imap.store(mid, "-FLAGS", "\\Seen")
        if einmal:
            return
        time.sleep(intervall_s)
