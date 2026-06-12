#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v8 (spifix6 전압 복원 + UFREQ만 연속 0xFF 스킵)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX8" in text or "IONE_BK7238_REGFIX9" in text or "IONE_BK7238_REGFIX10" in text or "IONE_BK7238_REGFIX11" in text or "IONE_BK7238_REGFIX12" in text:
    print("Patch v8/v9/v10 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX7" not in text and "IONE_BK7238_REGFIX6" not in text:
    sys.exit("ERROR: apply spifix6/7 first")

old_helper = """#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
/* IONE_BK7238_REGFIX7: 3-wire UFREQ 등 — 선행 0xFF 연속 스킵 (24-bit 전압은 rx[0] 유지) */
static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t size) {
\tint off = 0;
\tif (size == 3)
\t\treturn 0;
\twhile (off + size <= 5 && rx[off] == 0xFF)
\t\toff++;
\treturn off;
}
#endif"""

new_helper = """#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
/* IONE_BK7238_REGFIX8: 24-bit/일반 16-bit는 spifix6(off=0/1), UFREQ만 0xFF 연속 스킵 */
static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t reg, uint8_t size) {
\tint off;
\tif (size == 3)
\t\treturn 0;
\tif (reg == HLW8112_REG_UFREQ && size == 2) {
\t\toff = 0;
\t\twhile (off + size <= 5 && rx[off] == 0xFF)
\t\t\toff++;
\t\treturn off;
\t}
\treturn 1;
}
#endif"""

if old_helper in text:
    text = text.replace(old_helper, new_helper, 1)
elif "HLW8112_BK7238_RxOffset" in text:
    sys.exit("ERROR: REGFIX7 helper pattern not found for v8 upgrade")
else:
    sys.exit("ERROR: HLW8112_BK7238_RxOffset not found")

old_call = "\tint off = HLW8112_BK7238_RxOffset(rx, size);"
new_call = "\tint off = HLW8112_BK7238_RxOffset(rx, reg, size);"
if old_call not in text:
    sys.exit("ERROR: RxOffset call site not found")
text = text.replace(old_call, new_call, 1)

text = text.replace("/* IONE_BK7238_REGFIX7 */", "/* IONE_BK7238_REGFIX8 */", 1)
text = text.replace("IONE_BK7238_REGFIX7", "IONE_BK7238_REGFIX8")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v8 OK")
