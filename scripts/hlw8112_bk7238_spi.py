#!/usr/bin/env python3
# BK7238 + HLW8112: SPI ReadRegister -6 수정 (PLATFORM_BEKEN_NEW)
from pathlib import Path
import re
import sys

p = Path("src/driver/drv_hlw8112.c")
text = p.read_text(encoding="utf-8")

if "IONE_BK7238_SPI_FIX" in text:
    print("Patch already applied (IONE_BK7238_SPI_FIX)")
    sys.exit(0)

# 1) HLW8112_SPI_Transact — BK7238: 순차 write/read
old_transact = re.compile(
    r"int HLW8112_SPI_Transact\(uint8_t \*txBuffer, uint32_t txSize, uint8_t \*rxBuffer, uint32_t rxSize\) \{\s*"
    r"HLW8112_SPI_Txn_Begin\(\);\s*"
    r"int Result = SPI_Transmit\(txBuffer, txSize, rxBuffer, rxSize\);\s*"
    r"HLW8112_SPI_Txn_End\(\);",
    re.MULTILINE,
)
new_transact = """int HLW8112_SPI_Transact(uint8_t *txBuffer, uint32_t txSize, uint8_t *rxBuffer, uint32_t rxSize) {
\t/* IONE_BK7238_SPI_FIX */
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
    print("ERROR: HLW8112_SPI_Transact pattern not found")
    sys.exit(1)
text = old_transact.sub(new_transact, text, count=1)

# 2) HLW8112_ReadRegister — BK7238: tx/rx 동일 길이(5) full-duplex
old_read = re.compile(
    r"int HLW8112_ReadRegister\(uint8_t reg, uint8_t size, uint32_t \*valueResult\) \{\s*"
    r"uint8_t tx\[1\] = \{0xFF\};\s*"
    r"uint8_t rx\[5\] = \{0\};\s*"
    r"tx\[0\] = reg & 0x7F;\s*"
    r"\s*int result = HLW8112_SPI_Transact\(tx, 1, rx, 5\);",
    re.MULTILINE,
)
new_read = """int HLW8112_ReadRegister(uint8_t reg, uint8_t size, uint32_t *valueResult) {
\tuint8_t tx[5] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
\tuint8_t rx[5] = {0};
\tint result;
#if PLATFORM_BEKEN_NEW
\ttx[0] = reg & 0x7F;
\tHLW8112_SPI_Txn_Begin();
\tresult = SPI_Transmit(tx, 5, rx, 5);
\tHLW8112_SPI_Txn_End();
#else
\ttx[0] = reg & 0x7F;
\tresult = HLW8112_SPI_Transact(tx, 1, rx, 5);
#endif"""

if not old_read.search(text):
    print("ERROR: HLW8112_ReadRegister pattern not found")
    sys.exit(1)
text = old_read.sub(new_read, text, count=1)

# 3) SPI 초기화 — HLW8112 mode3, 속도 낮춤, 4-wire (CS는 GPIO)
text = text.replace(
    "\tcfg.polarity = SPI_POLARITY_HIGH;\n\tcfg.phase = SPI_PHASE_1ST_EDGE;\n\tcfg.wire_mode = SPI_3WIRE_MODE;\n\tcfg.baud_rate = HLW8112_SPI_BAUD_RATE;",
    "\tcfg.polarity = SPI_POLARITY_HIGH;\n\tcfg.phase = SPI_PHASE_2ND_EDGE; /* IONE_BK7238_SPI_FIX mode3 */\n\tcfg.wire_mode = SPI_4WIRE_MODE;\n\tcfg.baud_rate = 500000; /* IONE_BK7238_SPI_FIX was HLW8112_SPI_BAUD_RATE */",
    1,
)

p.write_text(text, encoding="utf-8")
print("IONE BK7238 HLW8112 SPI patch applied OK")
