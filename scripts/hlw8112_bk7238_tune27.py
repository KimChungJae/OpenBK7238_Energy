#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v27 (tele/Energy_Meta/SENSOR MQTT 발행)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")
MAIN = Path("src/driver/drv_main.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX27" in text:
    print("Patch v27 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX25" not in text and "HLW8112_RoundChPower" not in text:
    sys.exit("ERROR: apply spifix25 first")

includes = '#include "../libraries/obktime/obktime.h"\n#include "../driver/drv_deviceclock.h"\n'
if "obktime.h" not in text:
    text = text.replace('#include "../mqtt/new_mqtt.h"\n', '#include "../mqtt/new_mqtt.h"\n' + includes, 1)

mqtt_fn = """
/* IONE_BK7238_REGFIX27: STM32/Stream GUI — tele/Energy_Meta/SENSOR (Tasmota ENERGY JSON) */
#ifndef IONE_MQTT_ENERGY_TOPIC
#define IONE_MQTT_ENERGY_TOPIC "Energy_Meta"
#endif

static void HLW8112_IoneMqttPublishEnergy(void) {
\tchar payload[420];
\tconst char *timeStr;
\tfloat v, cur, p, s, pf, freq, total, reactive;
\tchar topic[48];

\tif (!Main_HasMQTTConnected())
\t\treturn;

\tv = last_update_data.v_rms / 1000.0f;
\tcur = last_update_data.ia_rms / 1000.0f;
\tp = last_update_data.pa / 1000.0f;
\ts = last_update_data.ap / 1000.0f;
\tpf = last_update_data.pf / 1000.0f;
\tfreq = last_update_data.freq / 100.0f;
\ttotal = (float)last_update_data.ea->Import;

\t{
\t\tfloat pkw = p / 1000.0f;
\t\tfloat skw = s / 1000.0f;
\t\tfloat q2 = skw * skw - pkw * pkw;
\t\treactive = (q2 > 0.0f) ? sqrtf(q2) * 1000.0f : 0.0f;
\t\tif (p < 0.0f)
\t\t\treactive = -reactive;
\t}

\ttimeStr = TS2STR(TIME_GetCurrentTime(), TIME_FORMAT_ISO_8601);
\tsnprintf(payload, sizeof(payload),
\t\t"{\\"Time\\":\\"%s\\",\\"ENERGY\\":{"
\t\t"\\"Total\\":%.3f,\\"Yesterday\\":0,\\"Today\\":0,"
\t\t"\\"Power\\":%.1f,\\"ApparentPower\\":%.1f,\\"ReactivePower\\":%.1f,"
\t\t"\\"Factor\\":%.2f,\\"Voltage\\":%.1f,\\"Current\\":%.3f,\\"Frequency\\":%.1f}}",
\t\ttimeStr, total, p, s, reactive, pf, v, cur, freq);

\tsnprintf(topic, sizeof(topic), "tele/%s", IONE_MQTT_ENERGY_TOPIC);
\tMQTT_Publish(topic, "SENSOR", payload, 0);
}
"""

anchor = "static float HLW8112_RoundChPF(int32_t pf) {"
if anchor not in text:
    sys.exit("ERROR: RoundChPF not found")

if "HLW8112_IoneMqttPublishEnergy" not in text:
    idx = text.find(anchor)
    end = text.find("\n}\n", idx)
    if end < 0:
        sys.exit("ERROR: RoundChPF end not found")
    end += 3
    text = text[:end] + mqtt_fn + text[end:]

call_old = "    HLW8112_ScaleAndUpdate(&data);\n}"
call_new = "    HLW8112_ScaleAndUpdate(&data);\n#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238\n\tHLW8112_IoneMqttPublishEnergy();\n#endif\n}"
if call_old in text and "HLW8112_IoneMqttPublishEnergy()" not in text:
    text = text.replace(call_old, call_new, 1)

HLW.write_text(text, encoding="utf-8")

if MAIN.is_file():
    mt = MAIN.read_text(encoding="utf-8")
    old = '\t\t|| DRV_IsRunning("RN8209");\n\t\t// || DRV_IsRunning("HLW8112SPI"); TODO messup ha config if enabled'
    new = '\t\t|| DRV_IsRunning("RN8209")\n\t\t|| DRV_IsRunning("HLW8112SPI");'
    if old in mt:
        mt = mt.replace(old, new, 1)
        MAIN.write_text(mt, encoding="utf-8")
    elif '|| DRV_IsRunning("HLW8112SPI")' not in mt:
        print("WARN: drv_main HLW8112SPI patch skipped")

print("HLW8112 regfix v27 OK")
