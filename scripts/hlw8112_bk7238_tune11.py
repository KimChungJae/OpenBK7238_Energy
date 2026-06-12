#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v11 (UFREQ: BE+LE off 스캔)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX11" in text or "IONE_BK7238_REGFIX12" in text or "IONE_BK7238_REGFIX13" in text or "IONE_BK7238_REGFIX14" in text:
    print("Patch v11/v12 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX10" not in text:
    sys.exit("ERROR: apply spifix10 first")

old_fn = """static uint32_t HLW8112_BK7238_ParseUfreq(const uint8_t *rx, int *offOut) {
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

new_fn = """static uint32_t HLW8112_BK7238_UfreqPair(const uint8_t *rx, int off, int le) {
\tif (le)
\t\treturn ((uint32_t)rx[off + 1] << 8) | (uint32_t)rx[off];
\treturn ((uint32_t)rx[off] << 8) | (uint32_t)rx[off + 1];
}

static uint32_t HLW8112_BK7238_ParseUfreq(const uint8_t *rx, int *offOut, int *leOut) {
\tuint32_t fallback = ((uint32_t)rx[1] << 8) | (uint32_t)rx[2];
\tuint32_t best = 0;
\tint bestOff = 1;
\tint bestLe = 0;
\t/* 60Hz UFREQ reg 약 7466 — BE/LE 모두 스캔 (LE 0x2A1D는 BE로 10781>9500 탈락) */
\tfor (int off = 0; off <= 3; off++) {
\t\tfor (int le = 0; le <= 1; le++) {
\t\t\tuint32_t v = HLW8112_BK7238_UfreqPair(rx, off, le);
\t\t\tif (v < 5500 || v > 9500 || v >= 0xFF00)
\t\t\t\tcontinue;
\t\t\tif (best == 0 || v < best) {
\t\t\t\tbest = v;
\t\t\t\tbestOff = off;
\t\t\t\tbestLe = le;
\t\t\t}
\t\t}
\t}
\tif (best != 0) {
\t\tif (offOut)
\t\t\t*offOut = bestOff;
\t\tif (leOut)
\t\t\t*leOut = bestLe;
\t\treturn best;
\t}
\tif (offOut)
\t\t*offOut = bestOff;
\tif (leOut)
\t\t*leOut = bestLe;
\treturn fallback;
}"""

if old_fn not in text:
    sys.exit("ERROR: ParseUfreq v10 block not found")
text = text.replace(old_fn, new_fn, 1)

old_log_fn = """static void HLW8112_LogUfreqRxOnce(const uint8_t *rx, uint32_t parsed, int off) {
\tstatic uint8_t done;
\tif (done)
\t\treturn;
\tdone = 1;
\tADDLOG_INFO(LOG_FEATURE_ENERGYMETER,
\t\t"UFREQ rx %02X %02X %02X %02X %02X off=%d val=%u (Ch1 expect ~6000)",
\t\trx[0], rx[1], rx[2], rx[3], rx[4], off, (unsigned)parsed);
}"""

new_log_fn = """static void HLW8112_LogUfreqRxOnce(const uint8_t *rx, uint32_t parsed, int off, int le) {
\tstatic uint8_t done;
\tif (done)
\t\treturn;
\tdone = 1;
\tdouble frqScale = device.ScaleFactor.freq;
\tif (frqScale <= 0)
\t\tfrqScale = (double)DEFAULT_INTERNAL_CLK * 100.0 / 8.0;
\tADDLOG_WARN(LOG_FEATURE_ENERGYMETER,
\t\t"UFREQ rx %02X %02X %02X %02X %02X off=%d le=%d val=%u Ch1~%u",
\t\trx[0], rx[1], rx[2], rx[3], rx[4], off, le, (unsigned)parsed,
\t\t(unsigned)(parsed ? (uint32_t)(frqScale / (double)parsed) : 0));
}"""

if old_log_fn not in text:
    sys.exit("ERROR: LogUfreqRxOnce v10 block not found")
text = text.replace(old_log_fn, new_log_fn, 1)

old_read = """\tint off = 0;
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
  \tif (reg == HLW8112_REG_UFREQ && size == 2) {
  \t\tvalue = HLW8112_BK7238_ParseUfreq(rx, &off);
  \t} else {
  \t\toff = HLW8112_BK7238_RxOffset(rx, reg, size);
#endif"""

new_read = """\tint off = 0;
\tint ufreqLe = 0;
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
  \tif (reg == HLW8112_REG_UFREQ && size == 2) {
  \t\tvalue = HLW8112_BK7238_ParseUfreq(rx, &off, &ufreqLe);
  \t} else {
  \t\toff = HLW8112_BK7238_RxOffset(rx, reg, size);
#endif"""

if old_read not in text:
    sys.exit("ERROR: ReadRegister UFREQ call not found")
text = text.replace(old_read, new_read, 1)

old_log_call = "\t\tHLW8112_LogUfreqRxOnce(rx, value, off);"
new_log_call = "\t\tHLW8112_LogUfreqRxOnce(rx, value, off, ufreqLe);"
if old_log_call not in text:
    sys.exit("ERROR: LogUfreqRxOnce call not found")
text = text.replace(old_log_call, new_log_call, 1)

text = text.replace("IONE_BK7238_REGFIX10", "IONE_BK7238_REGFIX11")
text = text.replace("/* IONE_BK7238_REGFIX10:", "/* IONE_BK7238_REGFIX11:")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v11 OK")
