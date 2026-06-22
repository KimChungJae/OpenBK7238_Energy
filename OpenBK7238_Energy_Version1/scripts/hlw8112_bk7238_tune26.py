#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v26 (메인 웹 갱신 주기 10초)
from pathlib import Path
import sys

HTTP = Path("src/httpserver/new_http.c")

if not HTTP.is_file():
    sys.exit("ERROR: new_http.c not found")

text = HTTP.read_text(encoding="utf-8")
if "IONE_BK7238_HTTP_REFRESH" in text or "g_indexAutoRefreshInterval = 10000" in text:
    print("Patch v26 already applied")
    sys.exit(0)

old = "int g_indexAutoRefreshInterval = 1000; // 1s"
new = "int g_indexAutoRefreshInterval = 10000; // IONE_BK7238_HTTP_REFRESH: 10s (웹 깜빡임 완화)"

if old not in text:
    sys.exit("ERROR: g_indexAutoRefreshInterval default not found")

HTTP.write_text(text.replace(old, new, 1), encoding="utf-8")
print("HTTP refresh interval v26 OK (10s)")
