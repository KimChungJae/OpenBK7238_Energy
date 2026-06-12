#!/usr/bin/env python3
# BK7238 + HLW8112 SPI (ReadRegister -6) — IONE patch v2
from pathlib import Path
import re
import sys

HLW = Path("src/driver/drv_hlw8112.c")
SPI = Path("src/driver/drv_spi.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_SPI_FIX2" in text:
    print("Patch v2 already applied")
    sys.exit(0)

# --- v1 base (skip if v1 already there) ---
if "IONE_BK7238_SPI_FIX" not in text:
    old_transact = re.compile(
        r"int HLW8112_SPI_Transact\(uint8_t \*txBuffer, uint32_t txSize, uint8_t \*rxBuffer, uint32_t rxSize\) \{\s*"
        r"HLW8112_SPI_Txn_Begin\(\);\s*"
        r"int Result = SPI_Transmit\(txBuffer, txSize, rxBuffer, rxSize\);\s*"
        r"HLW8112_SPI_Txn_End\(\);",
        re.MULTILINE,
    )
    new_transact = """int HLW8112_SPI_Transact(uint8_t *txBuffer, uint32_t txSize, uint8_t *rxBuffer, uint32_t rxSize) {
\t/* IONE_BK7238_SPI_FIX2 */
\tHLW8112_SPI_Txn_Begin();
\tint Result = 0;
#if PLATFORM_BEKEN_NEW
\tif (txSize && txBuffer)
\t\tResult = SPI_WriteBytes(txBuffer, txSize);
\tif (Result >= 0 && rxSize && rxBuffer)
\t\tResult = SPI_ReadBytes(rxBuffer, rxSize);
#else
\tResult = SPI_Transmit(txBuffer, txSize, rxBuffer, rxSize);
#endif
\tHLW8112_SPI_Txn_End();"""
    if not old_transact.search(text):
        sys.exit("ERROR: HLW8112_SPI_Transact pattern not found")
    text = old_transact.sub(new_transact, text, count=1)

    # ReadRegister: BK7238도 Transact(1+5) — BL0942SPI 와 동일 순차 방식
    old_read = re.compile(
        r"int HLW8112_ReadRegister\(uint8_t reg, uint8_t size, uint32_t \*valueResult\) \{\s*"
        r"uint8_t tx\[1\] = \{0xFF\};\s*"
        r"uint8_t rx\[5\] = \{0\};\s*"
        r"tx\[0\] = reg & 0x7F;\s*"
        r"\s*int result = HLW8112_SPI_Transact\(tx, 1, rx, 5\);",
        re.MULTILINE,
    )
    if not old_read.search(text):
        # v1 may have changed ReadRegister — normalize back
        old_read_v1 = re.compile(
            r"int HLW8112_ReadRegister\(uint8_t reg, uint8_t size, uint32_t \*valueResult\) \{.*?#endif\s*",
            re.MULTILINE | re.DOTALL,
        )
        new_read = """int HLW8112_ReadRegister(uint8_t reg, uint8_t size, uint32_t *valueResult) {
\tuint8_t tx[1] = {0xFF};
\tuint8_t rx[5] = {0};
\ttx[0] = reg & 0x7F;
\tint result = HLW8112_SPI_Transact(tx, 1, rx, 5);
"""
        if old_read_v1.search(text):
            text = old_read_v1.sub(new_read, text, count=1)
        else:
            sys.exit("ERROR: HLW8112_ReadRegister pattern not found")
    else:
        pass  # already 1+5 transact

    text = text.replace(
        "\tcfg.polarity = SPI_POLARITY_HIGH;\n\tcfg.phase = SPI_PHASE_1ST_EDGE;\n\tcfg.wire_mode = SPI_3WIRE_MODE;\n\tcfg.baud_rate = HLW8112_SPI_BAUD_RATE;",
        "\tcfg.polarity = SPI_POLARITY_LOW;\n\tcfg.phase = SPI_PHASE_2ND_EDGE; /* IONE_BK7238_SPI_FIX2 BL0942-like */\n\tcfg.wire_mode = SPI_3WIRE_MODE;\n\tcfg.baud_rate = 500000;",
        1,
    )
else:
    text = text.replace("IONE_BK7238_SPI_FIX", "IONE_BK7238_SPI_FIX2")
    # v1 SPI mode -> v2 BL0942-like
    text = text.replace(
        "SPI_POLARITY_HIGH;\n\tcfg.phase = SPI_PHASE_2ND_EDGE; /* IONE_BK7238_SPI_FIX mode3 */\n\tcfg.wire_mode = SPI_4WIRE_MODE;",
        "SPI_POLARITY_LOW;\n\tcfg.phase = SPI_PHASE_2ND_EDGE; /* IONE_BK7238_SPI_FIX2 BL0942-like */\n\tcfg.wire_mode = SPI_3WIRE_MODE;",
        1,
    )
    # undo v1 direct 5+5 ReadRegister if present
    old_read_v1 = re.compile(
        r"int HLW8112_ReadRegister\(uint8_t reg, uint8_t size, uint32_t \*valueResult\) \{.*?#endif\s*",
        re.MULTILINE | re.DOTALL,
    )
    new_read = """int HLW8112_ReadRegister(uint8_t reg, uint8_t size, uint32_t *valueResult) {
\tuint8_t tx[1] = {0xFF};
\tuint8_t rx[5] = {0};
\ttx[0] = reg & 0x7F;
\tint result = HLW8112_SPI_Transact(tx, 1, rx, 5);
"""
    if old_read_v1.search(text):
        text = old_read_v1.sub(new_read, text, count=1)

# --- v2: SPI GPIO mux (P14/P16/P17) — SPILED_Init 과 동일 ---
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
    text = text.replace(
        "void HLW8112SPI_Init(void) {\n\tHLW8112_Init();\n\tSPI_DriverInit();",
        "void HLW8112SPI_Init(void) {\n\tHLW8112_Init();\n#if PLATFORM_BEKEN_NEW && (PLATFORM_BK7238 || PLATFORM_BK7231N || PLATFORM_BK7252N)\n\tHLW8112_SPI_EnableGpio();\n#endif\n\tSPI_DriverInit();",
        1,
    )

if "IONE_BK7238_SPI_FIX2" not in text:
    text = text.replace("IONE_BK7238_SPI_FIX", "IONE_BK7238_SPI_FIX2", 1)

HLW.write_text(text, encoding="utf-8")
print("HLW8112 patch v2 OK")

# --- drv_spi.c: bk_spi_driver_init on BEKEN_NEW ---
if SPI.is_file():
    spi = SPI.read_text(encoding="utf-8")
    if "IONE_BK7238_SPI_FIX2" not in spi:
        old = "#elif PLATFORM_BEKEN_NEW\n\treturn 0;"
        new = "#elif PLATFORM_BEKEN_NEW\n\treturn bk_spi_driver_init(); /* IONE_BK7238_SPI_FIX2 */"
        if old in spi:
            spi = spi.replace(old, new, 1)
            SPI.write_text(spi, encoding="utf-8")
            print("drv_spi.c patch v2 OK")
        else:
            print("WARN: drv_spi.c BEKEN_NEW pattern not found — skip")

print("IONE BK7238 HLW8112 SPI patch v2 applied OK")
