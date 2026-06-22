#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v61 (Energy Total 채널별 월 누적)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX61" in text:
    print("Patch v61 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX60" not in text:
    sys.exit("ERROR: apply spifix60 first")

need = [
    "IONE_BK7238_REGFIX61",
    "EnergyTotal_A",
    "EnergyTotal_B",
    "HLW8112_MONTH_B_ENV",
    'CMD_RegisterCommand("EnergyTotal"',
    '"Energy Total", "kWh"',
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v61 OK")
