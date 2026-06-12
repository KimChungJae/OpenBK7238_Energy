#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v13 (UFREQ: 45~70Hz Hz 스코어링 + ufreq 디버그 CMD)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX13" in text or "IONE_BK7238_REGFIX14" in text or "IONE_BK7238_REGFIX15" in text or "IONE_BK7238_REGFIX16" in text or "IONE_BK7238_REGFIX17" in text:
    print("Patch v13+ already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX12" not in text:
    sys.exit("ERROR: apply spifix12 first")

old_fn = """static uint32_t HLW8112_BK7238_ParseUfreq(const uint8_t *rx, int *offOut, int *leOut) {
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
\t\t*offOut = -1;
\tif (leOut)
\t\t*leOut = -1;
\treturn 0; /* 유효 UFREQ 후보 없음 — 0xFF80 garbage fallback 금지 */
}"""

new_fn = """static void HLW8112_BK7238_TryUfreqHz(const uint8_t *rx, int off, int le, double frqScale,
\t\tuint32_t *best, int *bestOff, int *bestLe, int32_t *bestDiff) {
\tuint32_t v = HLW8112_BK7238_UfreqPair(rx, off, le);
\tint32_t hz, diff;
\tif (v == 0 || v >= 0xFF00)
\t\treturn;
\thz = (int32_t)(frqScale / (double)v);
\tif (hz < 4500 || hz > 7000)
\t\treturn;
\tdiff = hz - 6000;
\tif (diff < 0)
\t\tdiff = -diff;
\tif (*best == 0 || diff < *bestDiff) {
\t\t*best = v;
\t\t*bestOff = off;
\t\t*bestLe = le;
\t\t*bestDiff = diff;
\t}
}

static uint32_t HLW8112_BK7238_ParseUfreq(const uint8_t *rx, int *offOut, int *leOut) {
\tuint32_t best = 0;
\tint bestOff = -1;
\tint bestLe = -1;
\tint32_t bestDiff = 999999;
\tdouble frqScale = device.ScaleFactor.freq;
\tif (frqScale <= 0)
\t\tfrqScale = (double)DEFAULT_INTERNAL_CLK * 100.0 / 8.0;
\t/* off×BE/LE 스캔 + 선행 0xFF 스킵 — 45~70Hz(Ch1 4500~7000)에 가장 가까운 후보 */
\tfor (int off = 0; off <= 3; off++) {
\t\tfor (int le = 0; le <= 1; le++)
\t\t\tHLW8112_BK7238_TryUfreqHz(rx, off, le, frqScale, &best, &bestOff, &bestLe, &bestDiff);
\t}
\t{
\t\tint skip = 0;
\t\twhile (skip < 4 && rx[skip] == 0xFF)
\t\t\tskip++;
\t\tif (skip <= 3) {
\t\t\tHLW8112_BK7238_TryUfreqHz(rx, skip, 0, frqScale, &best, &bestOff, &bestLe, &bestDiff);
\t\t\tHLW8112_BK7238_TryUfreqHz(rx, skip, 1, frqScale, &best, &bestOff, &bestLe, &bestDiff);
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
\t\t*offOut = -1;
\tif (leOut)
\t\t*leOut = -1;
\treturn 0;
}"""

if old_fn not in text:
    sys.exit("ERROR: ParseUfreq v12 block not found")
text = text.replace(old_fn, new_fn, 1)

cmd_anchor = """void HLW8112_addCommads(void){"""
cmd_insert = """#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
static commandResult_t HLW8112_CmdUfreqDbg(const void *context, const char *cmd, const char *args, int cmdFlags) {
\tuint8_t tx[1] = { HLW8112_REG_UFREQ & 0x7F };
\tuint8_t rx[5] = { 0 };
\tint off = -1, le = -1;
\tuint32_t parsed;
\tdouble frqScale;
\tuint32_t ch1;
\t(void)context; (void)cmd; (void)args; (void)cmdFlags;
\tHLW8112_SPI_Transact(tx, 1, rx, 5);
\tparsed = HLW8112_BK7238_ParseUfreq(rx, &off, &le);
\tfrqScale = device.ScaleFactor.freq;
\tif (frqScale <= 0)
\t\tfrqScale = (double)DEFAULT_INTERNAL_CLK * 100.0 / 8.0;
\tch1 = parsed ? (uint32_t)(frqScale / (double)parsed) : 0;
\tADDLOG_INFO(LOG_FEATURE_CMD,
\t\t"UFREQ dbg rx=%02X %02X %02X %02X %02X off=%d le=%d reg=%u Ch1~%u",
\t\trx[0], rx[1], rx[2], rx[3], rx[4], off, le, (unsigned)parsed, (unsigned)ch1);
\treturn CMD_RES_OK;
}
#endif

void HLW8112_addCommads(void){"""

if cmd_anchor not in text:
    sys.exit("ERROR: HLW8112_addCommads anchor not found")
text = text.replace(cmd_anchor, cmd_insert, 1)

reg_anchor = """    CMD_RegisterCommand("clear_energy", HLW8112_ClearEnergy, NULL);
#if HLW8112_SPI_RAWACCESS"""

reg_insert = """    CMD_RegisterCommand("clear_energy", HLW8112_ClearEnergy, NULL);
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tCMD_RegisterCommand("HLW8112_ufreq", HLW8112_CmdUfreqDbg, NULL);
#endif
#if HLW8112_SPI_RAWACCESS"""

if reg_anchor not in text:
    sys.exit("ERROR: clear_energy register anchor not found")
text = text.replace(reg_anchor, reg_insert, 1)

text = text.replace("IONE_BK7238_REGFIX12", "IONE_BK7238_REGFIX13")
text = text.replace("/* IONE_BK7238_REGFIX12:", "/* IONE_BK7238_REGFIX13:")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v13 OK")
