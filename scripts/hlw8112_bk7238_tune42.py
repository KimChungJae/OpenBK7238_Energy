#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v42 (*_A/*_B 키·모듈 합산 제거)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX42" in text and "Current_A" in text:
    print("Patch v42 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX41" not in text:
    sys.exit("ERROR: apply spifix41 first")

need = [
    "IONE_BK7238_REGFIX42",
    "Current_A",
    "Current_B",
    "Power_A",
    "Power_B",
    "Total_A",
    "Total_B",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

if '"Power_T"' in text or '"Total_T"' in text:
    sys.exit("ERROR: spifix42 should remove summed MQTT keys")

print("HLW8112 regfix v42 OK")
