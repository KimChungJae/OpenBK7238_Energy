#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v30 (spireg Command Tool 다운, B채널 지연 기동)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")
UM = Path("src/user_main.c")

for p in (HLW, UM):
    if not p.is_file():
        sys.exit(f"ERROR: {p} not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX30" in text:
    print("Patch v30 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX29" not in text:
    sys.exit("ERROR: apply spifix29 first")

need = [
    "IONE_BK7238_REGFIX30",
    "g_hlw8112_diag_hold",
    "HLW8112_DiagBegin",
    "Command Tool 금지",
    "GPIO_HLW_SCSN = 15",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: drv missing {s!r}")

um = UM.read_text(encoding="utf-8")
if "IONE PM01: HLW8112는 Startup에서 지연 기동" not in um:
    sys.exit("ERROR: user_main defer-start comment missing")

print("HLW8112 regfix v30 OK")
