#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v17 (RxOffset: 24-bit=0, 16/32-bit=1 복원 + spireg 유지)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX17" in text or "IONE_BK7238_REGFIX18" in text:
    print("Patch v17/v18 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX16" not in text and "IONE_BK7238_REGFIX17" not in text:
    sys.exit("ERROR: apply spifix16 first")

old_rx = """static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t reg, uint8_t size) {
\t(void)rx;
\t(void)reg;
\t(void)size;
\t/* BK7238 3-wire SPI: 유효 데이터는 rx[0]부터 (RMSU와 동일) */
\treturn 0;
}"""

new_rx = """static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t reg, uint8_t size) {
\t(void)rx;
\t(void)reg;
\t/* 24-bit(RMSU/RMSIA 등): rx[0]~ / 16·32-bit: rx[1]~ (spifix16 off=0은 RmsUC 틀어져 152V) */
\tif (size == 3)
\t\treturn 0;
\treturn 1;
}"""

if old_rx not in text:
    sys.exit("ERROR: REGFIX16 RxOffset block not found")
text = text.replace(old_rx, new_rx, 1)

text = text.replace("IONE_BK7238_REGFIX16", "IONE_BK7238_REGFIX17")
text = text.replace("/* IONE_BK7238_REGFIX16:", "/* IONE_BK7238_REGFIX17:")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v17 OK")
