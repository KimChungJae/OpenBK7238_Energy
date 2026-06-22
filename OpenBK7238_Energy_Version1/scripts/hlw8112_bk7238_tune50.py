#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v50 (HLW8112_pagain CLI)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX50" in text and "HLW8112_CmdPagain" in text:
    print("Patch v50 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX49" not in text:
    sys.exit("ERROR: apply spifix49 first")

need = [
    "IONE_BK7238_REGFIX50",
    "HLW8112_CmdPagain",
    'CMD_RegisterCommand("HLW8112_pagain"',
    "HLW8112_UpdateCoeff();",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v50 OK")
