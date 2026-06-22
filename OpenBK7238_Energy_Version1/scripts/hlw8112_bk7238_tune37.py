#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v37 (ufreq F=0: DiagBeginSlow 10ms gap·UFREQ 선읽기)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX37" in text and "HLW8112_DiagBeginSlow" in text:
    print("Patch v37 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX36" not in text:
    sys.exit("ERROR: apply spifix36 first")

need = [
    "IONE_BK7238_REGFIX37",
    "HLW8112_DiagBeginSlow",
    "UFREQ는 SPI gap 10ms 필수",
    "uf=%u",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v37 OK")
