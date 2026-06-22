#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v64 (Web 표 580px·열 좌측 정렬)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX64" in text:
    print("Patch v64 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX63" not in text:
    sys.exit("ERROR: apply spifix63 first")

need = [
    "IONE_BK7238_REGFIX64",
    "max-width:580px",
    "hlw-span",
    "width:30%",
    "<table class='hlw8112-tbl'>",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

if "max-width:520px" in text:
    sys.exit("ERROR: old 520px wrap still present")

if "<div class='hlw8112-wrap'><table" in text:
    sys.exit("ERROR: nested hlw8112-wrap table wrapper still present")

print("HLW8112 regfix v64 OK")
