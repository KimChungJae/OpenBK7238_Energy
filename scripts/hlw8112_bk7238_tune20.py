#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v20 (32-bit 전력 레지스터 off=0, ScalePower invalid 차단)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX20" in text or "IONE_BK7238_REGFIX21" in text:
    print("Patch v20 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX19" not in text and "IONE_BK7238_REGFIX20" not in text and "IONE_BK7238_REGFIX21" not in text:
    sys.exit("ERROR: apply spifix19 first")

old_off = """/* IONE_BK7238_REGFIX19: 24-bit/일반 16-bit off=0/1, UFREQ는 rx 후보 off 스캔 */
static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t reg, uint8_t size) {
\t(void)rx;
\t(void)reg;
\t/* 24-bit(RMSU/RMSIA 등): rx[0]~ / 16·32-bit: rx[1]~ (spifix16 off=0은 RmsUC 틀어져 152V) */
\tif (size == 3)
\t\treturn 0;
\treturn 1;
}"""

new_off = """/* IONE_BK7238_REGFIX20: 24·32-bit=rx[0]~ / 16-bit 계수만 rx[1]~ (32-bit off=1 시 rx[4]=0xFF 혼입→전력 -111kW) */
static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t reg, uint8_t size) {
\t(void)rx;
\t(void)reg;
\tif (size == 2)
\t\treturn 1;
\treturn 0;
}"""

if old_off not in text:
    sys.exit("ERROR: RxOffset block not found")
text = text.replace(old_off, new_off, 1)

old_pwr = """void HLW8112_ScalePower(HLW8112_Channel_t channel, uint32_t regValue, int32_t* value){
\tif (regValue == 0) {
\t\t*value = 0;
\t}
\telse {
\t\tint32_t rv = (int32_t)regValue;"""

new_pwr = """void HLW8112_ScalePower(HLW8112_Channel_t channel, uint32_t regValue, int32_t* value){
\tif (regValue == 0) {
\t\t*value = 0;
\t}
\telse if (regValue & HLW8112_INVALID_REGVALUE) {
\t\t*value = 0;
\t}
\telse {
\t\tint32_t rv = (int32_t)regValue;"""

if old_pwr not in text:
    sys.exit("ERROR: ScalePower block not found")
text = text.replace(old_pwr, new_pwr, 1)

old_ap = """void HLW8112_ScaleAparentPower(HLW8112_Channel_t channel, uint32_t regValue, int32_t* value){
\t
\tif (regValue == 0) {
\t\t*value = 0;
\t}
\telse {
\t\tint32_t rv = (int32_t)regValue;"""

new_ap = """void HLW8112_ScaleAparentPower(HLW8112_Channel_t channel, uint32_t regValue, int32_t* value){
\t
\tif (regValue == 0) {
\t\t*value = 0;
\t}
\telse if (regValue & HLW8112_INVALID_REGVALUE) {
\t\t*value = 0;
\t}
\telse {
\t\tint32_t rv = (int32_t)regValue;"""

if old_ap not in text:
    sys.exit("ERROR: ScaleAparentPower block not found")
text = text.replace(old_ap, new_ap, 1)

text = text.replace("/* IONE_BK7238_REGFIX19 */", "/* IONE_BK7238_REGFIX20 */", 1)

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v20 OK")
