#!/usr/bin/env python3
"""tele/SENSOR JSON 템플릿에 ENERGY 키가 각 1회만 있는지 검증"""
import re
import sys

SRC = "src/driver/drv_ione_energy_mqtt.c"
KEYS = ("EnergyTotal_A", "Power_A", "Today_A", "Voltage", "Current_A", "Time")

text = open(SRC, encoding="utf-8").read()
match = re.search(r"void IONE_EnergyMqtt_PublishTeleSensor\(.*?\n\}", text, re.S)
if not match:
    sys.exit("PublishTeleSensor block not found")

block = match.group(0)
for key in KEYS:
    # snprintf 포맷 문자열은 C 소스에서 \"키\": 형태
    needle = f'\\"{key}\\":'
    count = block.count(needle)
    if count != 1:
        sys.exit(f"SENSOR template key {key}: expected 1, found {count}")

print("SENSOR JSON keys unique OK")
