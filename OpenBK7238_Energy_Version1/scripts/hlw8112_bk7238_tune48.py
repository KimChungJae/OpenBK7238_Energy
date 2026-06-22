#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v48 (HLW8112_phase CLI for PHASEA/B)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX48" in text and "HLW8112_CmdPhase" in text:
    print("Patch v48 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX47" not in text:
    sys.exit("ERROR: apply spifix47 first")

need = [
    "IONE_BK7238_REGFIX48",
    "HLW8112_CmdPhase",
    'CMD_RegisterCommand("HLW8112_phase"',
    "HLW8112_WriteRegister8(reg, (uint8_t)val)",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v48 OK")
