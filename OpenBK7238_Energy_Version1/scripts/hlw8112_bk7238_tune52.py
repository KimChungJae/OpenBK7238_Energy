#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v52 (HLW8112_psgain CLI + PSGAIN verify skip)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX52" in text:
    print("Patch v52 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX51" not in text:
    sys.exit("ERROR: apply spifix51 first")

need = [
    "IONE_BK7238_REGFIX52",
    "HLW8112_CmdPsgain",
    'CMD_RegisterCommand("HLW8112_psgain"',
    "HLW8112_REG_PSGAIN",
    "Sonoff PF 목표",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v52 OK")
