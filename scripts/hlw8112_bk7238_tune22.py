#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v22 (계수 reg별 off + 웹 표 min-width)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX22" in text:
    print("Patch v22 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX21" not in text and "IONE_BK7238_REGFIX22" not in text:
    sys.exit("ERROR: apply spifix21 first")

old_off = """/* IONE_BK7238_REGFIX21: 16-bit 계수 CA0B→off0 / F77F→off1 (RMSIAC off=1이면 전류 ~17배 저하) */
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

new_off = """/* IONE_BK7238_REGFIX22: 16-bit 계수 레지스터별 off (0x70/0x71=0, 0x72~=1) + 웹 표 숫자 폭 고정 */
static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t reg, uint8_t size) {
\t(void)rx;
\tif (size == 2) {
\t\tif (reg == HLW8112_REG_RMSIAC || reg == HLW8112_REG_RMSIBC)
\t\t\treturn 0;
\t\treturn 1;
\t}
\treturn 0;
}"""

if old_off not in text:
    sys.exit("ERROR: RxOffset block not found")
text = text.replace(old_off, new_off, 1)

old_row = """void appendTableRow(http_request_t *request, char *name,char* unit, int32_t value, int precision, float factor) {
\thprintf255(request,
        \"<tr><td><b>%s</b></td><td style='text-align: right;'>%.*f</td><td>%s</td></tr>\",
\t\tname,   precision, value / factor, unit);
}"""

new_row = """void appendTableRow(http_request_t *request, char *name,char* unit, int32_t value, int precision, float factor) {
\thprintf255(request,
        \"<tr><td><b>%s</b></td><td style='text-align:right;min-width:8em;font-variant-numeric:tabular-nums;'>%.*f</td><td>%s</td></tr>\",
\t\tname,   precision, value / factor, unit);
}"""

if old_row not in text:
    sys.exit("ERROR: appendTableRow block not found")
text = text.replace(old_row, new_row, 1)

old_ch = """void appendChannelTableRow(http_request_t *request, char *name,char* unit, float value_a, float value_b, int precision, float factor) {
\thprintf255(request,
        \"<tr><td><b>%s</b></td><td style='text-align: right;'>%.*f</td><td>%s</td><td style='text-align: right;'>%.*f</td><td>%s</td></tr>\",
\t\tname, precision, value_a/ factor, unit,precision, value_b/ factor, unit);
}"""

new_ch = """void appendChannelTableRow(http_request_t *request, char *name,char* unit, float value_a, float value_b, int precision, float factor) {
\thprintf255(request,
        \"<tr><td><b>%s</b></td><td style='text-align:right;min-width:7em;font-variant-numeric:tabular-nums;'>%.*f</td><td>%s</td><td style='text-align:right;min-width:7em;font-variant-numeric:tabular-nums;'>%.*f</td><td>%s</td></tr>\",
\t\tname, precision, value_a/ factor, unit,precision, value_b/ factor, unit);
}"""

if old_ch not in text:
    sys.exit("ERROR: appendChannelTableRow block not found")
text = text.replace(old_ch, new_ch, 1)

text = text.replace("/* IONE_BK7238_REGFIX21 */", "/* IONE_BK7238_REGFIX22 */", 1)

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v22 OK")
