#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v46 (tele/SENSOR Export_A/B)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX46" in text:
    print("Patch v46 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX45" not in text:
    sys.exit("ERROR: apply spifix45 first")

need = [
    "IONE_BK7238_REGFIX46",
    '"Export_A":%.3f,"Export_B":%.3f',
    "export_a = (float)last_update_data.ea->Export",
    "export_b = (float)last_update_data.eb->Export",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v46 OK")
