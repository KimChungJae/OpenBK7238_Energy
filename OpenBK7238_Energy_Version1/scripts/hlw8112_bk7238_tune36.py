#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v36 (Command Tool OK만 보임 → HTML 직접 출력)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")
LOG = Path("src/logging/logging.c")

for p in (HLW, LOG):
    if not p.is_file():
        sys.exit(f"ERROR: {p} not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX36" in text and "HLW8112_CmdHttpLine" in text:
    print("Patch v36 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX35" not in text:
    sys.exit("ERROR: apply spifix35 first")

need = [
    "IONE_BK7238_REGFIX36",
    "HLW8112_CmdHttpLine",
    "LOG_PostToCmdHttp",
    "driver OFF",
]
for s in need:
    if s not in text and s != "LOG_PostToCmdHttp":
        sys.exit(f"ERROR: drv missing {s!r}")
    if s == "LOG_PostToCmdHttp" and s not in LOG.read_text(encoding="utf-8"):
        sys.exit("ERROR: LOG_PostToCmdHttp missing in logging.c")

print("HLW8112 regfix v36 OK")
