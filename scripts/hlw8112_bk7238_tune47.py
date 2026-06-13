#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v47 (tele/SENSOR = Web MQTT Client Topic)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX47" in text and "mqttTopic = CFG_GetMQTTClientId()" in text:
    print("Patch v47 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX46" not in text:
    sys.exit("ERROR: apply spifix46 first")

need = [
    "IONE_BK7238_REGFIX47",
    "mqttTopic = CFG_GetMQTTClientId()",
    'snprintf(topic, sizeof(topic), "tele/%s", mqttTopic)',
    "teleperiod: tele/%s/SENSOR every %u s",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

if "IONE_MQTT_ENERGY_TOPIC" in text:
    sys.exit("ERROR: remove hardcoded IONE_MQTT_ENERGY_TOPIC (use CFG_GetMQTTClientId)")

print("HLW8112 regfix v47 OK")
