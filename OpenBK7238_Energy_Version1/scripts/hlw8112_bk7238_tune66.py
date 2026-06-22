#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v66 (Today sanitize: boot Import delta, not absolute Import)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX66" in text:
    print("Patch v66 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX65" not in text:
    sys.exit("ERROR: apply spifix65 first")

marker = "/* IONE_BK7238_REGFIX65:"
idx = text.find(marker)
if idx < 0:
    sys.exit("ERROR: REGFIX65 marker not found")

insert = (
    "/* IONE_BK7238_REGFIX66: Today≠Import — 부팅 Import 증분 기준 sanitize, 펌웨어 갱신 시 Today 소실 방지 */\n"
)
end = text.find("\n", idx)
text = text[: end + 1] + insert + text[end + 1 :]

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v66 marker OK — apply drv_hlw8112.c body changes manually or from git")
