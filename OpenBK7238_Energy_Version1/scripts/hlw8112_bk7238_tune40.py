#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v40 (teleperiod flash 버그·MQTT 연결 즉시 발행)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX40" in text and "HLW8112_TeleResetTick" in text:
    print("Patch v40 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX39" not in text:
    sys.exit("ERROR: apply spifix39 first")

need = [
    "IONE_BK7238_REGFIX40",
    "HLW8112_TeleResetTick",
    "HLW8112_TeleTryPublish",
    "g_hlw8112_mqtt_was_up",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

if "HLW8112_LoadTelePeriod" in text or "unused_fill1" in text:
    sys.exit("ERROR: spifix40 should remove flash teleperiod load")

print("HLW8112 regfix v40 OK")
