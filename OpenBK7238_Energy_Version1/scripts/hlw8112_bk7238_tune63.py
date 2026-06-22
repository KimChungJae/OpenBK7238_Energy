#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v63 (Energy scale: HFConst/4096, EnergyBC for B)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX63" in text:
    print("Patch v63 already in tree")
    sys.exit(0)

if "IONE_BK7238_REGFIX62" not in text:
    sys.exit("ERROR: apply spifix62 first")

old = """\tdouble ea = (double) device.DeviceRegisterCoeff.EnergyAC * 10000000 / (k1a * k2 * E_RESOLUTION);
\tdouble eb = (double) device.DeviceRegisterCoeff.EnergyAC * 10000000 / (k1b * k2 * E_RESOLUTION);"""

new = """\t/* §10: kWh = Pulse × EnergyXXC × HFConst / (K1 × K2 × 2^29 × 4096) — HFConst 미반영 시 약 1/2 누적 */
\t{
\t\tdouble hf_e = (double)device.HFconst;
\t\tif (hf_e < 1.0)
\t\t\thf_e = 4096.0;
\t\tconst double e_norm = 4096.0;
\t\tdouble ea = (double)device.DeviceRegisterCoeff.EnergyAC * hf_e * 10000000.0
\t\t\t/ (k1a * k2 * (double)E_RESOLUTION * e_norm);
\t\tdouble eb = (double)device.DeviceRegisterCoeff.EnergyBC * hf_e * 10000000.0
\t\t\t/ (k1b * k2 * (double)E_RESOLUTION * e_norm);
\t\tdevice.ScaleFactor.a.e = ea;
\t\tdevice.ScaleFactor.b.e = eb;
\t}"""

if old not in text:
    sys.exit("ERROR: energy scale block not found (already patched?)")

text = text.replace(old, new, 1)
text = text.replace(
    "/* IONE_BK7238_REGFIX62: Energy Total = month + yesterday + today (채널별 일별 누적) */",
    "/* IONE_BK7238_REGFIX62: Energy Total = month + yesterday + today (채널별 일별 누적) */\n"
    "/* IONE_BK7238_REGFIX63: 유효에너지 HFConst·4096·EnergyBC — 채널별 전력 대비 1/2 누적 보정 */",
    1,
)

# 구버전: 블록 밖에서 ea/eb 재대입 — 컴파일 오류 방지
text = text.replace(
    "\tdevice.ScaleFactor.a.ap = apa;\n\tdevice.ScaleFactor.a.e = ea;\n\tdevice.ScaleFactor.b.i = ib;",
    "\tdevice.ScaleFactor.a.ap = apa;\n\tdevice.ScaleFactor.b.i = ib;",
    1,
)
text = text.replace(
    "\tdevice.ScaleFactor.b.ap = apb;\n\tdevice.ScaleFactor.b.e = eb;\n",
    "\tdevice.ScaleFactor.b.ap = apb;\n",
    1,
)

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v63 OK")
