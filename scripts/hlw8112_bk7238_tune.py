#!/usr/bin/env python3
# BK7238 HLW8112 — IONE patch v6 (레지스터 오프셋, KU, EA 무효값, 로그/부하 경량화)
from pathlib import Path
import sys

HLW = Path("src/driver/drv_hlw8112.c")
HDR = Path("src/driver/drv_hlw8112.h")

if not HLW.is_file():
    sys.exit("ERROR: drv_hlw8112.c not found")

text = HLW.read_text(encoding="utf-8")
if "IONE_BK7238_REGFIX15" in text:
    print("Patch v15 already in tree")
    sys.exit(0)
if "IONE_BK7238_REGFIX14" in text:
    print("Patch v14 already in tree")
    sys.exit(0)
if "IONE_BK7238_REGFIX13" in text:
    print("Patch v13 already in tree")
    sys.exit(0)
if "IONE_BK7238_REGFIX12" in text:
    print("Patch v12 already in tree")
    sys.exit(0)
if "IONE_BK7238_REGFIX11" in text:
    print("Patch v11 already in tree")
    sys.exit(0)
if "IONE_BK7238_REGFIX10" in text:
    print("Patch v10 already in tree")
    sys.exit(0)
if "IONE_BK7238_REGFIX9" in text:
    print("Patch v9 already in tree")
    sys.exit(0)
if "IONE_BK7238_REGFIX8" in text:
    print("Patch v8 already in tree")
    sys.exit(0)
if "IONE_BK7238_REGFIX7" in text:
    print("Patch v7 already in tree")
    sys.exit(0)
if "IONE_BK7238_REGFIX6" in text:
    print("Patch v6 tune already applied")
    sys.exit(0)

if "IONE_BK7238_SPI_FIX5" not in text:
    sys.exit("ERROR: spifix5 (hlw8112_bk7238_spi.py) must be applied first")

# --- ReadRegister: 16/8/32-bit 선행 0xFF 스킵 (주파수 60Hz) ---
old_parse = """\tuint32_t value = 0x0;
  	if (size == 4) {
    	value = ((uint32_t)rx[0] << 24) | ((uint32_t)rx[1] << 16) | ((uint32_t)rx[2] << 8) | ((uint32_t)rx[3]);
  	} else if (size == 3) {
    	value = ((uint32_t)rx[0] << 16) | ((uint32_t)rx[1] << 8) | ((uint32_t)rx[2]);
  	} else if (size == 2) {
    	value = ((uint32_t)rx[0] << 8) | ((uint32_t)rx[1]);
  	} else {
    	value = ((uint32_t)rx[0]);
  	}"""

new_parse = """\t/* IONE_BK7238_REGFIX6: 3-wire read 시 선행 0xFF 더미 — 8/16/32-bit는 rx[1]부터 */
  	int off = (size == 3) ? 0 : 1;
  	uint32_t value = 0x0;
  	if (size == 4) {
    	value = ((uint32_t)rx[off] << 24) | ((uint32_t)rx[off + 1] << 16)
    	        | ((uint32_t)rx[off + 2] << 8) | ((uint32_t)rx[off + 3]);
  	} else if (size == 3) {
    	value = ((uint32_t)rx[off] << 16) | ((uint32_t)rx[off + 1] << 8) | ((uint32_t)rx[off + 2]);
  	} else if (size == 2) {
    	value = ((uint32_t)rx[off] << 8) | ((uint32_t)rx[off + 1]);
  	} else {
    	value = ((uint32_t)rx[off]);
  	}"""

if old_parse not in text:
    sys.exit("ERROR: HLW8112_ReadRegister parse block not found")
text = text.replace(old_parse, new_parse, 1)

# --- EA 0xFFFFFF 무효값 → 스케일 0 (CT/부하 없을 때 ERROR 로그 폭주 방지) ---
old_energy_scale = """void HLW8112_ScaleEnergy(HLW8112_Channel_t channel, uint32_t regValue, int32_t* value){
	if (regValue == 0) {
		*value = 0;
	} else {
		int32_t rv = HLW8112_24BitTo32Bit(regValue);
		double scale = channel == HLW8112_CHANNEL_B ? device.ScaleFactor.b.e : device.ScaleFactor.a.e;
		double v = rv*scale;
		*value = (int32_t)v;
	}
}"""

new_energy_scale = """void HLW8112_ScaleEnergy(HLW8112_Channel_t channel, uint32_t regValue, int32_t* value){
	if (regValue == 0) {
		*value = 0;
	} else if ((regValue & 0x00FFFFFF) == 0x00FFFFFF || (regValue & HLW8112_INVALID_REGVALUE)) {
		/* IONE_BK7238_REGFIX6: 무효 에너지 레지스터 */
		*value = 0;
	} else {
		int32_t rv = HLW8112_24BitTo32Bit(regValue);
		double scale = channel == HLW8112_CHANNEL_B ? device.ScaleFactor.b.e : device.ScaleFactor.a.e;
		double v = rv*scale;
		*value = (int32_t)v;
	}
}"""

if old_energy_scale not in text:
    sys.exit("ERROR: HLW8112_ScaleEnergy not found")
text = text.replace(old_energy_scale, new_energy_scale, 1)

# --- EA 디버그 ERROR 로그 제거 (매초 4줄 → 웹/MQTT 부하) ---
old_ea_log = """\tif (energy_a !=0  ) {
\t\tADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "EA val %08X", data->ea);
\t\tADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "EA scaled val %08X", energy_a);
\t\tADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "Import before %f", energy_acc_a.Import);
\t\tif (power_a > 0) {
\t\t\tenergy_acc_a.Import +=  (double)energy_a / 10000000.0;
\t\t\tsave |= HLW8112_SAVE_A_IMP;
\t\t}else {
\t\t\tenergy_acc_a.Export +=  (double)energy_a / 10000000.0;
\t\t\tsave |= HLW8112_SAVE_A_EXP;
\t\t}

\t\tADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "Import after %f", energy_acc_a.Import);
\t\t}"""

new_ea_log = """\tif (energy_a != 0) {
\t\tADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "EA val %08X scaled %08X", data->ea, energy_a);
\t\tif (power_a > 0) {
\t\t\tenergy_acc_a.Import += (double)energy_a / 10000000.0;
\t\t\tsave |= HLW8112_SAVE_A_IMP;
\t\t} else {
\t\t\tenergy_acc_a.Export += (double)energy_a / 10000000.0;
\t\t\tsave |= HLW8112_SAVE_A_EXP;
\t\t}
\t}"""

if old_ea_log not in text:
    sys.exit("ERROR: EA log block not found")
text = text.replace(old_ea_log, new_ea_log, 1)

# --- RunEverySecond READ_REG 15개 제거 (SPI 부하·웹 불안정) ---
old_read_regs = """
\tREAD_REG(SYSCON,16);
\tREAD_REG(EMUCON,16);
\tREAD_REG(HFCONST,16);
\tREAD_REG(PSTARTA,16);
\tREAD_REG(PSTARTB,16);
\tREAD_REG(PAGAIN,16);
\tREAD_REG(PBGAIN,16);
\tREAD_REG(PHASEA,8);
\tREAD_REG(PHASEB,8);
\tREAD_REG(PAOS,16);
\tREAD_REG(PBOS,16);
\tREAD_REG(RMSIAOS,16);
\tREAD_REG(RMSIBOS,16);
\tREAD_REG(IBGAIN,16);
\tREAD_REG(PSGAIN,16);
\tREAD_REG(PSOS,16);
\tREAD_REG(EMUCON2,16);
\t"""

new_read_regs = """
#if HLW8112_SPI_RAWACCESS
\tREAD_REG(SYSCON,16);
\tREAD_REG(EMUCON,16);
\tREAD_REG(HFCONST,16);
\tREAD_REG(PSTARTA,16);
\tREAD_REG(PSTARTB,16);
\tREAD_REG(PAGAIN,16);
\tREAD_REG(PBGAIN,16);
\tREAD_REG(PHASEA,8);
\tREAD_REG(PHASEB,8);
\tREAD_REG(PAOS,16);
\tREAD_REG(PBOS,16);
\tREAD_REG(RMSIAOS,16);
\tREAD_REG(RMSIBOS,16);
\tREAD_REG(IBGAIN,16);
\tREAD_REG(PSGAIN,16);
\tREAD_REG(PSOS,16);
\tREAD_REG(EMUCON2,16);
#endif
\t"""

if old_read_regs in text:
    text = text.replace(old_read_regs, new_read_regs, 1)

HLW.write_text(text, encoding="utf-8")
print("HLW8112 regfix v6 OK")

if HDR.is_file():
    hdr = HDR.read_text(encoding="utf-8")
    if "IONE PM01_A003" not in hdr:
        hdr = hdr.replace(
            "#define DEFAULT_RES_KU \t\t\t\t\t1.0f",
            "#define DEFAULT_RES_KU \t\t\t\t\t1.5f /* IONE PM01_A003 1.5:1 */",
            1,
        )
        if "1.5f /* IONE PM01_A003" not in hdr:
            hdr = hdr.replace("#define DEFAULT_RES_KU \t\t\t\t\t1.0f", "#define DEFAULT_RES_KU \t\t\t\t\t1.5f")
        HDR.write_text(hdr, encoding="utf-8")
        print("DEFAULT_RES_KU -> 1.5 OK")

print("IONE BK7238 HLW8112 tune v6 applied OK")
