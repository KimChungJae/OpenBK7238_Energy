#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v7 (UFREQ: 연속 0xFF 스킵)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX7" in text:
    print("Patch v7 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX6" not in text and "IONE_BK7238_SPI_FIX5" not in text:
    sys.exit("ERROR: apply spifix5/6 first")

helper = """
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
/* IONE_BK7238_REGFIX7: 3-wire UFREQ 등 — 선행 0xFF 연속 스킵 (24-bit 전압은 rx[0] 유지) */
static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t size) {
\tint off = 0;
\tif (size == 3)
\t\treturn 0;
\twhile (off + size <= 5 && rx[off] == 0xFF)
\t\toff++;
\treturn off;
}
#endif
"""

if "HLW8112_BK7238_RxOffset" not in text:
    anchor = "int HLW8112_ReadRegister(uint8_t reg, uint8_t size, uint32_t *valueResult) {"
    if anchor not in text:
        sys.exit("ERROR: HLW8112_ReadRegister not found")
    text = text.replace(anchor, helper + "\n" + anchor, 1)

old_off = """\t/* IONE_BK7238_REGFIX6: 3-wire read 시 선행 0xFF 더미 — 8/16/32-bit는 rx[1]부터 */
  	int off = (size == 3) ? 0 : 1;"""

new_off = """\t/* IONE_BK7238_REGFIX7 */
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
  	int off = HLW8112_BK7238_RxOffset(rx, size);
#else
  	int off = 0;
#endif"""

if old_off not in text:
    # v6 미적용 트리 — 고정 off=1 블록도 교체
    old_off = "\tint off = (size == 3) ? 0 : 1;"
    if old_off not in text:
        sys.exit("ERROR: ReadRegister off block not found")
text = text.replace(old_off, new_off, 1)

# UFREQ 1회 디버그 (loglevel 3에서 rx 확인)
if "HLW8112_LogUfreqRxOnce" not in text:
    log_fn = """
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
static void HLW8112_LogUfreqRxOnce(const uint8_t *rx, uint32_t parsed, int off) {
\tstatic uint8_t done;
\tif (done)
\t\treturn;
\tdone = 1;
\tADDLOG_INFO(LOG_FEATURE_ENERGYMETER,
\t\t"UFREQ rx %02X %02X %02X %02X %02X off=%d val=%u",
\t\trx[0], rx[1], rx[2], rx[3], rx[4], off, (unsigned)parsed);
}
#endif
"""
    text = text.replace(
        "int HLW8112_ReadRegister(uint8_t reg, uint8_t size, uint32_t *valueResult) {",
        log_fn + "\nint HLW8112_ReadRegister(uint8_t reg, uint8_t size, uint32_t *valueResult) {",
        1,
    )
    insert = """\t*valueResult = value;
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tif (reg == HLW8112_REG_UFREQ && size == 2)
\t\tHLW8112_LogUfreqRxOnce(rx, value, off);
#endif
  	return result;"""
    text = text.replace("\t*valueResult = value;\n  	return result;", insert, 1)

text = text.replace("IONE_BK7238_REGFIX6", "IONE_BK7238_REGFIX7")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v7 OK")
