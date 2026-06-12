#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v9 (UFREQ: off 후보 스캔 → 45~70Hz 선택)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX9" in text or "IONE_BK7238_REGFIX10" in text or "IONE_BK7238_REGFIX11" in text or "IONE_BK7238_REGFIX13" in text:
    print("Patch v9/v10 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX8" not in text:
    sys.exit("ERROR: apply spifix8 first")

old_block = """#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
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

new_block = """#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
/* IONE_BK7238_REGFIX9: 24-bit/일반 16-bit off=0/1, UFREQ는 rx 후보 off 스캔 */
static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t reg, uint8_t size) {
\t(void)rx;
\t(void)reg;
\tif (size == 3)
\t\treturn 0;
\treturn 1;
}

static uint32_t HLW8112_BK7238_ParseUfreq(const uint8_t *rx, int *offOut) {
\tuint32_t fallback = ((uint32_t)rx[1] << 8) | (uint32_t)rx[2];
\tdouble frqScale = device.ScaleFactor.freq;
\tif (frqScale <= 0)
\t\tfrqScale = (double)DEFAULT_INTERNAL_CLK * 100.0 / 8.0;
\tfor (int off = 0; off <= 3; off++) {
\t\tuint32_t v = ((uint32_t)rx[off] << 8) | (uint32_t)rx[off + 1];
\t\tif (v == 0 || v >= 0xFF00)
\t\t\tcontinue;
\t\tint32_t hz = (int32_t)(frqScale / (double)v);
\t\tif (hz >= 4500 && hz <= 7000) {
\t\t\tif (offOut)
\t\t\t\t*offOut = off;
\t\t\treturn v;
\t\t}
\t}
\tif (offOut)
\t\t*offOut = 1;
\treturn fallback;
}
#endif"""

if old_block not in text:
    sys.exit("ERROR: REGFIX8 block not found for v9 upgrade")
text = text.replace(old_block, new_block, 1)

old_parse = """\t/* IONE_BK7238_REGFIX8 */
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
  	int off = HLW8112_BK7238_RxOffset(rx, reg, size);
#else
  	int off = 0;
#endif
  	uint32_t value = 0x0;
  	if (size == 4) {
    	value = ((uint32_t)rx[off] << 24) | ((uint32_t)rx[off + 1] << 16)
    	        | ((uint32_t)rx[off + 2] << 8) | ((uint32_t)rx[off + 3]);
  	} else if (size == 3) {
    	value = ((uint32_t)rx[off] << 16) | ((uint32_t)rx[off + 1] << 8) | ((uint32_t)rx[off + 2]);
  	} else if (size == 2) {
    	value = ((uint32_t)rx[off] << 8) | ((uint32_t)rx[off + 1]);
  	} else {
    	value = ((uint32_t)rx[off]);
  	}"""

new_parse = """\t/* IONE_BK7238_REGFIX9 */
  	uint32_t value = 0x0;
  	int off = 0;
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
  	if (reg == HLW8112_REG_UFREQ && size == 2) {
  		value = HLW8112_BK7238_ParseUfreq(rx, &off);
  	} else {
  		off = HLW8112_BK7238_RxOffset(rx, reg, size);
#endif
  	if (size == 4) {
    	value = ((uint32_t)rx[off] << 24) | ((uint32_t)rx[off + 1] << 16)
    	        | ((uint32_t)rx[off + 2] << 8) | ((uint32_t)rx[off + 3]);
  	} else if (size == 3) {
    	value = ((uint32_t)rx[off] << 16) | ((uint32_t)rx[off + 1] << 8) | ((uint32_t)rx[off + 2]);
  	} else if (size == 2) {
    	value = ((uint32_t)rx[off] << 8) | ((uint32_t)rx[off + 1]);
  	} else {
    	value = ((uint32_t)rx[off]);
  	}
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
  	}
#endif"""

if old_parse not in text:
    sys.exit("ERROR: ReadRegister parse block not found")
text = text.replace(old_parse, new_parse, 1)

text = text.replace("IONE_BK7238_REGFIX8", "IONE_BK7238_REGFIX9")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v9 OK")
