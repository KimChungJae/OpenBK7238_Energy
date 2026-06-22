#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v54 (MQTT topic base: IONE-Energy-Meta-2CH 하이픈 형식)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")
IONE = Path("src/driver/drv_ione_energy_mqtt.c")

if not HLW.is_file() or not IONE.is_file():
    sys.exit("ERROR: source files not found")

hlw = HLW.read_text(encoding="utf-8")
ione = IONE.read_text(encoding="utf-8")

if "IONE_BK7238_REGFIX54" in hlw and "IONE-Energy-Meta-2CH" in ione:
    print("Patch v54 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX53" not in hlw:
    sys.exit("ERROR: apply spifix53 first")

need = [
    "IONE_BK7238_REGFIX54",
    "IONE-Energy-Meta-2CH",
    "IONE_TopicBaseMatches",
    "IONE_EnergyMqtt_ApplyTopicMacSuffix",
]
for s in need:
    if s not in ione and s not in hlw:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v54 OK (MQTT topic hyphen base)")
