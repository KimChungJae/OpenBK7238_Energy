#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v57 (Web HLW8112 표 #energy 분리, 표 소실 방지)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")
HTTP = Path("src/httpserver/http_fns.c")
MAIN = Path("src/driver/drv_main.c")

for p in (HLW, HTTP, MAIN):
    if not p.is_file():
        sys.exit(f"ERROR: {p} not found")

hlw = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX57" in hlw:
    print("Patch v57 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX56" not in hlw:
    sys.exit("ERROR: apply spifix56 first")

http = HTTP.read_text(encoding="utf-8")
main = MAIN.read_text(encoding="utf-8")

need = [
    (hlw, "IONE_BK7238_REGFIX57"),
    (http, 'id=\\"energy\\"'),
    (http, "index?energy=1"),
    (main, "HLW8112 cache"),
]
for text, s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

print("HLW8112 regfix v57 OK")
