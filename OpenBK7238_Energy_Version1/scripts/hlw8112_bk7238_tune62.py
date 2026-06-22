#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v62 (Energy Total = month + yesterday + today)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX62" in text:
    print("Patch v62 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX61" not in text:
    sys.exit("ERROR: apply spifix61 first")

need = [
    "IONE_BK7238_REGFIX62",
    "g_hlw8112_month_a + g_hlw8112_yesterday_a + g_hlw8112_today_a",
    "g_hlw8112_month_a += g_hlw8112_yesterday_a",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v62 OK")
