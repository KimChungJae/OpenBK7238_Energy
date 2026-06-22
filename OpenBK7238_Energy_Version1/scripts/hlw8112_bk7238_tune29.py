#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v29 (spireg hang/reboot: SPI mutex + 경량화)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX29" in text:
    print("Patch v29 already applied")
    sys.exit(0)

if "Energy_Meta_2CH" not in text:
    sys.exit("ERROR: apply spifix28 first")

need = [
    "IONE_BK7238_REGFIX29",
    "g_hlw8112_spi_mtx",
    "HLW8112_SpiLock",
    "scale(cached)",
    "3초 후 다시 실행",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r} — apply spifix29 source changes to drv_hlw8112.c")

print("HLW8112 regfix v29 OK (spireg SPI mutex)")
