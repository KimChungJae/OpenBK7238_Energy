#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v38 (teleperiod: tele/Energy_Meta_2CH/SENSOR MQTT 주기)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX38" in text and "HLW8112_CmdTelePeriod" in text:
    print("Patch v38 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX37" not in text:
    sys.exit("ERROR: apply spifix37 first")

need = [
    "IONE_BK7238_REGFIX38",
    "HLW8112_CmdTelePeriod",
    'CMD_RegisterCommand("teleperiod"',
    "g_hlw8112_teleperiod_sec",
    "g_hlw8112_tele_tick",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v38 OK")
