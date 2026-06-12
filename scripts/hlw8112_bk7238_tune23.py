#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v23 (전력 bit23=부호, INVALID 오판으로 0W 수정)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX23" in text or "IONE_BK7238_REGFIX24" in text:
    print("Patch v23 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX22" not in text:
    sys.exit("ERROR: apply spifix22 first")

parse_fn = """
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
/* IONE_BK7238_REGFIX23: 32-bit 전력 signed — bit23은 부호, INVALID 아님 (0W 고정 버그) */
static int32_t HLW8112_BK7238_ParsePower32(uint32_t raw) {
\tif ((raw & 0x00FFFFFF) == 0x00FFFFFF || raw == 0xFFFFFFFF)
\t\treturn 0;
\treturn (int32_t)raw;
}
#endif

"""

anchor = "#pragma region scalers\n\nvoid HLW8112_ScaleVoltage"
if anchor not in text:
    sys.exit("ERROR: scalers region not found")
text = text.replace("#pragma region scalers\n\nvoid HLW8112_ScaleVoltage", "#pragma region scalers\n" + parse_fn + "void HLW8112_ScaleVoltage", 1)

old_pwr = """void HLW8112_ScalePower(HLW8112_Channel_t channel, uint32_t regValue, int32_t* value){
\tif (regValue == 0) {
\t\t*value = 0;
\t}
\telse if (regValue & HLW8112_INVALID_REGVALUE) {
\t\t*value = 0;
\t}
\telse {
\t\tint32_t rv = (int32_t)regValue;"""

new_pwr = """void HLW8112_ScalePower(HLW8112_Channel_t channel, uint32_t regValue, int32_t* value){
\tif (regValue == 0) {
\t\t*value = 0;
\t}
\telse if ((regValue & 0x00FFFFFF) == 0x00FFFFFF) {
\t\t*value = 0;
\t}
\telse {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\t\tint32_t rv = HLW8112_BK7238_ParsePower32(regValue);
#else
\t\tint32_t rv = (int32_t)regValue;
#endif"""

if old_pwr not in text:
    sys.exit("ERROR: ScalePower block not found")
text = text.replace(old_pwr, new_pwr, 1)

old_ap = """\telse if (regValue & HLW8112_INVALID_REGVALUE) {
\t\t*value = 0;
\t}
\telse {
\t\tint32_t rv = (int32_t)regValue;
\t\tdouble scale = channel == HLW8112_CHANNEL_B ? device.ScaleFactor.b.ap : device.ScaleFactor.a.ap;"""

new_ap = """\telse if ((regValue & 0x00FFFFFF) == 0x00FFFFFF) {
\t\t*value = 0;
\t}
\telse {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\t\tint32_t rv = HLW8112_BK7238_ParsePower32(regValue);
#else
\t\tint32_t rv = (int32_t)regValue;
#endif
\t\tdouble scale = channel == HLW8112_CHANNEL_B ? device.ScaleFactor.b.ap : device.ScaleFactor.a.ap;"""

if old_ap not in text:
    sys.exit("ERROR: ScaleAparentPower block not found")
text = text.replace(old_ap, new_ap, 1)

text = text.replace("/* IONE_BK7238_REGFIX22 */", "/* IONE_BK7238_REGFIX23 */", 1)

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v23 OK")
