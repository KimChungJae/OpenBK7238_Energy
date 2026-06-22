#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v34 (HLW8112_ufreq Command Tool 다운 방지)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX34" in text and "HLW8112_BK7238_ScalePreview" in text:
    print("Patch v34 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX33" not in text:
    sys.exit("ERROR: apply spifix33 first")

need = [
    "IONE_BK7238_REGFIX34",
    "HLW8112_BK7238_ScalePreview",
    "s_ufreq_last_ms",
    "HLW8112_ufreq: 5초 후 다시",
    "CHANNEL_Set·flash·MQTT는 1Hz",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

if "HLW8112_BK7238_MeasureLive" in text:
    sys.exit("ERROR: MeasureLive should be removed in v34")

print("HLW8112 regfix v34 OK")
