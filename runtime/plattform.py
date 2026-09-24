"""Plattform-Betrieb: EIN Prozess für ALLE Kunden.

  python -m runtime plattform kunden --port 8080

- Jeder Kunde unter /k/<slug>/ (Chat, Widget, Demo, Cockpit, Webhooks, Telefon, Kalender).
- Neue oder geänderte Kunden (kunden/*/agent/*) werden alle 30 s automatisch geladen –
  kein Neustart nötig. Zusammen mit `git pull` per Cron ist jeder neu gebaute Kunde sofort live.
- Zeitplan-Agenten (Lead-Generierung, Nachfassen …) und E-Mail-Posteingänge laufen im Hintergrund
  für alle Kunden mit.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from . import config
from .server import KundenApp, erstelle_server
from .worker import daueraufgabe_starten, email_abrufen, faellige_agenten, imap_zugang

NEU_LADEN_S = 30
EMAIL_INTERVALL_S = 120


class Plattform:
    def __init__(self, kunden_root: str | Path):
        self.root = Path(kunden_root).resolve()
        self.apps: dict[str, KundenApp] = {}
        self._staende: dict[str, float] = {}
        self._fehler: dict[str, str] = {}
        self._lock = threading.Lock()
        self._laufend: set[str] = set()

    # ------------------------------------------------------------------ Kunden laden

    def _stand(self, kunden_dir: Path) -> float:
        return max((f.stat().st_mtime for f in (kunden_dir / "agent").iterdir() if f.is_file()), default=0.0)

    def aktualisieren(self) -> None:
        gefunden = set()
        for d in sorted(self.root.iterdir()):
            if not d.is_dir() or d.name.startswith((".", "_")) or not (d / "agent" / "config.json").exists():
                continue
            gefunden.add(d.name)
            stand = self._stand(d)
            if self._staende.get(d.name) == stand:
                continue
            self._staende[d.name] = stand
            try:
                konfig = config.laden(d)
            except config.KonfigFehler as e:
                if self._fehler.get(d.name) != str(e):
                    print(f"⚠️  {d.name}: nicht geladen – {e}", flush=True)
                    self._fehler[d.name] = str(e)
                continue  # bisherige Version (falls vorhanden) läuft weiter
            self._fehler.pop(d.name, None)
            with self._lock:
                alt = self.apps.get(d.name)
                # Chat-Sitzungen übernehmen, damit laufende Gespräche ein Update überleben
                self.apps[d.name] = KundenApp(konfig, alt.sitzungen if alt else None)
            print(f"{'🔄' if alt else '✅'} {d.name}: {konfig.firma['name']} "
                  f"({', '.join(konfig.daten['agenten'])}){' [Demo]' if konfig.daten.get('demo') else ''}", flush=True)
        with self._lock:
            for weg in set(self.apps) - gefunden:
                del self.apps[weg]
                self._staende.pop(weg, None)
                print(f"➖ {weg}: entfernt", flush=True)

    def aufloesen(self, pfad: str) -> tuple[KundenApp | None, str]:
        teile = pfad.strip("/").split("/", 2)
        if len(teile) >= 2 and teile[0] == "k":
            with self._lock:
                app = self.apps.get(teile[1])
            return app, (teile[2] if len(teile) == 3 else "")
        return None, ""

    # ------------------------------------------------------------------ Hintergrundarbeit

    def _im_hintergrund(self, schluessel: str, fn, *args) -> None:
        """Startet fn in einem Thread – aber nie zweimal gleichzeitig für denselben Schlüssel."""
        with self._lock:
            if schluessel in self._laufend:
                return
            self._laufend.add(schluessel)

        def lauf() -> None:
            try:
                fn(*args)
            except Exception as e:  # ein Kunde darf nie die Plattform stören
                print(f"FEHLER {schluessel}: {type(e).__name__}: {e}", flush=True)
            finally:
                with self._lock:
                    self._laufend.discard(schluessel)

        threading.Thread(target=lauf, daemon=True, name=schluessel).start()

    def hintergrund_schleife(self) -> None:
        letzter_mailabruf = 0.0
        while True:
            try:
                self.aktualisieren()
            except OSError as e:
                print(f"FEHLER beim Laden der Kunden: {e}", flush=True)
            with self._lock:
                apps = dict(self.apps)
            for slug, app in apps.items():
                for agent_name in faellige_agenten(app.k):
                    self._im_hintergrund(f"{slug}/{agent_name}/zeitplan", daueraufgabe_starten, app.k, agent_name)
            if time.time() - letzter_mailabruf >= EMAIL_INTERVALL_S:
                letzter_mailabruf = time.time()
                for slug, app in apps.items():
                    if not imap_zugang(app.k):
                        continue
                    for agent_name, a in app.k.daten["agenten"].items():
                        if "email" in a.get("kanaele", []):
                            agent = app.agent_fuer(agent_name, "email")
                            self._im_hintergrund(f"{slug}/{agent_name}/email", email_abrufen, app.k, agent)
                            break  # ein Postfach pro Kunde: der erste E-Mail-Agent bearbeitet es
            time.sleep(NEU_LADEN_S)


def starten(kunden_root: str | Path, port: int = 8080, host: str = "0.0.0.0") -> None:
    plattform = Plattform(kunden_root)
    plattform.aktualisieren()
    threading.Thread(target=plattform.hintergrund_schleife, daemon=True, name="hintergrund").start()
    server = erstelle_server(plattform.aufloesen, port, host)
    print(f"NG-Customs-Plattform auf http://{host}:{port} – {len(plattform.apps)} Kunden. "
          "Kunden-Adressen: /k/<slug>/demo · /k/<slug>/cockpit", flush=True)
    server.serve_forever()
