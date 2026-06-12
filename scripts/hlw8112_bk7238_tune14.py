#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v14 (UFREQ: CLKI 기준 Hz + 후보 dump)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX14" in text or "IONE_BK7238_REGFIX15" in text or "IONE_BK7238_REGFIX16" in text or "IONE_BK7238_REGFIX17" in text or "IONE_BK7238_REGFIX19" in text:
    print("Patch v14/v15 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX13" not in text:
    sys.exit("ERROR: apply spifix13 first")

old_try = """\tif (v == 0 || v >= 0xFF00)
\t\treturn;
\thz = (int32_t)(frqScale / (double)v);
\tif (hz < 4500 || hz > 7000)
\t\treturn;"""

new_try = """\tif (v == 0 || v >= 0xFF00)
\t\treturn;
\thz = (int32_t)(frqScale / (double)v);
\tif (hz < 3500 || hz > 8000)
\t\treturn;"""

if old_try not in text:
    sys.exit("ERROR: TryUfreqHz range block not found")
text = text.replace(old_try, new_try, 1)

old_scale = """\tdouble frqScale = device.ScaleFactor.freq;
\tif (frqScale <= 0)
\t\tfrqScale = (double)DEFAULT_INTERNAL_CLK * 100.0 / 8.0;
\t/* off×BE/LE 스캔 + 선행 0xFF 스킵 — 45~70Hz(Ch1 4500~7000)에 가장 가까운 후보 */"""

new_scale = """\tdouble frqScale;
\tif (device.CLKI > 0)
\t\tfrqScale = (double)device.CLKI * 100.0 / 8.0;
\telse
\t\tfrqScale = (double)DEFAULT_INTERNAL_CLK * 100.0 / 8.0;
\t/* off×BE/LE 스캔 — 35~80Hz(Ch1 3500~8000)에 60Hz(6000)에 가장 가까운 후보 */"""

if old_scale not in text:
    sys.exit("ERROR: ParseUfreq frqScale block not found")
text = text.replace(old_scale, new_scale, 1)

old_cmd = """static commandResult_t HLW8112_CmdUfreqDbg(const void *context, const char *cmd, const char *args, int cmdFlags) {
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
}"""

new_cmd = """static commandResult_t HLW8112_CmdUfreqDbg(const void *context, const char *cmd, const char *args, int cmdFlags) {
\tuint8_t tx[1] = { HLW8112_REG_UFREQ & 0x7F };
\tuint8_t rx[5] = { 0 };
\tint off = -1, le = -1;
\tuint32_t parsed;
\tdouble frqScale;
\tuint32_t ch1;
\t(void)context; (void)cmd; (void)args; (void)cmdFlags;
\tHLW8112_SPI_Transact(tx, 1, rx, 5);
\tif (device.CLKI > 0)
\t\tfrqScale = (double)device.CLKI * 100.0 / 8.0;
\telse
\t\tfrqScale = (double)DEFAULT_INTERNAL_CLK * 100.0 / 8.0;
\tfor (int o = 0; o <= 3; o++) {
\t\tfor (int l = 0; l <= 1; l++) {
\t\t\tuint32_t v = HLW8112_BK7238_UfreqPair(rx, o, l);
\t\t\tuint32_t hz = v ? (uint32_t)(frqScale / (double)v) : 0;
\t\t\tADDLOG_INFO(LOG_FEATURE_CMD, "  cand off=%d le=%d v=%u hz~%u", o, l, (unsigned)v, (unsigned)hz);
\t\t}
\t}
\tparsed = HLW8112_BK7238_ParseUfreq(rx, &off, &le);
\tch1 = parsed ? (uint32_t)(frqScale / (double)parsed) : 0;
\tADDLOG_INFO(LOG_FEATURE_CMD,
\t\t"UFREQ pick rx=%02X %02X %02X %02X %02X CLKI=%u off=%d le=%d reg=%u Ch1~%u V=%d",
\t\trx[0], rx[1], rx[2], rx[3], rx[4], (unsigned)device.CLKI, off, le,
\t\t(unsigned)parsed, (unsigned)ch1, (int)last_update_data.v_rms);
\treturn CMD_RES_OK;
}"""

if old_cmd not in text:
    sys.exit("ERROR: CmdUfreqDbg block not found")
text = text.replace(old_cmd, new_cmd, 1)

text = text.replace("IONE_BK7238_REGFIX13", "IONE_BK7238_REGFIX14")
text = text.replace("/* IONE_BK7238_REGFIX13:", "/* IONE_BK7238_REGFIX14:")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v14 OK")
