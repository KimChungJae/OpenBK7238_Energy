#!/usr/bin/env python3
"""CI patch 단계와 동일 검증 (로컬/Actions 디버그용)"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1_SCRIPTS = ROOT / "OpenBK7238_Energy_Version1" / "scripts"
SCRIPTS = ["hlw8112_bk7238_spi.py", "hlw8112_bk7238_tune.py"] + [
    f"hlw8112_bk7238_tune{n}.py"
    for n in range(7, 47)
]

for name in SCRIPTS:
    r = subprocess.run([sys.executable, str(V1_SCRIPTS / name)], cwd=ROOT)
    if r.returncode:
        print(f"FAIL script: {name}", file=sys.stderr)
        sys.exit(r.returncode)

t = (ROOT / "src/driver/drv_hlw8112.c").read_text(encoding="utf-8")
h = (ROOT / "src/driver/drv_hlw8112.h").read_text(encoding="utf-8")
n = (ROOT / "src/httpserver/new_http.c").read_text(encoding="utf-8")

checks = [
    ("REGFIX45", "IONE_BK7238_REGFIX45" in t),
    ("REGFIX46", "IONE_BK7238_REGFIX46" in t),
    ('Export_A/B', '\\"Export_A\\":%.3f,\\"Export_B\\":%.3f' in t),
    ('Power Factor %', '"Power Factor", "%"' in t),
    ("LocalYmd", "HLW8112_LocalYmd" in t),
    ("PeriodicFlashSave", "HLW8112_PeriodicFlashSave" in t),
    ("Today_A", "Today_A" in t),
    ("no Power_T", '"Power_T"' not in t),
    ("refresh10s", "g_indexAutoRefreshInterval = 10000" in n),
    ("KU1.5", "DEFAULT_RES_KU" in h and "1.5f" in h),
]
for name, ok in checks:
    if not ok:
        print(f"FAIL check: {name}", file=sys.stderr)
        sys.exit(1)
print("CI_PATCH_OK")
