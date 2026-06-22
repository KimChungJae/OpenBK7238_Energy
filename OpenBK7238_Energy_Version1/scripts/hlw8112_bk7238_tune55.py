#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v55 (Web Today/Yesterday Energy)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX55" in text:
    print("Patch v55 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX54" not in text:
    sys.exit("ERROR: apply spifix54 first")

need = [
    "IONE_BK7238_REGFIX55",
    'appendChannelTableRow(request, "Today Energy"',
    'appendChannelTableRow(request, "Yesterday Energy"',
    "g_hlw8112_today_a",
    "g_hlw8112_yesterday_b",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v55 OK")
