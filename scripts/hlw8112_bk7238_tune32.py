#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v32 (clear_energy 다운: PFCnt verify·flash 연속 쓰기 제거)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")
HAL = Path("src/hal/bk7231/hal_flashVars_bk7231.c")

for p in (HLW, HAL):
    if not p.is_file():
        sys.exit(f"ERROR: {p} not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX32" in text and "HLW8112_ClearEnergyBoth" in text:
    print("Patch v32 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX31" not in text:
    sys.exit("ERROR: apply spifix31 first")

need = [
    "IONE_BK7238_REGFIX32",
    "HLW8112_ClearEnergyBoth",
    "HLW8112_ClearEnergyTryBegin",
    "clear_energy: 3초 간격",
    "PFCnt는 실시간 증가",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: drv missing {s!r}")

if "HAL_FlashVars_SaveEnergyOne" not in HAL.read_text(encoding="utf-8"):
    sys.exit("ERROR: HAL_FlashVars_SaveEnergyOne missing in hal_flashVars_bk7231.c")

print("HLW8112 regfix v32 OK")
