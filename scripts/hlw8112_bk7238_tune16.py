#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v16 (전 레지스터 SPI off=0 + spireg 진단)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX16" in text:
    print("Patch v16 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX15" not in text:
    sys.exit("ERROR: apply spifix15 first")

old_rx = """static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t reg, uint8_t size) {
\t(void)rx;
\t(void)reg;
\tif (size == 3)
\t\treturn 0;
\treturn 1;
}"""

new_rx = """static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t reg, uint8_t size) {
\t(void)rx;
\t(void)reg;
\t(void)size;
\t/* BK7238 3-wire SPI: 유효 데이터는 rx[0]부터 (RMSU와 동일) */
\treturn 0;
}"""

if old_rx not in text:
    sys.exit("ERROR: RxOffset block not found")
text = text.replace(old_rx, new_rx, 1)

insert_before = """static commandResult_t HLW8112_CmdUfreqDbg(const void *context, const char *cmd, const char *args, int cmdFlags) {"""

new_fn = """static uint32_t HLW8112_BK7238_ParseAt(const uint8_t *rx, int off, uint8_t size) {
\tif (size == 4)
\t\treturn ((uint32_t)rx[off] << 24) | ((uint32_t)rx[off + 1] << 16)
\t\t       | ((uint32_t)rx[off + 2] << 8) | (uint32_t)rx[off + 3];
\tif (size == 3)
\t\treturn ((uint32_t)rx[off] << 16) | ((uint32_t)rx[off + 1] << 8) | (uint32_t)rx[off + 2];
\tif (size == 2)
\t\treturn ((uint32_t)rx[off] << 8) | (uint32_t)rx[off + 1];
\treturn (uint32_t)rx[off];
}

static commandResult_t HLW8112_CmdSpiRegDbg(const void *context, const char *cmd, const char *args, int cmdFlags) {
\tstatic const struct { uint8_t reg; uint8_t sz; const char *nm; } tbl[] = {
\t\t{ HLW8112_REG_RMSU, 3, "RMSU" },
\t\t{ HLW8112_REG_UFREQ, 2, "UFREQ" },
\t\t{ HLW8112_REG_RMSIA, 3, "RMSIA" },
\t\t{ HLW8112_REG_RMSIB, 3, "RMSIB" },
\t\t{ HLW8112_REG_POWER_PA, 4, "POWER_PA" },
\t\t{ HLW8112_REG_RMSIAC, 2, "RMSIAC" },
\t\t{ HLW8112_REG_RMSIBC, 2, "RMSIBC" },
\t\t{ HLW8112_REG_RMSUC, 2, "RMSUC" },
\t\t{ HLW8112_REG_POWER_PAC, 2, "POWER_PAC" },
\t};
\tuint8_t tx[1];
\tint i;
\t(void)context; (void)cmd; (void)args; (void)cmdFlags;
\tfor (i = 0; i < (int)(sizeof(tbl) / sizeof(tbl[0])); i++) {
\t\tuint8_t rx[5] = { 0 };
\t\ttx[0] = tbl[i].reg & 0x7F;
\t\tHLW8112_SPI_Transact(tx, 1, rx, 5);
\t\tADDLOG_INFO(LOG_FEATURE_CMD,
\t\t\t"SPI %s reg=%02X rx=%02X %02X %02X %02X %02X off0=%u off1=%u",
\t\t\ttbl[i].nm, tbl[i].reg, rx[0], rx[1], rx[2], rx[3], rx[4],
\t\t\t(unsigned)HLW8112_BK7238_ParseAt(rx, 0, tbl[i].sz),
\t\t\t(unsigned)HLW8112_BK7238_ParseAt(rx, 1, tbl[i].sz));
\t}
\tHLW8112_UpdateCoeff();
\tADDLOG_INFO(LOG_FEATURE_CMD,
\t\t"scale v=%.6f ia=%.6f ib=%.6f pa=%.6f pb=%.6f frq=%.1f CLKI=%u",
\t\tdevice.ScaleFactor.v_rms, device.ScaleFactor.a.i, device.ScaleFactor.b.i,
\t\tdevice.ScaleFactor.a.p, device.ScaleFactor.b.p, device.ScaleFactor.freq,
\t\t(unsigned)device.CLKI);
\treturn CMD_RES_OK;
}

"""

if insert_before not in text:
    sys.exit("ERROR: CmdUfreqDbg anchor not found")
text = text.replace(insert_before, new_fn + insert_before, 1)

old_reg = "\tCMD_RegisterCommand(\"HLW8112_ufreq\", HLW8112_CmdUfreqDbg, NULL);"
new_reg = """\tCMD_RegisterCommand("HLW8112_ufreq", HLW8112_CmdUfreqDbg, NULL);
\tCMD_RegisterCommand("HLW8112_spireg", HLW8112_CmdSpiRegDbg, NULL);"""

if old_reg not in text:
    sys.exit("ERROR: ufreq CMD register not found")
text = text.replace(old_reg, new_reg, 1)

text = text.replace("IONE_BK7238_REGFIX15", "IONE_BK7238_REGFIX16")
text = text.replace("/* IONE_BK7238_REGFIX15:", "/* IONE_BK7238_REGFIX16:")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v16 OK")
