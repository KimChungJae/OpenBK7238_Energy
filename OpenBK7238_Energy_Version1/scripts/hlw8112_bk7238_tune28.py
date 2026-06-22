#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v28 (MQTT 토픽 Energy_Meta_2CH, Energy_Meta와 분리)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "Energy_Meta_2CH" in text and "IONE_BK7238_REGFIX27" in text:
    print("Patch v28 already applied")
    sys.exit(0)

if "HLW8112_IoneMqttPublishEnergy" not in text:
    sys.exit("ERROR: apply spifix27 first")

text = text.replace(
    '#define IONE_MQTT_ENERGY_TOPIC "Energy_Meta"',
    '#define IONE_MQTT_ENERGY_TOPIC "Energy_Meta_2CH"',
)
text = text.replace(
    "tele/Energy_Meta/SENSOR (Tasmota ENERGY JSON)",
    "tele/Energy_Meta_2CH/SENSOR (2CH 미터 전용, STM32 Energy_Meta와 분리)",
)

if "Energy_Meta_2CH" not in text:
    sys.exit("ERROR: topic replace failed")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v28 OK (Energy_Meta_2CH)")
