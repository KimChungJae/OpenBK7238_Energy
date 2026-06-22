#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v33 (V=0 회귀: InitReg 반복·bit23 오판·ufreq 실측)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX33" in text and "HLW8112_BK7238_RefreshScaleOnly" in text:
    print("Patch v33 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX32" not in text:
    sys.exit("ERROR: apply spifix32 first")

need = [
    "IONE_BK7238_REGFIX33",
    "HLW8112_BK7238_RefreshScaleOnly",
    "HLW8112_BK7238_FullInitReg",
    "HLW8112_BK7238_Invalid24",
    "HLW8112 live V=",
    "InitReg once (6s)",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

if "PostInitReg" in text:
    sys.exit("ERROR: PostInitReg should be removed in v33")

print("HLW8112 regfix v33 OK")
