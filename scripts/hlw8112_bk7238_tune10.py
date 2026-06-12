#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v10 (UFREQ: reg 5500~9500 후보 선택)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if ("IONE_BK7238_REGFIX10" in text or "IONE_BK7238_REGFIX11" in text or "IONE_BK7238_REGFIX12" in text
        or "IONE_BK7238_REGFIX13" in text or "IONE_BK7238_REGFIX14" in text or "IONE_BK7238_REGFIX15" in text or "IONE_BK7238_REGFIX16" in text or "IONE_BK7238_REGFIX17" in text):
    print("Patch v10/v11 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX9" not in text:
    sys.exit("ERROR: apply spifix9 first")

old_fn = """static uint32_t HLW8112_BK7238_ParseUfreq(const uint8_t *rx, int *offOut) {
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
}"""

new_fn = """static uint32_t HLW8112_BK7238_ParseUfreq(const uint8_t *rx, int *offOut) {
\tuint32_t fallback = ((uint32_t)rx[1] << 8) | (uint32_t)rx[2];
\tuint32_t best = 0;
\tint bestOff = 1;
\t/* 60Hz(CLKI=3579545) UFREQ reg 약 7466, 50Hz 약 8959 — 5500~9500 */
\tfor (int off = 0; off <= 3; off++) {
\t\tuint32_t v = ((uint32_t)rx[off] << 8) | (uint32_t)rx[off + 1];
\t\tif (v < 5500 || v > 9500 || v >= 0xFF00)
\t\t\tcontinue;
\t\tif (best == 0 || v < best) {
\t\t\tbest = v;
\t\t\tbestOff = off;
\t\t}
\t}
\tif (best != 0) {
\t\tif (offOut)
\t\t\t*offOut = bestOff;
\t\treturn best;
\t}
\tif (offOut)
\t\t*offOut = bestOff;
\treturn fallback;
}"""

if old_fn not in text:
    sys.exit("ERROR: ParseUfreq v9 block not found")
text = text.replace(old_fn, new_fn, 1)

old_log = """\tADDLOG_INFO(LOG_FEATURE_ENERGYMETER,
\t\t"UFREQ rx %02X %02X %02X %02X %02X off=%d val=%u",
\t\trx[0], rx[1], rx[2], rx[3], rx[4], off, (unsigned)parsed);"""

new_log = """\tADDLOG_INFO(LOG_FEATURE_ENERGYMETER,
\t\t"UFREQ rx %02X %02X %02X %02X %02X off=%d val=%u (Ch1 expect ~6000)",
\t\trx[0], rx[1], rx[2], rx[3], rx[4], off, (unsigned)parsed);"""

if old_log in text:
    text = text.replace(old_log, new_log, 1)

text = text.replace("IONE_BK7238_REGFIX9", "IONE_BK7238_REGFIX10")
text = text.replace("/* IONE_BK7238_REGFIX9:", "/* IONE_BK7238_REGFIX10:")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v10 OK")
