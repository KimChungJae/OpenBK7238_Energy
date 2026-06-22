#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v44 (YYYYMMDD 자정·주기 flash)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX44" in text and "HLW8112_LocalYmd" in text:
    print("Patch v44 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX43" not in text:
    sys.exit("ERROR: apply spifix43 first")

need = [
    "IONE_BK7238_REGFIX44",
    "HLW8112_LocalYmd",
    "HLW8112_PeriodicFlashSave",
    "HLW8112_FLASH_PERIOD_SEC",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v44 OK")
