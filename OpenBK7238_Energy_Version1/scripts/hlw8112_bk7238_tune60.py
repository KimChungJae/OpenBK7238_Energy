#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v60 (Web 3열·Channel A/B 우측 정렬)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX60" in text:
    print("Patch v60 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX59" not in text:
    sys.exit("ERROR: apply spifix59 first")

need = ["IONE_BK7238_REGFIX60", "hlw-ch", "Channel A</th>"]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v60 OK")
