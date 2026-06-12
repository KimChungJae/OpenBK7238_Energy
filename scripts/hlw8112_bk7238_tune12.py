#!/usr/bin/env python3
# BK7238 HLW8112 ??IONE patch v12 (UFREQ: garbage fallback ?úÍ±∞ + Î¨¥Ï†Ñ????0Hz)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if ("IONE_BK7238_REGFIX12" in text or "IONE_BK7238_REGFIX13" in text
        or "IONE_BK7238_REGFIX14" in text or "IONE_BK7238_REGFIX15" in text or "IONE_BK7238_REGFIX16" in text or "IONE_BK7238_REGFIX17" in text):
    print("Patch v12/v13 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX11" not in text:
    sys.exit("ERROR: apply spifix11 first")

old_tail = """\tif (offOut)
\t\t*offOut = bestOff;
\tif (leOut)
\t\t*leOut = bestLe;
\treturn fallback;
}"""

new_tail = """\tif (offOut)
\t\t*offOut = -1;
\tif (leOut)
\t\t*leOut = -1;
\treturn 0; /* ?†Ìö® UFREQ ?ÑÎ≥¥ ?ÜÏùå ??0xFF80 garbage fallback Í∏àÏ? */
}"""

if old_tail not in text:
    sys.exit("ERROR: ParseUfreq fallback tail not found")
text = text.replace(old_tail, new_tail, 1)

# fallback Î≥Ä?òÎäî ÎØ∏ÏÇ¨?©Ïù¥ÏßÄÎß?Í≤ΩÍ≥† Î∞©Ï??©ÏúºÎ°??†Ï? (Ïª¥Ìåå?ºÎü¨Í∞Ä ÏµúÏ†Å??

old_scale = """\tHLW8112_ScaleVoltage(data->v_rms, &voltage);
\tHLW8112_ScaleFrequency(data->freq, &frequency);

  \tHLW8112_ScaleCurrent(HLW8112_CHANNEL_A, data->ia_rms, &current_a);"""

new_scale = """\tHLW8112_ScaleVoltage(data->v_rms, &voltage);
\tHLW8112_ScaleFrequency(data->freq, &frequency);
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
\t/* AC ÎØ∏Ïù∏Í∞Ä(<50V) ??UFREQ Î¨¥Ïãú ??SPI idle Î∞îÏù¥?∏Í? 6.82HzÎ°?Í≥†Ï†ï?òÎäî Î¨∏Ï†ú Î∞©Ï? */
\tif (voltage < 50000)
\t\tfrequency = 0;
#endif

  \tHLW8112_ScaleCurrent(HLW8112_CHANNEL_A, data->ia_rms, &current_a);"""

if old_scale not in text:
    sys.exit("ERROR: ScaleAndUpdate block not found")
text = text.replace(old_scale, new_scale, 1)

text = text.replace("IONE_BK7238_REGFIX11", "IONE_BK7238_REGFIX12")
text = text.replace("/* IONE_BK7238_REGFIX11:", "/* IONE_BK7238_REGFIX12:")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v12 OK")
