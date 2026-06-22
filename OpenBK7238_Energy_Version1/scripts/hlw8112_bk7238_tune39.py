#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v39 (teleperiod: 채널 MQTT 1Hz 차단 + flash 저장)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX39" in text and "HLW8112_CH_MQTT_SKIP" in text:
    print("Patch v39 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX38" not in text:
    sys.exit("ERROR: apply spifix38 first")

need = [
    "IONE_BK7238_REGFIX39",
    "HLW8112_CH_MQTT_SKIP",
    "HLW8112_LoadTelePeriod",
    "HLW8112_SaveTelePeriod",
    "unused_fill1",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v39 OK")
