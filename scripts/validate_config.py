#!/usr/bin/env python3
"""Prüft die Konfiguration eines Kunden und listet offene Punkte ([OFFEN …]).

  python scripts/validate_config.py kunden/<slug>

Exit-Code 1 bei Fehlern (offene Punkte sind nur Warnungen).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from runtime import config  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    kunden_dir = Path(sys.argv[1])
    try:
        k = config.laden(kunden_dir)
    except config.KonfigFehler as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    offen = []
    for datei in sorted(k.agent_dir.glob("*")):
        if datei.suffix not in (".md", ".json"):
            continue
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\[OFFEN", zeile) or "{{" in zeile:
                offen.append(f"agent/{datei.name}:{nr}: {zeile.strip()[:100]}")
    print(f"✅ {k.firma['name']}: Konfiguration gültig ({len(k.daten['agenten'])} Agenten).")
    if offen:
        print(f"⚠️  {len(offen)} offene Punkte (vor Livegang klären):")
        for o in offen:
            print(f"   {o}")


if __name__ == "__main__":
    main()
