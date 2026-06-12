#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v19 (SPI gap 10ms + Transact 전후 + FF 재시도)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX19" in text:
    print("Patch v19 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX18" not in text and "IONE_BK7238_REGFIX19" not in text:
    sys.exit("ERROR: apply spifix18 first")

old_gap = """/* IONE_BK7238_REGFIX18: 연속 read 시 2번째부터 MISO=0xFF — HLW8112 read 간격 */
static void HLW8112_BK7238_RegGap(void) {
\trtos_delay_milliseconds(5);
}"""

new_gap = """/* IONE_BK7238_REGFIX19: HLW8112 SPI 프레임 간 CS-high 유지 (10ms) */
static void HLW8112_BK7238_RegGap(void) {
\trtos_delay_milliseconds(10);
}

static int HLW8112_BK7238_RxAllFF(const uint8_t *rx) {
\treturn rx[0] == 0xFF && rx[1] == 0xFF && rx[2] == 0xFF;
}"""

if old_gap not in text:
    sys.exit("ERROR: RegGap block not found")
text = text.replace(old_gap, new_gap, 1)

old_xfer = """\t}
\tif (rxSize && rx) {
\t\tfor (i = 0; i < rxSize; i++) {"""

new_xfer = """\t}
\tif (rxSize && rx) {
\t\trtos_delay_milliseconds(1);
\t\tfor (i = 0; i < rxSize; i++) {"""

if old_xfer not in text:
    sys.exit("ERROR: PollXfer rx block not found")
text = text.replace(old_xfer, new_xfer, 1)

old_transact = """int HLW8112_SPI_Transact(uint8_t *txBuffer, uint32_t txSize, uint8_t *rxBuffer, uint32_t rxSize) {
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

new_transact = """int HLW8112_SPI_Transact(uint8_t *txBuffer, uint32_t txSize, uint8_t *rxBuffer, uint32_t rxSize) {
\t/* IONE_BK7238_SPI_FIX5 */
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tHLW8112_BK7238_RegGap();
#endif
\tHLW8112_SPI_Txn_Begin();
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tint Result = HLW8112_BK7238_PollXfer((const uint8_t *)txBuffer, txSize, rxBuffer, rxSize);
#else
\tint Result = SPI_Transmit(txBuffer, txSize, rxBuffer, rxSize);
#endif
\tHLW8112_SPI_Txn_End();
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tHLW8112_BK7238_RegGap();
#endif
\tADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_SPI_Transact result %d", Result);
\treturn Result;
}"""

if old_transact not in text:
    sys.exit("ERROR: SPI_Transact block not found")
text = text.replace(old_transact, new_transact, 1)

old_read = """\ttx[0] = reg & 0x7F;
\t
\tint result = HLW8112_SPI_Transact(tx, 1, rx, 5);
  	if (result < 0) {"""

new_read = """\ttx[0] = reg & 0x7F;
\t
\tint result = HLW8112_SPI_Transact(tx, 1, rx, 5);
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tif (result >= 0 && HLW8112_BK7238_RxAllFF(rx))
\t\tHLW8112_SPI_Transact(tx, 1, rx, 5);
#endif
  	if (result < 0) {"""

if old_read not in text:
    sys.exit("ERROR: ReadRegister transact block not found")
text = text.replace(old_read, new_read, 1)

old_rr = """\tif (reg == HLW8112_REG_UFREQ && size == 2)
\t\tHLW8112_LogUfreqRxOnce(rx, value, off, ufreqLe);
\tHLW8112_BK7238_RegGap();
#endif
  	return result;
}"""

new_rr = """\tif (reg == HLW8112_REG_UFREQ && size == 2)
\t\tHLW8112_LogUfreqRxOnce(rx, value, off, ufreqLe);
#endif
  	return result;
}"""

if old_rr not in text:
    sys.exit("ERROR: ReadRegister RegGap tail not found")
text = text.replace(old_rr, new_rr, 1)

old_wr = """\tint result = HLW8112_SPI_WriteBytes(tx, size + 1);
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tHLW8112_BK7238_RegGap();
#endif
  	//TODO: verify written bytes register"""

new_wr = """\tint result = HLW8112_SPI_WriteBytes(tx, size + 1);
  	//TODO: verify written bytes register"""

if old_wr not in text:
    sys.exit("ERROR: WriteRegister RegGap not found")
text = text.replace(old_wr, new_wr, 1)

old_spi = """\t\tHLW8112_SPI_Transact(tx, 1, rx, 5);
\t\tHLW8112_BK7238_RegGap();
\t\tADDLOG_INFO(LOG_FEATURE_CMD,"""

new_spi = """\t\tHLW8112_SPI_Transact(tx, 1, rx, 5);
\t\tADDLOG_INFO(LOG_FEATURE_CMD,"""

if old_spi not in text:
    sys.exit("ERROR: CmdSpiRegDbg gap not found")
text = text.replace(old_spi, new_spi, 1)

text = text.replace("IONE_BK7238_REGFIX18", "IONE_BK7238_REGFIX19")
text = text.replace("/* IONE_BK7238_REGFIX18:", "/* IONE_BK7238_REGFIX19:")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v19 OK")
