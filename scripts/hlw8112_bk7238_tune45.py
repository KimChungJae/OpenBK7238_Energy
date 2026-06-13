#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v45 (Web 역률 % 표시)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX45" in text:
    print("Patch v45 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX44" not in text:
    sys.exit("ERROR: apply spifix44 first")

need = [
    "IONE_BK7238_REGFIX45",
    '"Power Factor", "%"',
    "last_update_data.pf, 1, 10.0f",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v45 OK")
