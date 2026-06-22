#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v53 (MQTT Client Topic 베이스 + MAC 6hex 자동)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")
IONE = Path("src/driver/drv_ione_energy_mqtt.c")

if not HLW.is_file() or not IONE.is_file():
    sys.exit("ERROR: source files not found")

hlw = HLW.read_text(encoding="utf-8")
ione = IONE.read_text(encoding="utf-8")

if "IONE_BK7238_REGFIX53" in hlw and "IONE_EnergyMqtt_ApplyTopicMacSuffix" in ione:
    print("Patch v53 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX52" not in hlw:
    sys.exit("ERROR: apply spifix52 first")

need_ione = [
    "IONE-Energy-Meta_2CH",
    "IONE-Energy-Meta-2CH",
    "_%02X%02X%02X",
    "mac[3], mac[4], mac[5]",
    "IONE_EnergyMqtt_ApplyTopicMacSuffix",
    "IONE_TopicBaseMatches",
]
for s in need_ione:
    if s not in ione:
        sys.exit(f"ERROR: drv_ione_energy_mqtt.c missing {s!r}")

if "IONE_BK7238_REGFIX53" not in hlw:
    sys.exit("ERROR: drv_hlw8112.c missing 'IONE_BK7238_REGFIX53'")

print("HLW8112 regfix v53 OK (MQTT topic MAC suffix)")
