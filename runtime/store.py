"""Kleiner JSON-Dateispeicher mit Dateisperre.

Server, E-Mail-Worker und Zeitplaner laufen oft als getrennte Prozesse und greifen auf dieselben
Dateien in kunden/<slug>/daten/ zu. Deshalb wird jeder Lese-Schreib-Zyklus über eine Lock-Datei
serialisiert (fcntl, Unix). Für ein KMU mit wenigen hundert Leads/Terminen reicht das völlig;
bei Wachstum gegen eine echte Datenbank/CRM-API tauschen.
"""

from __future__ import annotations

import json
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator

try:
    import fcntl
except ImportError:  # Windows: nur prozessinterne Sperre
    fcntl = None

_thread_lock = threading.RLock()


def neue_id(praefix: str) -> str:
    return f"{praefix}-{uuid.uuid4().hex[:8]}"


class JsonStore:
    def __init__(self, daten_dir: Path):
        self.dir = Path(daten_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _sperre(self) -> Iterator[None]:
        with _thread_lock:
            if fcntl is None:
                yield
                return
            with open(self.dir / ".lock", "w") as lf:
                fcntl.flock(lf, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lf, fcntl.LOCK_UN)

    def lesen(self, name: str, default: Any = None) -> Any:
        pfad = self.dir / f"{name}.json"
        with self._sperre():
            if not pfad.exists():
                return default
            return json.loads(pfad.read_text(encoding="utf-8"))

    def aendern(self, name: str, default: Any, fn: Callable[[Any], Any]) -> Any:
        """Liest die Datei, wendet fn auf den Inhalt an und schreibt atomar zurück.

        fn verändert den Inhalt in-place oder gibt einen Rückgabewert zurück, der an den Aufrufer geht.
        """
        pfad = self.dir / f"{name}.json"
        with self._sperre():
            daten = json.loads(pfad.read_text(encoding="utf-8")) if pfad.exists() else default
            ergebnis = fn(daten)
            tmp = pfad.with_suffix(".tmp")
            tmp.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(pfad)
            return ergebnis

    def protokollieren(self, eintrag: dict) -> None:
        """Audit-Log jeder Agenten-Aktion (wichtig bei autonomen Agenten: wer hat wann was getan)."""
        eintrag = {"zeit": datetime.now().isoformat(timespec="seconds"), **eintrag}
        with self._sperre():
            with open(self.dir / "protokoll.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(eintrag, ensure_ascii=False, default=str) + "\n")
