#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v54 (MQTT topic base: IONE-Energy-Meta-2CH 하이픈 형식)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")
MAIN = Path("src/user_main.c")

if not HLW.is_file() or not MAIN.is_file():
    sys.exit("ERROR: source files not found")

hlw = HLW.read_text(encoding="utf-8")
main = MAIN.read_text(encoding="utf-8")

if "IONE_BK7238_REGFIX54" in hlw and "IONE-Energy-Meta-2CH" in main:
    print("Patch v54 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX53" not in hlw:
    sys.exit("ERROR: apply spifix53 first")

need = [
    "IONE_BK7238_REGFIX54",
    "IONE-Energy-Meta-2CH",
    "IONE_TopicBaseMatches",
    "IONE_ApplyMqttTopicMacSuffix",
]
for s in need:
    if s not in main and s not in hlw:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v54 OK (MQTT topic hyphen base)")
