#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v53 (MQTT Client Topic 베이스 + MAC 6hex 자동)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")
MAIN = Path("src/user_main.c")

if not HLW.is_file() or not MAIN.is_file():
    sys.exit("ERROR: source files not found")

hlw = HLW.read_text(encoding="utf-8")
main = MAIN.read_text(encoding="utf-8")

if "IONE_BK7238_REGFIX53" in hlw and "IONE_ApplyMqttTopicMacSuffix" in main:
    print("Patch v53 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX52" not in hlw:
    sys.exit("ERROR: apply spifix52 first")

need_main = [
    "IONE_BK7238_REGFIX53",
    "IONE_ApplyMqttTopicMacSuffix",
    "IONE-Energy-Meta_2CH",
    "_%02X%02X%02X",
    "mac[3], mac[4], mac[5]",
]
for s in need_main:
    if s not in main:
        sys.exit(f"ERROR: user_main.c missing {s!r}")

need_hlw = [
    "IONE_BK7238_REGFIX53",
]
for s in need_hlw:
    if s not in hlw:
        sys.exit(f"ERROR: drv_hlw8112.c missing {s!r}")

print("HLW8112 regfix v53 OK (MQTT topic MAC suffix)")
