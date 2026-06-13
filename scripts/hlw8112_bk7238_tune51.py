#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v51 (PAGAIN/PBGAIN write verify skip)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX51" in text:
    print("Patch v51 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX50" not in text:
    sys.exit("ERROR: apply spifix50 first")

need = [
    "IONE_BK7238_REGFIX51",
    "PAGAIN/PBGAIN 등 — 쓰기 직후 readback off 어긋남",
    "HLW8112_compute_scale_factor();",
    "Sonoff W 목표",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v51 OK")
