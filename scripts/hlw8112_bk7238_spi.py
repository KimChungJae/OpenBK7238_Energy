#!/usr/bin/env python3
# BK7238 + HLW8112 SPI — IONE patch v4 (v3 Set3Wire 부팅루프 수정)
from pathlib import Path
import re
import sys

HLW = Path("src/driver/drv_hlw8112.c")
SPI = Path("src/driver/drv_spi.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_SPI_FIX4" in text:
    print("Patch v4 already applied")
    sys.exit(0)

# v3 버그 제거: sddev SPI_DEV_NAME (BEKEN_NEW 미등록) → HardFault/Wdt
text = re.sub(
    r"\nstatic void HLW8112_SPI_Set3Wire\(void\) \{[^}]+\}\n",
    "\n",
    text,
    count=1,
)
text = text.replace(
    "#if PLATFORM_BEKEN_NEW && (PLATFORM_BK7238 || PLATFORM_BK7231N || PLATFORM_BK7252N)\n\tHLW8112_SPI_Set3Wire();\n#endif\n",
    "",
)
text = text.replace("IONE_BK7238_SPI_FIX3", "IONE_BK7238_SPI_FIX4")

# --- Transact: full-duplex (reg + 0xFF 더미) — recv-only -6 회피 ---
if "IONE_BK7238_SPI_FIX4" not in text or "tx_local" not in text:
    transact_pat = re.compile(
        r"int HLW8112_SPI_Transact\(uint8_t \*txBuffer, uint32_t txSize, uint8_t \*rxBuffer, uint32_t rxSize\) \{.*?"
        r"HLW8112_SPI_Txn_End\(\);\s*"
        r"ADDLOG_DEBUG\(LOG_FEATURE_ENERGYMETER, \"HLW8112_SPI_Transact result %d\", Result\);\s*"
        r"return Result;\s*\}",
        re.MULTILINE | re.DOTALL,
    )
    new_transact = """int HLW8112_SPI_Transact(uint8_t *txBuffer, uint32_t txSize, uint8_t *rxBuffer, uint32_t rxSize) {
\t/* IONE_BK7238_SPI_FIX4 */
\tHLW8112_SPI_Txn_Begin();
\tint Result = 0;
#if PLATFORM_BEKEN_NEW && (PLATFORM_BK7238 || PLATFORM_BK7231N || PLATFORM_BK7252N)
\tif (rxSize && rxBuffer) {
\t\tuint8_t tx_local[16];
\t\tuint8_t rx_local[16];
\t\tuint32_t total = txSize + rxSize;
\t\tif (total > sizeof(tx_local))
\t\t\tResult = -2;
\t\telse {
\t\t\tuint32_t i;
\t\t\tfor (i = 0; i < txSize && txBuffer; i++)
\t\t\t\ttx_local[i] = txBuffer[i];
\t\t\tfor (; i < total; i++)
\t\t\t\ttx_local[i] = 0xFF;
\t\t\tResult = SPI_Transmit(tx_local, total, rx_local, total);
\t\t\tif (Result >= 0) {
\t\t\t\tfor (i = 0; i < rxSize; i++)
\t\t\t\t\trxBuffer[i] = rx_local[txSize + i];
\t\t\t}
\t\t}
\t} else if (txSize && txBuffer) {
\t\tResult = SPI_WriteBytes(txBuffer, txSize);
\t}
#else
\tResult = SPI_Transmit(txBuffer, txSize, rxBuffer, rxSize);
#endif
\tHLW8112_SPI_Txn_End();
\tADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_SPI_Transact result %d", Result);
\treturn Result;
}"""
    if not transact_pat.search(text):
        sys.exit("ERROR: HLW8112_SPI_Transact pattern not found")
    text = transact_pat.sub(new_transact, text, count=1)

# SPI mode2 (HLW8112 원래값)
text = text.replace(
    "\tcfg.polarity = SPI_POLARITY_LOW;\n\tcfg.phase = SPI_PHASE_2ND_EDGE; /* IONE_BK7238_SPI_FIX2 BL0942-like */\n\tcfg.wire_mode = SPI_3WIRE_MODE;\n\tcfg.baud_rate = 500000;",
    "\tcfg.polarity = SPI_POLARITY_HIGH;\n\tcfg.phase = SPI_PHASE_1ST_EDGE; /* IONE_BK7238_SPI_FIX4 */\n\tcfg.wire_mode = SPI_3WIRE_MODE;\n\tcfg.baud_rate = HLW8112_SPI_BAUD_RATE;",
    1,
)
if "IONE_BK7238_SPI_FIX4" not in text.split("cfg.phase")[1][:80] if "cfg.phase" in text else "":
    text = text.replace(
        "\tcfg.polarity = SPI_POLARITY_HIGH;\n\tcfg.phase = SPI_PHASE_1ST_EDGE;\n\tcfg.wire_mode = SPI_3WIRE_MODE;\n\tcfg.baud_rate = HLW8112_SPI_BAUD_RATE;",
        "\tcfg.polarity = SPI_POLARITY_HIGH;\n\tcfg.phase = SPI_PHASE_1ST_EDGE; /* IONE_BK7238_SPI_FIX4 */\n\tcfg.wire_mode = SPI_3WIRE_MODE;\n\tcfg.baud_rate = HLW8112_SPI_BAUD_RATE;",
        1,
    )

# GPIO mux (P14/P16/P17) — Set3Wire 대신 이것만 (SPILED_Init 과 동일)
if "HLW8112_SPI_EnableGpio" not in text:
    inc_block = """
#if PLATFORM_BEKEN_NEW && (PLATFORM_BK7238 || PLATFORM_BK7231N || PLATFORM_BK7252N)
#include "drv_spidma.h"
static void HLW8112_SPI_EnableGpio(void) {
\tuint32_t val;
\tval = GFUNC_MODE_SPI_USE_GPIO_14;
\tsddev_control(GPIO_DEV_NAME, CMD_GPIO_ENABLE_SECOND, &val);
\tval = GFUNC_MODE_SPI_USE_GPIO_16_17;
\tsddev_control(GPIO_DEV_NAME, CMD_GPIO_ENABLE_SECOND, &val);
\tUINT32 param = PCLK_POSI_SPI;
\tsddev_control(ICU_DEV_NAME, CMD_CONF_PCLK_26M, &param);
\tparam = PWD_SPI_CLK_BIT;
\tsddev_control(ICU_DEV_NAME, CMD_CLK_PWR_UP, &param);
}
#endif
"""
    anchor = "void HLW8112SPI_Init(void) {"
    if anchor not in text:
        sys.exit("ERROR: HLW8112SPI_Init not found")
    text = text.replace(anchor, inc_block + "\n" + anchor, 1)

if "HLW8112_SPI_EnableGpio();" not in text:
    init_call = re.compile(
        r"(void HLW8112SPI_Init\(void\) \{\s*\n\s*HLW8112_Init\(\);\s*\n)"
        r"(\s*SPI_DriverInit\(\);)",
        re.MULTILINE,
    )
    repl = (
        r"\1#if PLATFORM_BEKEN_NEW && (PLATFORM_BK7238 || PLATFORM_BK7231N || PLATFORM_BK7252N)\n"
        r"\tHLW8112_SPI_EnableGpio();\n"
        r"#endif\n"
        r"\2"
    )
    text, n = init_call.subn(repl, text, count=1)
    if n != 1:
        sys.exit("ERROR: HLW8112SPI_Init GPIO call insert failed")

text = text.replace("IONE_BK7238_SPI_FIX2", "IONE_BK7238_SPI_FIX4")
if "IONE_BK7238_SPI_FIX4" not in text:
    text = text.replace("/* IONE_BK7238_SPI_FIX", "/* IONE_BK7238_SPI_FIX4", 1)

if "HLW8112_SPI_Set3Wire" in text:
    sys.exit("ERROR: Set3Wire still present (boot loop risk)")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 patch v4 OK")

# drv_spi.c: recv-only 더미 TX
if SPI.is_file():
    spi = SPI.read_text(encoding="utf-8")
    old_read = """#elif PLATFORM_BEKEN_NEW
\tstruct spi_message msg;
\tmsg.recv_buf = data;
\tmsg.recv_len = size;
\tmsg.send_buf = NULL;
\tmsg.send_len = 0;
\tif(mode == SPI_MASTER)
\t\treturn bk_spi_master_xfer(&msg);"""
    new_read = """#elif PLATFORM_BEKEN_NEW
\tstruct spi_message msg;
\tuint8_t dummy_tx[64];
\tuint32_t n = size;
\tif (n > sizeof(dummy_tx))
\t\tn = sizeof(dummy_tx);
\tmemset(dummy_tx, 0xFF, n);
\tmsg.send_buf = dummy_tx;
\tmsg.send_len = n;
\tmsg.recv_buf = data;
\tmsg.recv_len = size;
\tif(mode == SPI_MASTER)
\t\treturn bk_spi_master_xfer(&msg); /* IONE_BK7238_SPI_FIX4 */"""
    if "IONE_BK7238_SPI_FIX4" not in spi:
        if old_read in spi:
            if "#include <string.h>" not in spi:
                spi = spi.replace(
                    '#include "../logging/logging.h"\n',
                    '#include "../logging/logging.h"\n#include <string.h>\n',
                    1,
                )
            spi = spi.replace(old_read, new_read, 1)
        elif "IONE_BK7238_SPI_FIX3" in spi:
            spi = spi.replace("IONE_BK7238_SPI_FIX3", "IONE_BK7238_SPI_FIX4")
        SPI.write_text(spi, encoding="utf-8")
        print("drv_spi.c ReadBytes dummy-TX patch OK")

print("IONE BK7238 HLW8112 SPI patch v4 applied OK")
