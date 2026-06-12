#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v24 (0.1 단위 표시: 227.1V, 3.6A)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")
PINS = Path("src/new_pins.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX24" in text or "HLW8112_RoundChVoltage" in text:
    print("Patch v24 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX23" not in text and "IONE_BK7238_REGFIX24" not in text:
    sys.exit("ERROR: apply spifix23 first")

round_fns = """
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
/* IONE_BK7238_REGFIX24: 채널/MQTT 0.1 단위 반올림 (227.1V, 3.6A) */
static float HLW8112_RoundChVoltage(int32_t v_mV) {
\treturn roundf(v_mV / 1000.0f * 10.0f) * 10.0f;
}
static float HLW8112_RoundChCurrent(int32_t i_mA) {
\treturn roundf(i_mA / 1000.0f * 10.0f) * 100.0f;
}
static float HLW8112_RoundChFreq(int32_t f) {
\treturn roundf(f / 100.0f * 10.0f) * 10.0f;
}
static float HLW8112_RoundChPower(int32_t p_mW) {
\treturn roundf(p_mW / 1000.0f * 10.0f) * 100.0f;
}
static float HLW8112_RoundChPF(int32_t pf) {
\treturn roundf(pf / 1000.0f * 10.0f) * 100.0f;
}
#endif

"""

anchor_fn = "static void HLW8112_ScaleAndUpdate(HLW8112_Data_t* data) {"
if anchor_fn not in text:
    sys.exit("ERROR: ScaleAndUpdate not found")
if "HLW8112_RoundChVoltage" not in text:
    text = text.replace(anchor_fn, round_fns + anchor_fn, 1)

anchor = "\t// update\n\t\n\tCHANNEL_Set(HLW8112_Channel_Voltage, last_update_data.v_rms / 10.0, 0);"
new_set = """\t// update
	
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\tCHANNEL_Set(HLW8112_Channel_Voltage, HLW8112_RoundChVoltage(last_update_data.v_rms), 0);
\tCHANNEL_Set(HLW8112_Channel_Frequency, HLW8112_RoundChFreq(last_update_data.freq), 0);
\tCHANNEL_Set(HLW8112_Channel_PowerFactor, HLW8112_RoundChPF(last_update_data.pf), 0);
\tCHANNEL_Set(HLW8112_Channel_current_B, HLW8112_RoundChCurrent(last_update_data.ib_rms), 0);
\tCHANNEL_Set(HLW8112_Channel_current_A, HLW8112_RoundChCurrent(last_update_data.ia_rms), 0);
\tCHANNEL_Set(HLW8112_Channel_power_B, HLW8112_RoundChPower(last_update_data.pb), 0);
\tCHANNEL_Set(HLW8112_Channel_power_A, HLW8112_RoundChPower(last_update_data.pa), 0);
\tCHANNEL_Set(HLW8112_Channel_apparent_power_A, HLW8112_RoundChPower(last_update_data.ap), 0);
#else
\tCHANNEL_Set(HLW8112_Channel_Voltage, last_update_data.v_rms / 10.0, 0);"""

if anchor not in text:
    sys.exit("ERROR: CHANNEL_Set block not found")
text = text.replace(anchor, new_set, 1)

old_tail = """\tCHANNEL_Set(HLW8112_Channel_apparent_power_A, last_update_data.ap / 10.0, 0);
\tCHANNEL_Set(HLW8112_Channel_export_B"""
new_tail = """\tCHANNEL_Set(HLW8112_Channel_apparent_power_A, last_update_data.ap / 10.0, 0);
#endif
\tCHANNEL_Set(HLW8112_Channel_export_B"""

if old_tail not in text:
    sys.exit("ERROR: CHANNEL_Set tail not found")
text = text.replace(old_tail, new_tail, 1)

old_ui = """\tappendTableRow(request, \"Voltage\", \"V\", last_update_data.v_rms, 2,1000.0f );
\tappendTableRow(request, \"Frequency\", \"Hz\", last_update_data.freq, 2, 100.0f );
\tappendTableRow(request, \"Active Power\", \"W\", last_update_data.pa, 3,1000.0f );
\tappendTableRow(request, \"Apparent Power\", \"VA\", last_update_data.ap, 3, 1000.0f );
\tappendTableRow(request, \"Power Factor\", \"\", last_update_data.pf, 2, 1000.0f );"""

new_ui = """\tappendTableRow(request, \"Voltage\", \"V\", last_update_data.v_rms, 1,1000.0f );
\tappendTableRow(request, \"Frequency\", \"Hz\", last_update_data.freq, 1, 100.0f );
\tappendTableRow(request, \"Active Power\", \"W\", last_update_data.pa, 1,1000.0f );
\tappendTableRow(request, \"Apparent Power\", \"VA\", last_update_data.ap, 1, 1000.0f );
\tappendTableRow(request, \"Power Factor\", \"\", last_update_data.pf, 1, 1000.0f );"""

if old_ui not in text:
    sys.exit("ERROR: appendTableRow block not found")
text = text.replace(old_ui, new_ui, 1)

old_ch = """\tappendChannelTableRow(request, \"Current\", \"mA\", last_update_data.ia_rms, last_update_data.ib_rms, 0,1 );
\tappendChannelTableRow(request, \"Active Power\", \"W\", last_update_data.pa, last_update_data.pb, 3,1000 );"""

new_ch = """\tappendChannelTableRow(request, \"Current\", \"A\", last_update_data.ia_rms, last_update_data.ib_rms, 1,1000 );
\tappendChannelTableRow(request, \"Active Power\", \"W\", last_update_data.pa, last_update_data.pb, 1,1000 );"""

if old_ch not in text:
    sys.exit("ERROR: appendChannelTableRow block not found")
text = text.replace(old_ch, new_ch, 1)

text = text.replace("/* IONE_BK7238_REGFIX23 */", "/* IONE_BK7238_REGFIX24 */", 1)
HLW.write_text(text, encoding="utf-8")

if PINS.is_file():
    pt = PINS.read_text(encoding="utf-8")
    needle = "int ChannelType_GetDecimalPlaces(int type) {\n\tint pl;"
    ins = """int ChannelType_GetDecimalPlaces(int type) {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\t/* IONE HLW8112: 웹/MQTT 0.1 단위 (227.1V, 3.6A) */
\tswitch (type) {
\tcase ChType_Voltage_div100:
\tcase ChType_Current_div1000:
\tcase ChType_Frequency_div100:
\tcase ChType_Power_div100:
\tcase ChType_PowerFactor_div1000:
\t\treturn 1;
\tdefault:
\t\tbreak;
\t}
#endif
\tint pl;"""
    if needle in pt and "IONE HLW8112: 웹/MQTT 0.1 단위" not in pt:
        pt = pt.replace(needle, ins, 1)
        PINS.write_text(pt, encoding="utf-8")

print("HLW8112 regfix v24 OK")
