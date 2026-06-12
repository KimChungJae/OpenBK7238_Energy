#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v18 (연속 SPI read 간 5ms gap)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX18" in text or "IONE_BK7238_REGFIX19" in text:
    print("Patch v18/v19 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX17" not in text:
    sys.exit("ERROR: apply spifix17 first")

if '#include "../new_common.h"' not in text:
    text = text.replace(
        '#include "../obk_config.h"',
        '#include "../obk_config.h"\n#include "../new_common.h"',
        1,
    )

gap_fn = """
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
/* IONE_BK7238_REGFIX18: 연속 read 시 2번째부터 MISO=0xFF — HLW8112 read 간격 */
static void HLW8112_BK7238_RegGap(void) {
\trtos_delay_milliseconds(5);
}
#endif
"""

anchor = "#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238\n/* IONE_BK7238_REGFIX17:"
if anchor not in text:
    sys.exit("ERROR: REGFIX17 block not found")
text = text.replace(anchor, gap_fn + anchor, 1)

old_ret = """\tif (reg == HLW8112_REG_UFREQ && size == 2)
\t\tHLW8112_LogUfreqRxOnce(rx, value, off, ufreqLe);
#endif
  	return result;
}"""

new_ret = """\tif (reg == HLW8112_REG_UFREQ && size == 2)
\t\tHLW8112_LogUfreqRxOnce(rx, value, off, ufreqLe);
\tHLW8112_BK7238_RegGap();
#endif
  	return result;
}"""

if old_ret not in text:
    sys.exit("ERROR: ReadRegister return block not found")
text = text.replace(old_ret, new_ret, 1)

old_wr = """\tint result = HLW8112_SPI_WriteBytes(tx, size + 1);
  	//TODO: verify written bytes register
  	return result;
}"""

new_wr = """\tint result = HLW8112_SPI_WriteBytes(tx, size + 1);
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tHLW8112_BK7238_RegGap();
#endif
  	//TODO: verify written bytes register
  	return result;
}"""

if old_wr not in text:
    sys.exit("ERROR: WriteRegister block not found")
text = text.replace(old_wr, new_wr, 1)

old_spi = """\t\tHLW8112_SPI_Transact(tx, 1, rx, 5);
\t\tADDLOG_INFO(LOG_FEATURE_CMD,"""

new_spi = """\t\tHLW8112_SPI_Transact(tx, 1, rx, 5);
\t\tHLW8112_BK7238_RegGap();
\t\tADDLOG_INFO(LOG_FEATURE_CMD,"""

if old_spi not in text:
    sys.exit("ERROR: CmdSpiRegDbg transact block not found")
text = text.replace(old_spi, new_spi, 1)

text = text.replace("IONE_BK7238_REGFIX17", "IONE_BK7238_REGFIX18")
text = text.replace("/* IONE_BK7238_REGFIX17:", "/* IONE_BK7238_REGFIX18:")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v18 OK")
