#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v25 (RoundChPower 10배 오류 수정)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX25" in text:
    print("Patch v25 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX24" not in text and "HLW8112_RoundChPower" not in text:
    sys.exit("ERROR: apply spifix24 first")

old = """static float HLW8112_RoundChPower(int32_t p_mW) {
\treturn roundf(p_mW / 1000.0f * 10.0f) * 100.0f;
}"""

new = """static float HLW8112_RoundChPower(int32_t p_mW) {
\t/* ChType_Power_div100 + 기존 pa/10 — 채널값×100=W, 0.1W 반올림 */
\treturn roundf(p_mW / 1000.0f * 10.0f) * 10.0f;
}"""

if old not in text:
    if "* 10.0f;" in text and "HLW8112_RoundChPower" in text:
        print("RoundChPower already fixed")
        sys.exit(0)
    sys.exit("ERROR: RoundChPower block not found")

text = text.replace(old, new, 1)
text = text.replace("/* IONE_BK7238_REGFIX24: 채널/MQTT 0.1 단위 반올림",
                    "/* IONE_BK7238_REGFIX25: RoundChPower 스케일 수정\n/* IONE_BK7238_REGFIX24: 채널/MQTT 0.1 단위 반올림", 1)
HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v25 OK")
