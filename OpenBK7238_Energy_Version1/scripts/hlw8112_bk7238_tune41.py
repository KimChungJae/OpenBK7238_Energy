#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v41 (tele/SENSOR 2CH JSON)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX41" in text and "Power_B" in text:
    print("Patch v41 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX40" not in text:
    sys.exit("ERROR: apply spifix40 first")

need = [
    "IONE_BK7238_REGFIX41",
    "Power_B",
    "Current_B",
    "Total_B",
    "Power_T",
    "Total_T",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v41 OK")
