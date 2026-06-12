#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v31 (cold boot B채널: InitReg 다중·IB 감시)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX31" in text and "HLW8112_BK7238_WatchChannelB()" in text:
    if "HLW8112_BK7238_WatchChannelB();" in text.split("HLW8112_ScaleAndUpdate")[1][:400]:
        print("Patch v31 already applied")
        sys.exit(0)

need = [
    "IONE_BK7238_REGFIX31",
    "HLW8112_BK7238_WatchChannelB",
    "HLW8112_BK7238_PostInitReg",
    "HLW8112_reinit",
    "rtos_delay_milliseconds(1500)",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

if "HLW8112_BK7238_WatchChannelB();" not in text:
    sys.exit("ERROR: WatchChannelB not called from RunEverySecond")

print("HLW8112 regfix v31 OK")
