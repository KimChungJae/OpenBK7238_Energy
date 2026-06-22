#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v58 (Web 표 5열 정렬·채널 중복 숨김)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX58" in text and "hlw8112-wrap" in text:
    print("Patch v58 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX57" not in text:
    sys.exit("ERROR: apply spifix57 first")

need = [
    "IONE_BK7238_REGFIX58",
    "hlw8112-wrap",
    "HLW8112_AppendWebTableStyles",
    "appendChannelTotalRow",
    "colgroup",
    "g_hiddenChannels",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v58 OK")
