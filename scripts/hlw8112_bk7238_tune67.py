#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v67 (Import/Today: Active Power 1s integration)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX67" in text:
    print("Patch v67 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX66" not in text:
    sys.exit("ERROR: apply spifix66 first")

marker = "/* IONE_BK7238_REGFIX66:"
idx = text.find(marker)
if idx < 0:
    sys.exit("ERROR: REGFIX66 marker not found")

insert = (
    "/* IONE_BK7238_REGFIX67: Import/Today — 유효전력(mW) 1초 적분 (펄스 스케일 오류·0 펄스 구간 보완) */\n"
)
end = text.find("\n", idx)
text = text[: end + 1] + insert + text[end + 1 :]

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v67 marker OK")
