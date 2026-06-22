#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v43 (Today_A/B·Yesterday_A/B, 모듈 일일 에너지)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX43" in text and "Today_A" in text:
    print("Patch v43 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX42" not in text:
    sys.exit("ERROR: apply spifix42 first")

need = [
    "IONE_BK7238_REGFIX43",
    "HLW8112_LoadDailyEnergy",
    "HLW8112_CheckDailyRollover",
    "Today_A",
    "Yesterday_A",
    "Today_B",
    "Yesterday_B",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v43 OK")
