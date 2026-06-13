#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v49 (HLW8112_phase SPI 성공=0 오판 수정)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX49" in text and "PHASE verify fail" in text:
    print("Patch v49 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX48" not in text:
    sys.exit("ERROR: apply spifix48 first")

need = [
    "IONE_BK7238_REGFIX49",
    "HLW8112_DiagBeginSlow",
    "PHASE verify fail",
    "(int8_t)w < 0",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v49 OK")
