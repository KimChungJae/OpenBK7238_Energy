#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v21 (16-bit RMSIAC/RMSIBC 계수 off=0, 전류 ~17배 저하 수정)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX21" in text or "IONE_BK7238_REGFIX22" in text:
    print("Patch v21 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX20" not in text and "IONE_BK7238_REGFIX21" not in text:
    sys.exit("ERROR: apply spifix20 first")

old_off = """/* IONE_BK7238_REGFIX20: 24·32-bit=rx[0]~ / 16-bit 계수만 rx[1]~ (32-bit off=1 시 rx[4]=0xFF 혼입→전력 -111kW) */
static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t reg, uint8_t size) {
\t(void)rx;
\t(void)reg;
\tif (size == 2)
\t\treturn 1;
\treturn 0;
}"""

new_off = """/* IONE_BK7238_REGFIX21: 16-bit 계수 CA0B→off0 / F77F→off1 (RMSIAC off=1이면 전류 ~17배 저하) */
static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t reg, uint8_t size) {
\t(void)reg;
\tif (size == 2) {
\t\t/* CA 0B 7F FF 패턴: 계수는 rx[0,1] / A4 F7 7F FF: 계수는 rx[1,2] */
\t\tif (rx[2] == 0x7F && rx[3] == 0xFF && rx[0] >= 0xC0)
\t\t\treturn 0;
\t\treturn 1;
\t}
\treturn 0;
}"""

if old_off not in text:
    sys.exit("ERROR: RxOffset block not found")
text = text.replace(old_off, new_off, 1)

text = text.replace("/* IONE_BK7238_REGFIX20 */", "/* IONE_BK7238_REGFIX21 */", 1)

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v21 OK")
