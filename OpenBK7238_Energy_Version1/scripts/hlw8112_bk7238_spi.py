#!/usr/bin/env python3
# BK7238 + HLW8112 SPI — IONE patch v5 (FIFO 폴링, 3-wire write-then-read)
from pathlib import Path
import re
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_SPI_FIX5" in text:
    print("Patch v5 already applied")
    sys.exit(0)

# v3/v4 잔재 제거
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

POLL_BLOCK = """
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
#include "arm_arch.h"
#include "drv_model_pub.h"
#include "gpio_pub.h"
#include "icu_pub.h"
#include "spi_pub.h"
#include "spi_bk7231n.h"

/* IONE_BK7238_SPI_FIX5 — BK7238 DMA SPI 미동작, FIFO 폴링 + 3-wire write-then-read */
static void HLW8112_SPI_EnableGpio(void) {
\tuint32_t val;
\tval = GFUNC_MODE_SPI_GPIO_14;
\tsddev_control(GPIO_DEV_NAME, CMD_GPIO_ENABLE_SECOND, &val);
\tval = GFUNC_MODE_SPI_GPIO_16_17;
\tsddev_control(GPIO_DEV_NAME, CMD_GPIO_ENABLE_SECOND, &val);
\tUINT32 param = PCLK_POSI_SPI;
\tsddev_control(ICU_DEV_NAME, CMD_CONF_PCLK_26M, &param);
\tparam = PWD_SPI_CLK_BIT;
\tsddev_control(ICU_DEV_NAME, CMD_CLK_PWR_UP, &param);
}

static void hlw8112_spi_reg_bit(uint32_t reg, uint32_t bit, int on) {
\tuint32_t v = REG_READ(reg);
\tif (on)
\t\tv |= bit;
\telse
\t\tv &= ~bit;
\tREG_WRITE(reg, v);
}

static void hlw8112_spi_rxfifo_clr(void) {
\tuint32_t st = REG_READ(SPI_STAT);
\twhile (st & RXFIFO_RD_READ) {
\t\tREG_READ(SPI_DAT);
\t\tst = REG_READ(SPI_STAT);
\t}
}

static void hlw8112_spi_txfifo_clr(void) {
\tuint32_t v = REG_READ(SPI_STAT);
\tv |= TXFIFO_CLR_EN;
\tREG_WRITE(SPI_STAT, v);
}

static int hlw8112_spi_write_byte(uint8_t b) {
\tint timeout = 20000;
\twhile (timeout-- > 0) {
\t\tif (REG_READ(SPI_STAT) & TXFIFO_WR_READ) {
\t\t\tREG_WRITE(SPI_DAT, b);
\t\t\treturn 0;
\t\t}
\t}
\treturn -6;
}

static int hlw8112_spi_read_byte(uint8_t *b) {
\tint timeout = 20000;
\twhile (timeout-- > 0) {
\t\tif (REG_READ(SPI_STAT) & RXFIFO_RD_READ) {
\t\t\tif (b)
\t\t\t\t*b = (uint8_t)REG_READ(SPI_DAT);
\t\t\telse
\t\t\t\tREG_READ(SPI_DAT);
\t\t\treturn 0;
\t\t}
\t}
\treturn -6;
}

static void hlw8112_spi_set_clock(uint32_t hz) {
\tconst uint32_t src = 26000000;
\tuint32_t div = src / 2 / hz;
\tif (div < 1)
\t\tdiv = 1;
\tif (div > 255)
\t\tdiv = 255;
\tuint32_t ctrl = REG_READ(SPI_CTRL);
\tctrl &= ~(SPI_CKR_MASK << SPI_CKR_POSI);
\tctrl |= (div << SPI_CKR_POSI);
\tREG_WRITE(SPI_CTRL, ctrl);
}

static void HLW8112_BK7238_PollSpiConfigure(void) {
\tHLW8112_SPI_EnableGpio();
\tREG_WRITE(SPI_CTRL, RXOVR_EN | TXOVR_EN);
\thlw8112_spi_reg_bit(SPI_CTRL, MSTEN, 0);
\thlw8112_spi_reg_bit(SPI_CTRL, BIT_WDTH, 0);
\thlw8112_spi_set_clock(HLW8112_SPI_BAUD_RATE);
\t/* mode2: CPOL=1 CPHA=0 */
\thlw8112_spi_reg_bit(SPI_CTRL, CKPOL, 1);
\thlw8112_spi_reg_bit(SPI_CTRL, CKPHA, 0);
\t/* 3-wire */
\t{
\t\tuint32_t ctrl = REG_READ(SPI_CTRL);
\t\tctrl &= ~CTRL_NSSMD_3;
\t\tctrl |= CTRL_NSSMD_3;
\t\tREG_WRITE(SPI_CTRL, ctrl);
\t}
\thlw8112_spi_reg_bit(SPI_CTRL, TXINT_EN, 0);
\thlw8112_spi_reg_bit(SPI_CTRL, RXINT_EN, 0);
\thlw8112_spi_reg_bit(SPI_CTRL, MSTEN, 1);
\thlw8112_spi_reg_bit(SPI_CTRL, SPIEN, 1);
\t{
\t\tuint32_t cfg = REG_READ(SPI_CONFIG);
\t\tcfg |= SPI_TX_EN | SPI_RX_EN;
\t\tREG_WRITE(SPI_CONFIG, cfg);
\t}
\thlw8112_spi_txfifo_clr();
\thlw8112_spi_rxfifo_clr();
}

static void HLW8112_BK7238_PollSpiShutdown(void) {
\thlw8112_spi_reg_bit(SPI_CTRL, SPIEN, 0);
\tUINT32 param = PWD_SPI_CLK_BIT;
\tsddev_control(ICU_DEV_NAME, CMD_CLK_PWR_DOWN, &param);
}

static int HLW8112_BK7238_PollXfer(const uint8_t *tx, uint32_t txSize, uint8_t *rx, uint32_t rxSize) {
\tuint32_t i;
\tint r;
\thlw8112_spi_txfifo_clr();
\thlw8112_spi_rxfifo_clr();
\tif (txSize && tx) {
\t\tfor (i = 0; i < txSize; i++) {
\t\t\tr = hlw8112_spi_write_byte(tx[i]);
\t\t\tif (r)
\t\t\t\treturn r;
\t\t\tr = hlw8112_spi_read_byte(NULL);
\t\t\tif (r)
\t\t\t\treturn r;
\t\t}
\t}
\tif (rxSize && rx) {
\t\tfor (i = 0; i < rxSize; i++) {
\t\t\tr = hlw8112_spi_write_byte(0xFF);
\t\t\tif (r)
\t\t\t\treturn r;
\t\t\tr = hlw8112_spi_read_byte(&rx[i]);
\t\t\tif (r)
\t\t\t\treturn r;
\t\t}
\t}
\treturn 0;
}
#endif
"""

if "HLW8112_BK7238_PollSpiConfigure" not in text:
    anchor = "void HLW8112_SPI_Txn_Begin(void) {"
    if anchor not in text:
        sys.exit("ERROR: HLW8112_SPI_Txn_Begin not found")
    text = text.replace(anchor, POLL_BLOCK + "\n" + anchor, 1)

# v4 Transact 블록 → v5
transact_v4 = re.compile(
    r"int HLW8112_SPI_Transact\(uint8_t \*txBuffer, uint32_t txSize, uint8_t \*rxBuffer, uint32_t rxSize\) \{"
    r".*?/\* IONE_BK7238_SPI_FIX4 \*/.*?return Result;\s*\}",
    re.MULTILINE | re.DOTALL,
)
transact_std = re.compile(
    r"int HLW8112_SPI_Transact\(uint8_t \*txBuffer, uint32_t txSize, uint8_t \*rxBuffer, uint32_t rxSize\) \{"
    r"\s*HLW8112_SPI_Txn_Begin\(\);\s*"
    r"int Result = SPI_Transmit\(txBuffer, txSize, rxBuffer, rxSize\);\s*"
    r"HLW8112_SPI_Txn_End\(\);\s*"
    r'ADDLOG_DEBUG\(LOG_FEATURE_ENERGYMETER, "HLW8112_SPI_Transact result %d", Result\);\s*'
    r"return Result;\s*\}",
    re.MULTILINE | re.DOTALL,
)

NEW_TRANSACT = """int HLW8112_SPI_Transact(uint8_t *txBuffer, uint32_t txSize, uint8_t *rxBuffer, uint32_t rxSize) {
\t/* IONE_BK7238_SPI_FIX5 */
\tHLW8112_SPI_Txn_Begin();
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tint Result = HLW8112_BK7238_PollXfer((const uint8_t *)txBuffer, txSize, rxBuffer, rxSize);
#else
\tint Result = SPI_Transmit(txBuffer, txSize, rxBuffer, rxSize);
#endif
\tHLW8112_SPI_Txn_End();
\tADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_SPI_Transact result %d", Result);
\treturn Result;
}"""

NEW_WRITE = """int HLW8112_SPI_WriteBytes(uint8_t *data, uint32_t size) {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tint Result = HLW8112_BK7238_PollXfer(data, size, NULL, 0);
#else
\tint Result = SPI_WriteBytes(data, size);
#endif
\tADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_SPI_Write result %x", Result);
\treturn Result;
}"""

NEW_READ = """int HLW8112_SPI_ReadBytes(uint8_t *buffer, uint32_t size) {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tint Result = HLW8112_BK7238_PollXfer(NULL, 0, buffer, size);
#else
\tint Result = SPI_ReadBytes(buffer, size);
#endif
\tADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_SPI_Read result %x", Result);
\treturn Result;
}"""

if transact_v4.search(text):
    text = transact_v4.sub(NEW_TRANSACT, text, count=1)
elif transact_std.search(text):
    text = transact_std.sub(NEW_TRANSACT, text, count=1)
else:
    sys.exit("ERROR: HLW8112_SPI_Transact pattern not found")

write_pat = re.compile(
    r"int HLW8112_SPI_WriteBytes\(uint8_t \*data, uint32_t size\) \{.*?\}",
    re.MULTILINE | re.DOTALL,
)
read_pat = re.compile(
    r"int HLW8112_SPI_ReadBytes\(uint8_t \*buffer, uint32_t size\) \{.*?\}",
    re.MULTILINE | re.DOTALL,
)
if not write_pat.search(text):
    sys.exit("ERROR: HLW8112_SPI_WriteBytes not found")
if not read_pat.search(text):
    sys.exit("ERROR: HLW8112_SPI_ReadBytes not found")
text = write_pat.sub(NEW_WRITE, text, count=1)
text = read_pat.sub(NEW_READ, text, count=1)

# v4 GPIO 블록 제거 (v5 Poll 블록에 통합)
text = re.sub(
    r"\n#if PLATFORM_BEKEN_NEW && \(PLATFORM_BK7238 \|\| PLATFORM_BK7231N \|\| PLATFORM_BK7252N\)\n#include \"drv_spidma\.h\".*?#endif\n",
    "\n",
    text,
    count=1,
    flags=re.DOTALL,
)

# HLW8112SPI_Init — BK7238는 DMA SPI 대신 폴링
init_old = re.compile(
    r"void HLW8112SPI_Init\(void\) \{\s*\n\s*HLW8112_Init\(\);\s*\n"
    r"(?:\s*#if PLATFORM_BEKEN_NEW.*?\n\s*HLW8112_SPI_EnableGpio\(\);\s*\n\s*#endif\s*\n)?"
    r"\s*SPI_DriverInit\(\);\s*\n\s*spi_config_t cfg;.*?OBK_SPI_Init\(&cfg\);\s*\n",
    re.MULTILINE | re.DOTALL,
)
init_new = """void HLW8112SPI_Init(void) {
\tHLW8112_Init();
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tHLW8112_BK7238_PollSpiConfigure();
#else
\tSPI_DriverInit();
\tspi_config_t cfg;
\tcfg.role = SPI_ROLE_MASTER;
\tcfg.bit_width = SPI_BIT_WIDTH_8BITS;
\tcfg.polarity = SPI_POLARITY_HIGH;
\tcfg.phase = SPI_PHASE_1ST_EDGE; /* IONE_BK7238_SPI_FIX5 mode2 */
\tcfg.wire_mode = SPI_3WIRE_MODE;
\tcfg.baud_rate = HLW8112_SPI_BAUD_RATE;
\tcfg.bit_order = SPI_MSB_FIRST;
\tOBK_SPI_Init(&cfg);
#endif
"""
if not init_old.search(text):
    sys.exit("ERROR: HLW8112SPI_Init pattern not found")
text = init_old.sub(init_new, text, count=1)

stop_old = """void HLW8112SPI_Stop(void) {
\tHLW8112_Save_Statistics();
\tSPI_Deinit();
\tSPI_DriverDeinit();
}"""
stop_new = """void HLW8112SPI_Stop(void) {
\tHLW8112_Save_Statistics();
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tHLW8112_BK7238_PollSpiShutdown();
#else
\tSPI_Deinit();
\tSPI_DriverDeinit();
#endif
}"""
if stop_old in text:
    text = text.replace(stop_old, stop_new, 1)

text = text.replace("IONE_BK7238_SPI_FIX4", "IONE_BK7238_SPI_FIX5")
text = text.replace("IONE_BK7238_SPI_FIX3", "IONE_BK7238_SPI_FIX5")
text = text.replace("IONE_BK7238_SPI_FIX2", "IONE_BK7238_SPI_FIX5")

if "HLW8112_SPI_Set3Wire" in text:
    sys.exit("ERROR: Set3Wire still present (boot loop risk)")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 patch v5 OK (BK7238 FIFO polling SPI)")
