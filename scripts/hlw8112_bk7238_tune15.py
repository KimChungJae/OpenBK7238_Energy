#!/usr/bin/env python3
# BK7238 HLW8112 ??IONE patch v15 (UFREQ: 24-bit off=0 ?¨Îùº?¥Ïä§ ?ÑÎ≥¥ Ï∂îÍ?)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX15" in text or "IONE_BK7238_REGFIX16" in text or "IONE_BK7238_REGFIX17" in text:
    print("Patch v15/v16 already applied")
    sys.exit(0)

if "IONE_BK7238_REGFIX14" not in text and "IONE_BK7238_REGFIX15" not in text:
    sys.exit("ERROR: apply spifix14 first")

insert_after = """\t{
\t\tint skip = 0;
\t\twhile (skip < 4 && rx[skip] == 0xFF)
\t\t\tskip++;
\t\tif (skip <= 3) {
\t\t\tHLW8112_BK7238_TryUfreqHz(rx, skip, 0, frqScale, &best, &bestOff, &bestLe, &bestDiff);
\t\t\tHLW8112_BK7238_TryUfreqHz(rx, skip, 1, frqScale, &best, &bestOff, &bestLe, &bestDiff);
\t\t}
\t}"""

new_block = """\t{
\t\tint skip = 0;
\t\twhile (skip < 4 && rx[skip] == 0xFF)
\t\t\tskip++;
\t\tif (skip <= 3) {
\t\t\tHLW8112_BK7238_TryUfreqHz(rx, skip, 0, frqScale, &best, &bestOff, &bestLe, &bestDiff);
\t\t\tHLW8112_BK7238_TryUfreqHz(rx, skip, 1, frqScale, &best, &bestOff, &bestLe, &bestDiff);
\t\t}
\t}
\t/* RMSU?Ä ?ôÏùº 24-bit(off=0) ?ÑÎ†à?ÑÏóê??16-bit UFREQ ?¨Îùº?¥Ïä§ ?ÑÎ≥¥ */
\t{
\t\tuint32_t raw24 = ((uint32_t)rx[0] << 16) | ((uint32_t)rx[1] << 8) | (uint32_t)rx[2];
\t\tuint32_t slice[4] = {
\t\t\traw24 & 0xFFFFU,
\t\t\t(raw24 >> 8) & 0xFFFFU,
\t\t\t((uint32_t)rx[2] << 8) | (uint32_t)rx[3],
\t\t\t((uint32_t)rx[3] << 8) | (uint32_t)rx[4],
\t\t};
\t\tfor (int si = 0; si < 4; si++) {
\t\t\tuint32_t v = slice[si];
\t\t\tint32_t hz, diff;
\t\t\tif (v == 0 || v >= 0xFF00)
\t\t\t\tcontinue;
\t\t\thz = (int32_t)(frqScale / (double)v);
\t\t\tif (hz < 3500 || hz > 8000)
\t\t\t\tcontinue;
\t\t\tdiff = hz - 6000;
\t\t\tif (diff < 0)
\t\t\t\tdiff = -diff;
\t\t\tif (best == 0 || diff < bestDiff) {
\t\t\t\tbest = v;
\t\t\t\tbestOff = 100 + si;
\t\t\t\tbestLe = -1;
\t\t\t\tbestDiff = diff;
\t\t\t}
\t\t}
\t}"""

if insert_after not in text:
    sys.exit("ERROR: ParseUfreq skip block not found")
text = text.replace(insert_after, new_block, 1)

text = text.replace("IONE_BK7238_REGFIX14", "IONE_BK7238_REGFIX15")
text = text.replace("/* IONE_BK7238_REGFIX14:", "/* IONE_BK7238_REGFIX15:")

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v15 OK")
