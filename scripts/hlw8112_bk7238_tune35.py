#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v35 (KU printf·보정 flash·InitReg 덮어쓰기 방지)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX35" in text and "HLW8112_LoadResistorCoeff" in text:
    print("Patch v35 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX34" not in text:
    sys.exit("ERROR: apply spifix34 first")

need = [
    "IONE_BK7238_REGFIX35",
    "HLW8112_LoadResistorCoeff",
    "HLW8112_SanitizeGain",
    "printf float 미지원",
    "CFG_Save_IfThereArePendingChanges",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v35 OK")
