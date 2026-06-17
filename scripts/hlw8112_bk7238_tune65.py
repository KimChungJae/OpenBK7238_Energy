#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v65 (제목·Daily Total 좌측 정렬)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX65" in text:
    print("Patch v65 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX64" not in text:
    sys.exit("ERROR: apply spifix64 first")

need = [
    "IONE_BK7238_REGFIX65",
    "#main>h1{max-width:580px",
    "hlw-line",
    "colspan='3' class='hlw-line'",
    "width:28%",
]
for s in need:
    if s not in text:
        sys.exit(f"ERROR: missing {s!r}")

if "hlw-span" in text:
    sys.exit("ERROR: hlw-span should be removed in v65")

print("HLW8112 regfix v65 OK")
