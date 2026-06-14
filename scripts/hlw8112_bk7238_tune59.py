#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v59 (clear_energy Today 0, 일일 flash 오염 복구)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX59" in text:
    print("Patch v59 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX58" not in text:
    sys.exit("ERROR: apply spifix58 first")

need = [
    "IONE_BK7238_REGFIX59",
    "HLW8112_ClearDailyEnergyBoth",
    "HLW8112_SanitizeDailyEnergy",
    "HLW8112_TODAY_SANITY_KWH",
    "Import/Export/Today=0",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v59 OK")
