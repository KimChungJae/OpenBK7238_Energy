// HLW8112

// workaround for code folding region pragma remove it when compiler are updated
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunknown-pragmas" 

#include "drv_hlw8112.h"
#include "../obk_config.h"
#include "../new_common.h"

#if ENABLE_DRIVER_HLW8112SPI

#include <math.h>
#include <stdint.h>
#include <inttypes.h>


#include "../cmnds/cmd_public.h"
#include "../hal/hal_flashVars.h"
#include "../hal/hal_ota.h"
#include "../hal/hal_pins.h"
#include "../httpserver/hass.h"
#include "../logging/logging.h"
#include "../libraries/obktime/obktime.h"
#include "../driver/drv_deviceclock.h"
#include "../new_pins.h"

#include "drv_public.h"
#include "drv_spi.h"


static const uint32_t RMS_I_RESOLUTION  = 8388608 ; // 1 << 23;
static const uint32_t RMS_U_RESOLUTION  = 4194304 ; //1 << 22;
static const uint32_t PF_RESOLUTION  = 8388607 ; //
static const uint32_t PWR_RESOLUTION  = 2147483648; // 1 << 31;
static const uint32_t E_RESOLUTION  = 536870912; // 1 << 29;

static HLW8112_Device_Conf_t device;   // coeff reg k1 k2 pga etc
static HLW8112_Data_t last_data;		// last read reg values
static HLW8112_UpdateData_t last_update_data;	// last scaled values for ext systems 


// energy stats saved/restored in/out flash
static ENERGY_DATA energy_acc_a = {
	.Import =0 , .Export = 0
}; 
static ENERGY_DATA energy_acc_b= {
	.Import =0 , .Export = 0
};;

static HLW8112_UpdateData_t last_update_data = {
	.v_rms = 0, .freq = 0, .pf = 0 , .ap = 0, 
	.ia_rms = 0, .pa =0, .ea= &energy_acc_a,
	.ib_rms = 0, .pb =0, .eb= &energy_acc_b
};	// last scaled values for ext systems 

static int stat_save_count_down = HLW8112_SAVE_COUNTER;
int GPIO_HLW_SCSN = 9;

#pragma region HLW8112 utils

#if HLW8112_SPI_RAWACCESS

void HLW8112_Print_Array(uint8_t *data, int size) {
	for (int i = 0; i <= size; i++) {
		ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_Print_Array i = %d : v = %02hhX", i, data[i]);
	}
}
#else
void HLW8112_Print_Array(uint8_t *data, int size) {}
#endif

static int32_t HLW8112_24BitTo32Bit(uint32_t value) {
	int32_t result = 0;
	value &= 0x00FFFFFF;
	if (value & 0x00800000)
		result = 0xFF000000;
	result |= value;
	return result;
}

#pragma endregion


#pragma region HLW8112 register ops

#pragma region HLW8112 register lowlevel ops


#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
#include "arm_arch.h"
#include "drv_model_pub.h"
#include "gpio_pub.h"
#include "icu_pub.h"
#include "spi_pub.h"
#include "spi_bk7231n.h"

/* IONE_BK7238_SPI_FIX5 — BK7238 DMA SPI 미동작, FIFO 폴링 + 3-wire write-then-read */
static void HLW8112_SPI_EnableGpio(void) {
	uint32_t val;
	val = GFUNC_MODE_SPI_GPIO_14;
	sddev_control(GPIO_DEV_NAME, CMD_GPIO_ENABLE_SECOND, &val);
	val = GFUNC_MODE_SPI_GPIO_16_17;
	sddev_control(GPIO_DEV_NAME, CMD_GPIO_ENABLE_SECOND, &val);
	UINT32 param = PCLK_POSI_SPI;
	sddev_control(ICU_DEV_NAME, CMD_CONF_PCLK_26M, &param);
	param = PWD_SPI_CLK_BIT;
	sddev_control(ICU_DEV_NAME, CMD_CLK_PWR_UP, &param);
}

static void hlw8112_spi_reg_bit(uint32_t reg, uint32_t bit, int on) {
	uint32_t v = REG_READ(reg);
	if (on)
		v |= bit;
	else
		v &= ~bit;
	REG_WRITE(reg, v);
}

static void hlw8112_spi_rxfifo_clr(void) {
	uint32_t st = REG_READ(SPI_STAT);
	while (st & RXFIFO_RD_READ) {
		REG_READ(SPI_DAT);
		st = REG_READ(SPI_STAT);
	}
}

static void hlw8112_spi_txfifo_clr(void) {
	uint32_t v = REG_READ(SPI_STAT);
	v |= TXFIFO_CLR_EN;
	REG_WRITE(SPI_STAT, v);
}

static int hlw8112_spi_write_byte(uint8_t b) {
	int timeout = 20000;
	while (timeout-- > 0) {
		if (REG_READ(SPI_STAT) & TXFIFO_WR_READ) {
			REG_WRITE(SPI_DAT, b);
			return 0;
		}
	}
	return -6;
}

static int hlw8112_spi_read_byte(uint8_t *b) {
	int timeout = 20000;
	while (timeout-- > 0) {
		if (REG_READ(SPI_STAT) & RXFIFO_RD_READ) {
			if (b)
				*b = (uint8_t)REG_READ(SPI_DAT);
			else
				REG_READ(SPI_DAT);
			return 0;
		}
	}
	return -6;
}

static void hlw8112_spi_set_clock(uint32_t hz) {
	const uint32_t src = 26000000;
	uint32_t div = src / 2 / hz;
	if (div < 1)
		div = 1;
	if (div > 255)
		div = 255;
	uint32_t ctrl = REG_READ(SPI_CTRL);
	ctrl &= ~(SPI_CKR_MASK << SPI_CKR_POSI);
	ctrl |= (div << SPI_CKR_POSI);
	REG_WRITE(SPI_CTRL, ctrl);
}

static void HLW8112_BK7238_PollSpiConfigure(void) {
	HLW8112_SPI_EnableGpio();
	REG_WRITE(SPI_CTRL, RXOVR_EN | TXOVR_EN);
	hlw8112_spi_reg_bit(SPI_CTRL, MSTEN, 0);
	hlw8112_spi_reg_bit(SPI_CTRL, BIT_WDTH, 0);
	hlw8112_spi_set_clock(HLW8112_SPI_BAUD_RATE);
	/* mode2: CPOL=1 CPHA=0 */
	hlw8112_spi_reg_bit(SPI_CTRL, CKPOL, 1);
	hlw8112_spi_reg_bit(SPI_CTRL, CKPHA, 0);
	/* 3-wire */
	{
		uint32_t ctrl = REG_READ(SPI_CTRL);
		ctrl &= ~CTRL_NSSMD_3;
		ctrl |= CTRL_NSSMD_3;
		REG_WRITE(SPI_CTRL, ctrl);
	}
	hlw8112_spi_reg_bit(SPI_CTRL, TXINT_EN, 0);
	hlw8112_spi_reg_bit(SPI_CTRL, RXINT_EN, 0);
	hlw8112_spi_reg_bit(SPI_CTRL, MSTEN, 1);
	hlw8112_spi_reg_bit(SPI_CTRL, SPIEN, 1);
	{
		uint32_t cfg = REG_READ(SPI_CONFIG);
		cfg |= SPI_TX_EN | SPI_RX_EN;
		REG_WRITE(SPI_CONFIG, cfg);
	}
	hlw8112_spi_txfifo_clr();
	hlw8112_spi_rxfifo_clr();
}

static void HLW8112_BK7238_PollSpiShutdown(void) {
	hlw8112_spi_reg_bit(SPI_CTRL, SPIEN, 0);
	UINT32 param = PWD_SPI_CLK_BIT;
	sddev_control(ICU_DEV_NAME, CMD_CLK_PWR_DOWN, &param);
}

static int HLW8112_BK7238_PollXfer(const uint8_t *tx, uint32_t txSize, uint8_t *rx, uint32_t rxSize) {
	uint32_t i;
	int r;
	hlw8112_spi_txfifo_clr();
	hlw8112_spi_rxfifo_clr();
	if (txSize && tx) {
		for (i = 0; i < txSize; i++) {
			r = hlw8112_spi_write_byte(tx[i]);
			if (r)
				return r;
			r = hlw8112_spi_read_byte(NULL);
			if (r)
				return r;
		}
	}
	if (rxSize && rx) {
		rtos_delay_milliseconds(1);
		for (i = 0; i < rxSize; i++) {
			r = hlw8112_spi_write_byte(0xFF);
			if (r)
				return r;
			r = hlw8112_spi_read_byte(&rx[i]);
			if (r)
				return r;
		}
	}
	return 0;
}
#endif

void HLW8112_SPI_Txn_Begin(void) {
	HAL_PIN_SetOutputValue(GPIO_HLW_SCSN, 0); 
}

void HLW8112_SPI_Txn_End(void) {
	 HAL_PIN_SetOutputValue(GPIO_HLW_SCSN, 1);
}

int HLW8112_SPI_ReadBytes(uint8_t *buffer, uint32_t size) {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	int Result = HLW8112_BK7238_PollXfer(NULL, 0, buffer, size);
#else
	int Result = SPI_ReadBytes(buffer, size);
#endif
	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_SPI_Read result %x", Result);
	return Result;
}

int HLW8112_SPI_WriteBytes(uint8_t *data, uint32_t size) {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	int Result = HLW8112_BK7238_PollXfer(data, size, NULL, 0);
#else
	int Result = SPI_WriteBytes(data, size);
#endif
	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_SPI_Write result %x", Result);
	return Result;
}

#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
static void HLW8112_BK7238_RegGap(void);
#endif

int HLW8112_SPI_Transact(uint8_t *txBuffer, uint32_t txSize, uint8_t *rxBuffer, uint32_t rxSize) {
	/* IONE_BK7238_SPI_FIX5 */
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	HLW8112_BK7238_RegGap();
#endif
	HLW8112_SPI_Txn_Begin();
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	int Result = HLW8112_BK7238_PollXfer((const uint8_t *)txBuffer, txSize, rxBuffer, rxSize);
#else
	int Result = SPI_Transmit(txBuffer, txSize, rxBuffer, rxSize);
#endif
	HLW8112_SPI_Txn_End();
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	HLW8112_BK7238_RegGap();
#endif
	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_SPI_Transact result %d", Result);
	return Result;
}
#pragma endregion

#pragma region read



#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
/* IONE_BK7238_REGFIX19: HLW8112 SPI 프레임 간 CS-high 유지 (10ms) */
static void HLW8112_BK7238_RegGap(void) {
	rtos_delay_milliseconds(10);
}

static int HLW8112_BK7238_RxAllFF(const uint8_t *rx) {
	return rx[0] == 0xFF && rx[1] == 0xFF && rx[2] == 0xFF;
}
#endif
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
/* IONE_BK7238_REGFIX22: 16-bit 계수 레지스터별 off (0x70/0x71=0, 0x72~=1) + 웹 표 숫자 폭 고정 */
static int HLW8112_BK7238_RxOffset(const uint8_t *rx, uint8_t reg, uint8_t size) {
	(void)rx;
	if (size == 2) {
		if (reg == HLW8112_REG_RMSIAC || reg == HLW8112_REG_RMSIBC)
			return 0;
		return 1;
	}
	return 0;
}

static uint32_t HLW8112_BK7238_UfreqPair(const uint8_t *rx, int off, int le) {
	if (le)
		return ((uint32_t)rx[off + 1] << 8) | (uint32_t)rx[off];
	return ((uint32_t)rx[off] << 8) | (uint32_t)rx[off + 1];
}

static void HLW8112_BK7238_TryUfreqHz(const uint8_t *rx, int off, int le, double frqScale,
		uint32_t *best, int *bestOff, int *bestLe, int32_t *bestDiff) {
	uint32_t v = HLW8112_BK7238_UfreqPair(rx, off, le);
	int32_t hz, diff;
	if (v == 0 || v >= 0xFF00)
		return;
	hz = (int32_t)(frqScale / (double)v);
	if (hz < 3500 || hz > 8000)
		return;
	diff = hz - 6000;
	if (diff < 0)
		diff = -diff;
	if (*best == 0 || diff < *bestDiff) {
		*best = v;
		*bestOff = off;
		*bestLe = le;
		*bestDiff = diff;
	}
}

static uint32_t HLW8112_BK7238_ParseUfreq(const uint8_t *rx, int *offOut, int *leOut) {
	uint32_t best = 0;
	int bestOff = -1;
	int bestLe = -1;
	int32_t bestDiff = 999999;
	double frqScale;
	if (device.CLKI > 0)
		frqScale = (double)device.CLKI * 100.0 / 8.0;
	else
		frqScale = (double)DEFAULT_INTERNAL_CLK * 100.0 / 8.0;
	/* off×BE/LE 스캔 — 35~80Hz(Ch1 3500~8000)에 60Hz(6000)에 가장 가까운 후보 */
	for (int off = 0; off <= 3; off++) {
		for (int le = 0; le <= 1; le++)
			HLW8112_BK7238_TryUfreqHz(rx, off, le, frqScale, &best, &bestOff, &bestLe, &bestDiff);
	}
	{
		int skip = 0;
		while (skip < 4 && rx[skip] == 0xFF)
			skip++;
		if (skip <= 3) {
			HLW8112_BK7238_TryUfreqHz(rx, skip, 0, frqScale, &best, &bestOff, &bestLe, &bestDiff);
			HLW8112_BK7238_TryUfreqHz(rx, skip, 1, frqScale, &best, &bestOff, &bestLe, &bestDiff);
		}
	}
	/* RMSU와 동일 24-bit(off=0) 프레임에서 16-bit UFREQ 슬라이스 후보 */
	{
		uint32_t raw24 = ((uint32_t)rx[0] << 16) | ((uint32_t)rx[1] << 8) | (uint32_t)rx[2];
		uint32_t slice[4] = {
			raw24 & 0xFFFFU,
			(raw24 >> 8) & 0xFFFFU,
			((uint32_t)rx[2] << 8) | (uint32_t)rx[3],
			((uint32_t)rx[3] << 8) | (uint32_t)rx[4],
		};
		for (int si = 0; si < 4; si++) {
			uint32_t v = slice[si];
			int32_t hz, diff;
			if (v == 0 || v >= 0xFF00)
				continue;
			hz = (int32_t)(frqScale / (double)v);
			if (hz < 3500 || hz > 8000)
				continue;
			diff = hz - 6000;
			if (diff < 0)
				diff = -diff;
			if (best == 0 || diff < bestDiff) {
				best = v;
				bestOff = 100 + si;
				bestLe = -1;
				bestDiff = diff;
			}
		}
	}
	if (best != 0) {
		if (offOut)
			*offOut = bestOff;
		if (leOut)
			*leOut = bestLe;
		return best;
	}
	if (offOut)
		*offOut = -1;
	if (leOut)
		*leOut = -1;
	return 0;
}
#endif


#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
static void HLW8112_LogUfreqRxOnce(const uint8_t *rx, uint32_t parsed, int off, int le) {
	static uint8_t done;
	if (done)
		return;
	done = 1;
	double frqScale = device.ScaleFactor.freq;
	if (frqScale <= 0)
		frqScale = (double)DEFAULT_INTERNAL_CLK * 100.0 / 8.0;
	ADDLOG_WARN(LOG_FEATURE_ENERGYMETER,
		"UFREQ rx %02X %02X %02X %02X %02X off=%d le=%d val=%u Ch1~%u",
		rx[0], rx[1], rx[2], rx[3], rx[4], off, le, (unsigned)parsed,
		(unsigned)(parsed ? (uint32_t)(frqScale / (double)parsed) : 0));
}
#endif

int HLW8112_ReadRegister(uint8_t reg, uint8_t size, uint32_t *valueResult) {
  	uint8_t tx[1] = {0xFF};
  	uint8_t rx[5] = {0};
  	tx[0] = reg & 0x7F;
  	
	int result = HLW8112_SPI_Transact(tx, 1, rx, 5);
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	if (result >= 0 && HLW8112_BK7238_RxAllFF(rx))
		HLW8112_SPI_Transact(tx, 1, rx, 5);
#endif
  	if (result < 0) {
    	ADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "HLW8112_ReadRegister non zero result %d", result);
    	return result;
  	}
  	HLW8112_Print_Array(rx, 5);
  
	/* IONE_BK7238_REGFIX24 */
  	uint32_t value = 0x0;
  	int off = 0;
	int ufreqLe = 0;
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
  	if (reg == HLW8112_REG_UFREQ && size == 2) {
  		value = HLW8112_BK7238_ParseUfreq(rx, &off, &ufreqLe);
  	} else {
  		off = HLW8112_BK7238_RxOffset(rx, reg, size);
#endif
  	if (size == 4) {
    	value = ((uint32_t)rx[off] << 24) | ((uint32_t)rx[off + 1] << 16)
    	        | ((uint32_t)rx[off + 2] << 8) | ((uint32_t)rx[off + 3]);
  	} else if (size == 3) {
    	value = ((uint32_t)rx[off] << 16) | ((uint32_t)rx[off + 1] << 8) | ((uint32_t)rx[off + 2]);
  	} else if (size == 2) {
    	value = ((uint32_t)rx[off] << 8) | ((uint32_t)rx[off + 1]);
  	} else {
    	value = ((uint32_t)rx[off]);
  	}
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
  	}
#endif
  	*valueResult = value;
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	if (reg == HLW8112_REG_UFREQ && size == 2)
		HLW8112_LogUfreqRxOnce(rx, value, off, ufreqLe);
#endif
  	return result;
}


int HLW8112_ReadRegister8(uint8_t reg, uint8_t *valueResult) {
  	uint32_t tmpValue;
  	int result = HLW8112_ReadRegister(reg, 1, &tmpValue);
  	*valueResult = (uint8_t)tmpValue;
  	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_ReadRegister8 reg= %02X : v = %02X", reg, *valueResult);
  	return result;
}

int HLW8112_ReadRegister16(uint8_t reg, uint16_t *valueResult) {
  	uint32_t tmpValue;
  	int result = HLW8112_ReadRegister(reg, 2, &tmpValue);
  	*valueResult = (uint16_t)tmpValue;
  	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_ReadRegister16 reg= %02X : v = %04X", reg, *valueResult);
  	return result;
}

int HLW8112_ReadRegister24(uint8_t reg, uint32_t *valueResult) {
	int result = HLW8112_ReadRegister(reg, 3, valueResult);
  	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_ReadRegister24 reg= %02X : v = %06X", reg, *valueResult);
  	return result;
}

int HLW8112_ReadRegister32(uint8_t reg, uint32_t *valueResult) {
  	int result = HLW8112_ReadRegister(reg, 4, valueResult);
  	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_ReadRegister32 reg= %02X : v = %08X", reg, *valueResult);
  	return result;
}
#pragma endregion

#pragma region write

// needs to take care of spi txn by callee
int HLW8112_WriteRegister(uint8_t reg, uint8_t *data, uint8_t size) {
  	uint8_t tx[3] = {0};
  	if (reg == HLW8112_REG_COMMAND) {
    	tx[0] = reg;
  	} else {
    	tx[0] = reg | 0x80;
  	}
	//checks
  	if (size > 2) {
    	ADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "HLW8112_WriteRegister can only write 8 or 16 bit reg = %02X", reg);
    	return -2;
  	}

	// buffer prepare
  	for (uint8_t i = 0; i < size; i++) {
    	tx[1 + i] = data[i];
  	}
  	
  	int result = HLW8112_SPI_WriteBytes(tx, size + 1);
  	//TODO: verify written bytes register
  	return result;
}

uint8_t HLW8112_WriteRegisterValue(uint8_t reg, uint16_t value) {
  	uint8_t data[2] = {0};
  	data[0] = (value >> 8) & 0xFF;
  	data[1] = value & 0xFF;
  	uint8_t result = HLW8112_WriteRegister(reg, data, 2);
  	return result;
}

uint8_t HLW8112_WriteRegisterValue8(uint8_t reg, uint8_t value) {
  	uint8_t data[1] = {value};
  	uint8_t result = HLW8112_WriteRegister(reg, data, 1);
  	return result;
}

uint8_t HLW8112_SPI_WriteControl(uint8_t control) {
  	return HLW8112_WriteRegisterValue8(HLW8112_REG_COMMAND, control);
}

int writeEnable() {
  	return HLW8112_SPI_WriteControl(HLW8112_COMMAND_WRITE_EN);
}

int writeDisable() {
  	return HLW8112_SPI_WriteControl(HLW8112_COMMAND_WRITE_PROTECT);
}

uint8_t HLW8112_WriteRegister16(uint8_t reg, uint16_t value) {
  	HLW8112_SPI_Txn_Begin();
  	writeEnable();
  	
	uint8_t result = HLW8112_WriteRegisterValue(reg, value);
  	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_WriteRegisterValue result %d", result);
  	
	writeDisable();
  	HLW8112_SPI_Txn_End();
  
	//TODO verify reg this is big no for clearing regs will need to switch last read reg
	uint16_t readValue;
  	int rresult = HLW8112_ReadRegister16(reg, &readValue);
  	if (rresult < 0) {
    	ADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "Write Verify read result %d", rresult);
		return -2;
  	}

  	if (value != readValue) {
    	ADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "Write Verify failed reg=%02X value=%04X rv=%04X", reg, value, readValue);
		return -3;
	}

  	return result;
}
uint8_t HLW8112_WriteRegister8(uint8_t reg, uint8_t value) {
  	HLW8112_SPI_Txn_Begin();
  	writeEnable();
  	
	uint8_t result = HLW8112_WriteRegisterValue8(reg, value);
  	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_WriteRegisterValue8 result %d", result);
  	
	writeDisable();
  	HLW8112_SPI_Txn_End();
  
	//TODO verify reg this is big no for clearing regs will need to switch last read reg
	uint8_t readValue;
  	int rresult = HLW8112_ReadRegister8(reg, &readValue);
  	if (rresult < 0) {
    	ADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "Write Verify read result %d", rresult);
		return -2;
  	}

  	if (value != readValue) {
    	ADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "Write Verify failed reg=%02X value=%04X rv=%04X", reg, value, readValue);
		return -3;
	}

  	return result;
}
#pragma endregion

#pragma endregion


#pragma region flash ops
void HLW8112_Restore_Stats(void) {
	energy_acc_a.Export = 0;
	energy_acc_a.Import = 0;
	energy_acc_b.Export = 0;
	energy_acc_a.Import = 0;
	HAL_FlashVars_GetEnergy(&energy_acc_a, ENERGY_CHANNEL_A);
	HAL_FlashVars_GetEnergy(&energy_acc_b, ENERGY_CHANNEL_B);
}

void HLW8112_save_stats(HLW8112_SaveFlags_t save) {
	ADDLOG_DEBUG( LOG_FEATURE_ENERGYMETER , "HLW8112_SaveFlash_t value = %08X", save);
	if(save > 0 ){
		//TODO write proper flash write debounce
		int pg = OTA_GetProgress();  
		// sometime this messup ota when ota is also writing to flash
		if (pg != -1)
      	{
        	ADDLOG_WARN( LOG_FEATURE_ENERGYMETER , "OTA in progress skip write to flash pg=%d", pg);
			return;
      	}
		stat_save_count_down --;
		if(stat_save_count_down <= 0 || save & HLW8112_SAVE_FORCE) {
			stat_save_count_down = HLW8112_SAVE_COUNTER;
			ENERGY_DATA* data[2] = {&energy_acc_a, &energy_acc_b};
			HAL_FlashVars_SaveEnergy(data, 2);
		}
	}
}
void HLW8112_Set_EnergyStat(HLW8112_Channel_t channel, float import, float export) {
	ENERGY_DATA* data = &energy_acc_a;
	uint16_t counter_reg = HLW8112_REG_PFCntPA;
	if (channel == HLW8112_CHANNEL_B){
		data = &energy_acc_b;
		counter_reg = HLW8112_REG_PFCntPB;
		CHANNEL_Set(HLW8112_Channel_export_B, export * 1000, 0);
		CHANNEL_Set(HLW8112_Channel_import_B, import * 1000, 0);
	}else {
		CHANNEL_Set(HLW8112_Channel_export_A, export * 1000, 0);
		CHANNEL_Set(HLW8112_Channel_import_A, import * 1000, 0);
	}

	HLW8112_WriteRegister16(counter_reg,0);
	data->Import = import;
	data->Export = export;
	HLW8112_save_stats(HLW8112_SAVE_FORCE);
}
#pragma endregion


#pragma region commands

static commandResult_t HLW8112_SetClock(const void *context, const char *cmd, const char *args, int cmdFlags) {
	Tokenizer_TokenizeString(args, TOKENIZER_ALLOW_QUOTES);
	if (Tokenizer_CheckArgsCountAndPrintWarning(cmd, 1)) {
		return CMD_RES_NOT_ENOUGH_ARGUMENTS;
	}
	uint32_t value = Tokenizer_GetArgInteger(0);
	device.CLKI = value;
	//CHANNEL_Set(HLW8112_Channel_Clk, value, 0 );
	CFG_SetPowerMeasurementCalibrationInteger(CFG_OBK_CLK,value);
	HLW8112_compute_scale_factor();
	return CMD_RES_OK;
}
static commandResult_t HLW8112_SetResistorGain(const void *context, const char *cmd, const char *args, int cmdFlags) {
	Tokenizer_TokenizeString(args, TOKENIZER_ALLOW_QUOTES);
	if (Tokenizer_CheckArgsCountAndPrintWarning(cmd, 3)) {
		return CMD_RES_NOT_ENOUGH_ARGUMENTS;
	}
	
	device.ResistorCoeff.KU = Tokenizer_GetArgFloat(0);
	device.ResistorCoeff.KIA = Tokenizer_GetArgFloat(1);
	device.ResistorCoeff.KIB = Tokenizer_GetArgFloat(2);
	
	//CHANNEL_Set(HLW8112_Channel_ResCof_Voltage, device.ResistorCoeff.KU, 0 );
	//CHANNEL_Set(HLW8112_Channel_ResCof_A, device.ResistorCoeff.KIA, 0 );
	//CHANNEL_Set(HLW8112_Channel_ResCof_B, device.ResistorCoeff.KIB, 0 );
	CFG_SetPowerMeasurementCalibrationFloat(CFG_OBK_RES_KU, device.ResistorCoeff.KU );
	CFG_SetPowerMeasurementCalibrationFloat(CFG_OBK_RES_KIA, device.ResistorCoeff.KIA );
	CFG_SetPowerMeasurementCalibrationFloat(CFG_OBK_RES_KIB, device.ResistorCoeff.KIB );
	HLW8112_compute_scale_factor();
	return CMD_RES_OK;
}
static commandResult_t HLW8112_SetEnergyStat(const void *context, const char *cmd, const char *args, int cmdFlags) {
	Tokenizer_TokenizeString(args, TOKENIZER_ALLOW_QUOTES);
	if (Tokenizer_CheckArgsCountAndPrintWarning(cmd, 4)) {
		return CMD_RES_NOT_ENOUGH_ARGUMENTS;
	}

	HLW8112_Set_EnergyStat(HLW8112_CHANNEL_A,Tokenizer_GetArgFloat(0),Tokenizer_GetArgFloat(1));
	HLW8112_Set_EnergyStat(HLW8112_CHANNEL_B,Tokenizer_GetArgFloat(2),Tokenizer_GetArgFloat(3));
	return CMD_RES_OK;
}

static commandResult_t HLW8112_ClearEnergy(const void *context, const char *cmd, const char *args, int cmdFlags) {
	Tokenizer_TokenizeString(args, TOKENIZER_ALLOW_QUOTES);
	if (Tokenizer_CheckArgsCountAndPrintWarning(cmd, 1)) {
		return CMD_RES_NOT_ENOUGH_ARGUMENTS;
	}
	char* channel = Tokenizer_GetArg(0);
	if (!strcmp("channel_a" , channel)) {
		HLW8112_Set_EnergyStat(HLW8112_CHANNEL_A,0,0);
	} else if (!strcmp("channel_b" , channel)){
		HLW8112_Set_EnergyStat(HLW8112_CHANNEL_B,0,0);
	}
	return CMD_RES_OK;
}

#if HLW8112_SPI_RAWACCESS
static commandResult_t HLW8112_write_reg(const void *context, const char *cmd, const char *args, int cmdFlags) {

  	Tokenizer_TokenizeString(args, TOKENIZER_ALLOW_QUOTES);
  	if (Tokenizer_CheckArgsCountAndPrintWarning(cmd, 2)) {
    	return CMD_RES_NOT_ENOUGH_ARGUMENTS;
  	}
  	int reg = Tokenizer_GetArgInteger(0);
  	if (reg < 0 || reg > 255) {
    	return CMD_RES_BAD_ARGUMENT;
  	}
  	int val = Tokenizer_GetArgInteger(1);
  	if (val > 65535) {
    	return CMD_RES_BAD_ARGUMENT;
  	}
  	int result = HLW8112_WriteRegister16((uint8_t)reg, (uint16_t)val);
  	ADDLOG_INFO(LOG_FEATURE_CMD, "HLW8112_write_reg result %d", result);

  	int cr = HLW8112_CheckCoeffs();
  	if (cr > 0) {
    	HLW8112_UpdateCoeff();
  	}
  return CMD_RES_OK;
}
static commandResult_t HLW8112_read_reg(const void *context, const char *cmd, const char *args, int cmdFlags) {

  	Tokenizer_TokenizeString(args, TOKENIZER_ALLOW_QUOTES);
  	if (Tokenizer_CheckArgsCountAndPrintWarning(cmd, 2)) {
    	return CMD_RES_NOT_ENOUGH_ARGUMENTS;
  	}
  	int reg = Tokenizer_GetArgInteger(0);
  	if (reg < 0 || reg > 255) {
    	return CMD_RES_BAD_ARGUMENT;
  	}
  	int width = Tokenizer_GetArgInteger(1);
  	if (width > 32) {
    	return CMD_RES_BAD_ARGUMENT;
  	}
  	uint32_t val;
  	int result;
  	if (width == 8) {
    	result = HLW8112_ReadRegister8((uint8_t)reg, (uint8_t *)&val);
  	}
	else if (width == 16) {
    	result = HLW8112_ReadRegister16((uint8_t)reg, (uint16_t *)&val);
  	}
	else if (width == 24) {
    	result = HLW8112_ReadRegister24((uint8_t)reg, &val);
  	}
  	else if (width == 32) {
    	result = HLW8112_ReadRegister32((uint8_t)reg, &val);
  	}
	else {
    	return CMD_RES_BAD_ARGUMENT;
  	}
  	ADDLOG_INFO( LOG_FEATURE_CMD , "HLW8112_read_reg result %d reg = %02X value = %08X", result, reg , val);

  	return CMD_RES_OK;
}
static commandResult_t HLW8112_print_coeff(const void *context, const char *cmd, const char *args, int cmdFlags) {

  	Tokenizer_TokenizeString(args, TOKENIZER_ALLOW_QUOTES);
  	if (Tokenizer_CheckArgsCountAndPrintWarning(cmd, 0)) {
    	return CMD_RES_NOT_ENOUGH_ARGUMENTS;
  	}
  	HLW8112_UpdateCoeff();
	return CMD_RES_OK;
}


static commandResult_t HLW8112_c(const void *context, const char *cmd, const char *args, int cmdFlags) {

  	Tokenizer_TokenizeString(args, TOKENIZER_ALLOW_QUOTES);
  	if (Tokenizer_CheckArgsCountAndPrintWarning(cmd, 1)) {
    	return CMD_RES_NOT_ENOUGH_ARGUMENTS;
  	}
  	energy_acc_a.Export =  Tokenizer_GetArgFloat(0);
  	HLW8112_save_stats(HLW8112_SAVE_A_EXP);
	return CMD_RES_OK;
}

static commandResult_t HLW8112_a(const void *context, const char *cmd, const char *args, int cmdFlags) {

  	Tokenizer_TokenizeString(args, TOKENIZER_ALLOW_QUOTES);
  	if (Tokenizer_CheckArgsCountAndPrintWarning(cmd, 0)) {
    	return CMD_RES_NOT_ENOUGH_ARGUMENTS;
  	}
  	HLW8112_Restore_Stats();
  	ADDLOG_INFO( LOG_FEATURE_CMD , "HLW8112_a HLW8112_Restore_Stats exp = %.4f imp = %.4f", energy_acc_a.Export, energy_acc_a.Import);
  	return CMD_RES_OK;
}
#endif

#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
static uint32_t HLW8112_BK7238_ParseAt(const uint8_t *rx, int off, uint8_t size) {
	if (size == 4)
		return ((uint32_t)rx[off] << 24) | ((uint32_t)rx[off + 1] << 16)
		       | ((uint32_t)rx[off + 2] << 8) | (uint32_t)rx[off + 3];
	if (size == 3)
		return ((uint32_t)rx[off] << 16) | ((uint32_t)rx[off + 1] << 8) | (uint32_t)rx[off + 2];
	if (size == 2)
		return ((uint32_t)rx[off] << 8) | (uint32_t)rx[off + 1];
	return (uint32_t)rx[off];
}

static commandResult_t HLW8112_CmdSpiRegDbg(const void *context, const char *cmd, const char *args, int cmdFlags) {
	static const struct { uint8_t reg; uint8_t sz; const char *nm; } tbl[] = {
		{ HLW8112_REG_RMSU, 3, "RMSU" },
		{ HLW8112_REG_UFREQ, 2, "UFREQ" },
		{ HLW8112_REG_RMSIA, 3, "RMSIA" },
		{ HLW8112_REG_RMSIB, 3, "RMSIB" },
		{ HLW8112_REG_POWER_PA, 4, "POWER_PA" },
		{ HLW8112_REG_RMSIAC, 2, "RMSIAC" },
		{ HLW8112_REG_RMSIBC, 2, "RMSIBC" },
		{ HLW8112_REG_RMSUC, 2, "RMSUC" },
		{ HLW8112_REG_POWER_PAC, 2, "POWER_PAC" },
	};
	uint8_t tx[1];
	int i;
	(void)context; (void)cmd; (void)args; (void)cmdFlags;
	for (i = 0; i < (int)(sizeof(tbl) / sizeof(tbl[0])); i++) {
		uint8_t rx[5] = { 0 };
		tx[0] = tbl[i].reg & 0x7F;
		HLW8112_SPI_Transact(tx, 1, rx, 5);
		ADDLOG_INFO(LOG_FEATURE_CMD,
			"SPI %s reg=%02X rx=%02X %02X %02X %02X %02X off0=%u off1=%u",
			tbl[i].nm, tbl[i].reg, rx[0], rx[1], rx[2], rx[3], rx[4],
			(unsigned)HLW8112_BK7238_ParseAt(rx, 0, tbl[i].sz),
			(unsigned)HLW8112_BK7238_ParseAt(rx, 1, tbl[i].sz));
	}
	HLW8112_UpdateCoeff();
	ADDLOG_INFO(LOG_FEATURE_CMD,
		"scale v=%.6f ia=%.6f ib=%.6f pa=%.6f pb=%.6f frq=%.1f CLKI=%u",
		device.ScaleFactor.v_rms, device.ScaleFactor.a.i, device.ScaleFactor.b.i,
		device.ScaleFactor.a.p, device.ScaleFactor.b.p, device.ScaleFactor.freq,
		(unsigned)device.CLKI);
	return CMD_RES_OK;
}

static commandResult_t HLW8112_CmdUfreqDbg(const void *context, const char *cmd, const char *args, int cmdFlags) {
	uint8_t tx[1] = { HLW8112_REG_UFREQ & 0x7F };
	uint8_t rx[5] = { 0 };
	int off = -1, le = -1;
	uint32_t parsed;
	double frqScale;
	uint32_t ch1;
	(void)context; (void)cmd; (void)args; (void)cmdFlags;
	HLW8112_SPI_Transact(tx, 1, rx, 5);
	if (device.CLKI > 0)
		frqScale = (double)device.CLKI * 100.0 / 8.0;
	else
		frqScale = (double)DEFAULT_INTERNAL_CLK * 100.0 / 8.0;
	for (int o = 0; o <= 3; o++) {
		for (int l = 0; l <= 1; l++) {
			uint32_t v = HLW8112_BK7238_UfreqPair(rx, o, l);
			uint32_t hz = v ? (uint32_t)(frqScale / (double)v) : 0;
			ADDLOG_INFO(LOG_FEATURE_CMD, "  cand off=%d le=%d v=%u hz~%u", o, l, (unsigned)v, (unsigned)hz);
		}
	}
	parsed = HLW8112_BK7238_ParseUfreq(rx, &off, &le);
	ch1 = parsed ? (uint32_t)(frqScale / (double)parsed) : 0;
	ADDLOG_INFO(LOG_FEATURE_CMD,
		"UFREQ pick rx=%02X %02X %02X %02X %02X CLKI=%u off=%d le=%d reg=%u Ch1~%u V=%d",
		rx[0], rx[1], rx[2], rx[3], rx[4], (unsigned)device.CLKI, off, le,
		(unsigned)parsed, (unsigned)ch1, (int)last_update_data.v_rms);
	return CMD_RES_OK;
}
#endif

void HLW8112_addCommads(void){
	//cmddetail:{"name":"HLW8112_SetClock","args":"TODO",
	//cmddetail:"descr":"",
	//cmddetail:"fn":"HLW8112_SetClock","file":"driver/drv_hlw8112.c","requires":"",
	//cmddetail:"examples":""}
    CMD_RegisterCommand("HLW8112_SetClock", HLW8112_SetClock, NULL);
	//cmddetail:{"name":"HLW8112_SetResistorGain","args":"TODO",
	//cmddetail:"descr":"",
	//cmddetail:"fn":"HLW8112_SetResistorGain","file":"driver/drv_hlw8112.c","requires":"",
	//cmddetail:"examples":""}
    CMD_RegisterCommand("HLW8112_SetResistorGain", HLW8112_SetResistorGain, NULL);
	//cmddetail:{"name":"HLW8112_SetEnergyStat","args":"TODO",
	//cmddetail:"descr":"",
	//cmddetail:"fn":"HLW8112_SetEnergyStat","file":"driver/drv_hlw8112.c","requires":"",
	//cmddetail:"examples":""}
    CMD_RegisterCommand("HLW8112_SetEnergyStat", HLW8112_SetEnergyStat, NULL);
	//cmddetail:{"name":"clear_energy","args":"TODO",
	//cmddetail:"descr":"",
	//cmddetail:"fn":"HLW8112_ClearEnergy","file":"driver/drv_hlw8112.c","requires":"",
	//cmddetail:"examples":""}
    CMD_RegisterCommand("clear_energy", HLW8112_ClearEnergy, NULL);
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	CMD_RegisterCommand("HLW8112_ufreq", HLW8112_CmdUfreqDbg, NULL);
	CMD_RegisterCommand("HLW8112_spireg", HLW8112_CmdSpiRegDbg, NULL);
#endif
#if HLW8112_SPI_RAWACCESS
	//cmddetail:{"name":"HLW8112_write_reg","args":"TODO",
	//cmddetail:"descr":"",
	//cmddetail:"fn":"HLW8112_write_reg","file":"driver/drv_hlw8112.c","requires":"",
	//cmddetail:"examples":""}
	CMD_RegisterCommand("HLW8112_write_reg", HLW8112_write_reg, NULL);
	//cmddetail:{"name":"HLW8112_read_reg","args":"TODO",
	//cmddetail:"descr":"",
	//cmddetail:"fn":"HLW8112_read_reg","file":"driver/drv_hlw8112.c","requires":"",
	//cmddetail:"examples":""}
	CMD_RegisterCommand("HLW8112_read_reg", HLW8112_read_reg, NULL);
	//cmddetail:{"name":"HLW8112_print_coeff","args":"TODO",
	//cmddetail:"descr":"",
	//cmddetail:"fn":"HLW8112_print_coeff","file":"driver/drv_hlw8112.c","requires":"",
	//cmddetail:"examples":""}
	CMD_RegisterCommand("HLW8112_print_coeff", HLW8112_print_coeff, NULL);
	//cmddetail:{"name":"HLW8112_c","args":"TODO",
	//cmddetail:"descr":"",
	//cmddetail:"fn":"HLW8112_c","file":"driver/drv_hlw8112.c","requires":"",
	//cmddetail:"examples":""}
	CMD_RegisterCommand("HLW8112_c", HLW8112_c, NULL);
	//cmddetail:{"name":"HLW8112_a","args":"TODO",
	//cmddetail:"descr":"",
	//cmddetail:"fn":"HLW8112_a","file":"driver/drv_hlw8112.c","requires":"",
	//cmddetail:"examples":""}
	CMD_RegisterCommand("HLW8112_a", HLW8112_a, NULL);
#endif
}

#pragma endregion



#pragma region HLW8112 init

void HLW8112_Shutdown_Pins() {

}
void HLW8112_Init_Channels() {
	CHANNEL_SetType(HLW8112_Channel_Voltage, ChType_Voltage_div100);
	CHANNEL_SetType(HLW8112_Channel_Frequency, ChType_Frequency_div100);
	CHANNEL_SetType(HLW8112_Channel_PowerFactor, ChType_PowerFactor_div1000);
	CHANNEL_SetType(HLW8112_Channel_current_B, ChType_Current_div1000);
	CHANNEL_SetType(HLW8112_Channel_current_A, ChType_Current_div1000);
	CHANNEL_SetType(HLW8112_Channel_power_B, ChType_Power_div100);
	CHANNEL_SetType(HLW8112_Channel_power_A, ChType_Power_div100);
	CHANNEL_SetType(HLW8112_Channel_apparent_power_A, ChType_Power_div100);
	CHANNEL_SetType(HLW8112_Channel_export_B, ChType_EnergyExport_kWh_div1000);
	CHANNEL_SetType(HLW8112_Channel_export_A, ChType_EnergyExport_kWh_div1000);
	CHANNEL_SetType(HLW8112_Channel_import_B, ChType_EnergyImport_kWh_div1000);
	CHANNEL_SetType(HLW8112_Channel_import_A, ChType_EnergyImport_kWh_div1000);
	//CHANNEL_SetType(HLW8112_Channel_ResCof_Voltage, ChType_Custom);
	//CHANNEL_SetType(HLW8112_Channel_ResCof_A, ChType_Custom);
	//CHANNEL_SetType(HLW8112_Channel_ResCof_B, ChType_Custom);
	//CHANNEL_SetType(HLW8112_Channel_Clk, ChType_Custom);

	CHANNEL_SetLabel(HLW8112_Channel_PowerFactor , "Power Factor", 1);
	CHANNEL_SetLabel(HLW8112_Channel_current_B , "Current B", 1);
	CHANNEL_SetLabel(HLW8112_Channel_current_A , "Current A", 1);
	CHANNEL_SetLabel(HLW8112_Channel_power_B , "Power B", 1);
	CHANNEL_SetLabel(HLW8112_Channel_power_A , "Power A", 1);
	CHANNEL_SetLabel(HLW8112_Channel_apparent_power_A , "Apparent Power", 1);
	CHANNEL_SetLabel(HLW8112_Channel_export_B , "Energy Export B", 1);
	CHANNEL_SetLabel(HLW8112_Channel_export_A , "Energy Export A", 1);
	CHANNEL_SetLabel(HLW8112_Channel_import_A , "Energy Import A", 1);
	CHANNEL_SetLabel(HLW8112_Channel_import_B , "Energy Import B", 1);
	//CHANNEL_SetLabel(HLW8112_Channel_ResCof_Voltage, "Voltage Resistor Ratio",1 );
	//CHANNEL_SetLabel(HLW8112_Channel_ResCof_A, "Channel A Resistor Ratio", 1);
	//CHANNEL_SetLabel(HLW8112_Channel_ResCof_B, "Channel b Resistor Ratio",1 );
	//CHANNEL_SetLabel(HLW8112_Channel_ResCof_B, "CLK",1 );

}

void HLW8112_Init_Pins() {

	//TODO INT1/INT2
  	int tmp;
  	tmp = PIN_FindPinIndexForRole(IOR_HLW8112_SCSN, -1);
  	if (tmp != -1) {
    	GPIO_HLW_SCSN = tmp;
  	} else {
    	GPIO_HLW_SCSN = PIN_FindPinIndexForRole(IOR_HLW8112_SCSN, GPIO_HLW_SCSN);
  	}
  
  	HAL_PIN_Setup_Output(GPIO_HLW_SCSN);
  	HAL_PIN_SetOutputValue(GPIO_HLW_SCSN, 1);

}

#pragma region register init and ops


int HLW8112_UpdateCoeffFromRegister(uint16_t reg, uint16_t* sink, char* name) {
	uint16_t regValue;
	int cmdResult;
	cmdResult = HLW8112_ReadRegister16(reg, &regValue);
	ADDLOG_INFO(LOG_FEATURE_ENERGYMETER, "HLW8112_UpdateCoeff %s %i value = %04X",name, cmdResult, regValue);
	if (cmdResult < 0)
		return cmdResult;
	*sink = regValue;
	return 0;
}

void HLW8112_compute_scale_factor() {
	double k2 = device.ResistorCoeff.KU;
	double k1a = device.ResistorCoeff.KIA;
	double k1b = device.ResistorCoeff.KIB;

	double v = (double)device.DeviceRegisterCoeff.RmsUC *10 / (k2 * RMS_U_RESOLUTION);  // mV
	double frq = (double) device.CLKI * 100 / 8;
	double pf =  (double) 1000.0 / ( (double) PF_RESOLUTION );


	double ia = (double) device.DeviceRegisterCoeff.RmsIAC / (k1a * RMS_I_RESOLUTION); // ma
	double ib = (double) device.DeviceRegisterCoeff.RmsIBC / (k1b * RMS_I_RESOLUTION);

	double pa = (double) device.DeviceRegisterCoeff.PowerPAC * 1000 / (k1a * k2 * PWR_RESOLUTION);
	double pb = (double) device.DeviceRegisterCoeff.PowerPBC * 1000 / (k1b * k2 * PWR_RESOLUTION);
	double apa = (double) device.DeviceRegisterCoeff.PowerSC * 1000 / (k1a * k2 * PWR_RESOLUTION);
	double apb = (double) device.DeviceRegisterCoeff.PowerSC * 1000 / (k1b * k2 * PWR_RESOLUTION);

	double ea = (double) device.DeviceRegisterCoeff.EnergyAC * 10000000 / (k1a * k2 * E_RESOLUTION);
	double eb = (double) device.DeviceRegisterCoeff.EnergyAC * 10000000 / (k1b * k2 * E_RESOLUTION);

	device.ScaleFactor.v_rms = v;
	device.ScaleFactor.freq = frq;
	device.ScaleFactor.pf = pf;
	device.ScaleFactor.a.i = ia;
	device.ScaleFactor.a.p = pa;
	device.ScaleFactor.a.ap = apa;
	device.ScaleFactor.a.e = ea;
	device.ScaleFactor.b.i = ib;
	device.ScaleFactor.b.p = pb;
	device.ScaleFactor.b.ap = apb;
	device.ScaleFactor.b.e = eb;
	
}

int HLW8112_UpdateCoeff() {
	CHECK_AND_RETURN(HLW8112_UpdateCoeffFromRegister(HLW8112_REG_HFCONST, &device.HFconst, "HLW8112_REG_HFCONST"));
	CHECK_AND_RETURN(HLW8112_UpdateCoeffFromRegister(HLW8112_REG_RMSIAC, &device.DeviceRegisterCoeff.RmsIAC, "HLW8112_REG_RMSIAC"));
	CHECK_AND_RETURN(HLW8112_UpdateCoeffFromRegister(HLW8112_REG_RMSIBC, &device.DeviceRegisterCoeff.RmsIBC, "HLW8112_REG_RMSIBC"));
	CHECK_AND_RETURN(HLW8112_UpdateCoeffFromRegister(HLW8112_REG_RMSUC, &device.DeviceRegisterCoeff.RmsUC, "HLW8112_REG_RMSUC"));
	CHECK_AND_RETURN(HLW8112_UpdateCoeffFromRegister(HLW8112_REG_POWER_PAC, &device.DeviceRegisterCoeff.PowerPAC, "HLW8112_REG_POWER_PAC"));
	CHECK_AND_RETURN(HLW8112_UpdateCoeffFromRegister(HLW8112_REG_POWER_PBC, &device.DeviceRegisterCoeff.PowerPBC, "HLW8112_REG_POWER_PBC"));
	CHECK_AND_RETURN(HLW8112_UpdateCoeffFromRegister(HLW8112_REG_POWER_SC, &device.DeviceRegisterCoeff.PowerSC, "HLW8112_REG_POWER_SC"));
	CHECK_AND_RETURN(HLW8112_UpdateCoeffFromRegister(HLW8112_REG_ENERGY_AC, &device.DeviceRegisterCoeff.EnergyAC, "HLW8112_REG_ENERGY_AC"));
	CHECK_AND_RETURN(HLW8112_UpdateCoeffFromRegister(HLW8112_REG_ENERGY_BC, &device.DeviceRegisterCoeff.EnergyBC, "HLW8112_REG_ENERGY_BC"));
	HLW8112_compute_scale_factor();
	return 0;
}

int HLW8112_CheckCoeffs() {
  	uint16_t checksum = 0xFFFF 
		+ device.DeviceRegisterCoeff.RmsIAC 
		+ device.DeviceRegisterCoeff.RmsIBC 
		+ device.DeviceRegisterCoeff.RmsUC 
		+ device.DeviceRegisterCoeff.PowerPAC 
		+ device.DeviceRegisterCoeff.PowerPBC 
		+ device.DeviceRegisterCoeff.PowerSC 
		+ device.DeviceRegisterCoeff.EnergyAC 
		+ device.DeviceRegisterCoeff.EnergyBC;
  	checksum = ~checksum;
  
	uint16_t regValue;
  	int cmdResult;
  	cmdResult = HLW8112_ReadRegister16(HLW8112_REG_COF_CHECKSUM, &regValue);
  	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_CheckCoeffs HLW8112_REG_EMUStatus_Chksum %i", cmdResult);
  	if (cmdResult < 0) {
    	ADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "HLW8112_CheckCoeffs HLW8112_REG_EMUStatus_Chksum no good %i", cmdResult);
    	return -1;
  	}

	if (checksum != regValue) {
		ADDLOG_WARN( LOG_FEATURE_ENERGYMETER, "HLW8112_CheckCoeffs Chksum mismatch = computed = %04X read = %04X", checksum, regValue);
		return 1;
	}
	return 0;
}

int HLW8112_SetMainChannel(HLW8112_Channel_t channel) {

	switch (channel) {
	case HLW8112_CHANNEL_A: {
		device.MainChannel = channel;
		return HLW8112_SPI_WriteControl(HLW8112_COMMAND_SELECT_CH_A);
	}
	case HLW8112_CHANNEL_B: {
		device.MainChannel = channel;
		return HLW8112_SPI_WriteControl(HLW8112_COMMAND_SELECT_CH_B);
	}
	}
	return -1;
}


int HLW8112_InitReg() {

	//HLW8112_SPI_WriteControl(HLW8112_COMMAND_RESET);

  	// pga values to config ?? 
	uint16_t PGA = HLW8112_PGA_16;
  	uint16_t PGB = HLW8112_PGA_16;
  	uint16_t PGU = HLW8112_PGA_1;	
	
	#pragma region init registers
	{
    	uint16_t syscon = 0;
    	syscon |= (1 << HLW8112_REG_SYSCON_ADC3ON);
    	syscon |= (1 << HLW8112_REG_SYSCON_ADC2ON);
    	syscon |= (1 << HLW8112_REG_SYSCON_ADC1ON);

    	syscon |= (PGA << HLW8112_REG_SYSCON_PGAIA);
    	syscon |= (PGB << HLW8112_REG_SYSCON_PGAIB);
    	syscon |= (PGU << HLW8112_REG_SYSCON_PGAU);

    	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_InitReg syscon %04X", syscon);
    	HLW8112_WriteRegister16(HLW8112_REG_SYSCON, syscon);

    	uint16_t emucon = 0;
    	emucon |= (1 << HLW8112_REG_EMUCON_PBRUN);
    	emucon |= (1 << HLW8112_REG_EMUCON_PARUN);
    	emucon |= (1 << HLW8112_REG_EMUCON_COMP_OFF);

    	emucon |= (HLW8112_ACTIVE_POW_CALC_METHOD_POS_NEG_ALGEBRAIC << HLW8112_REG_EMUCON_PMODE);

    	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_InitReg emucon %04X",  emucon);
    	HLW8112_WriteRegister16(HLW8112_REG_EMUCON, emucon);

    	uint16_t emucon2 = 0;

    	emucon2 |= (0 << HLW8112_REG_EMUCON2_EPB_CB);
    	emucon2 |= (0 << HLW8112_REG_EMUCON2_EPB_CA);
    	emucon2 |= (1 << HLW8112_REG_EMUCON2_CHS_IB);
    	emucon2 |= (1 << HLW8112_REG_EMUCON2_PFACTOREN);
    	emucon2 |= (1 << HLW8112_REG_EMUCON2_WAVEEN);
    	emucon2 |= (1 << HLW8112_REG_EMUCON2_ZXEN);
    	emucon2 |= (1 << HLW8112_REG_EMUCON2_VREFSEL);

    	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_InitReg emucon2 %04X", emucon2);
    	HLW8112_WriteRegister16(HLW8112_REG_EMUCON2, emucon2);
  	}
	#pragma endregion

  	// device info
	device.ResistorCoeff.KU = CFG_GetPowerMeasurementCalibrationFloat(CFG_OBK_RES_KU, DEFAULT_RES_KU);
	device.ResistorCoeff.KIA = CFG_GetPowerMeasurementCalibrationFloat(CFG_OBK_RES_KIA, DEFAULT_RES_KIA);
	device.ResistorCoeff.KIB = CFG_GetPowerMeasurementCalibrationFloat(CFG_OBK_RES_KIB, DEFAULT_RES_KIB);

	device.PGA.U = PGU;
	device.PGA.IA = PGA;
	device.PGA.IB = PGB;

  	//internal clock

  	device.CLKI =  CFG_GetPowerMeasurementCalibrationInteger(CFG_OBK_CLK, DEFAULT_INTERNAL_CLK);

	device.ScaleFactor.v_rms = 1.0;
	device.ScaleFactor.freq = 1.0;
	device.ScaleFactor.a.i = 1.0;
	device.ScaleFactor.a.p = 1.0;
	device.ScaleFactor.a.e = 1.0;
	device.ScaleFactor.a.ap = 1.0;
	device.ScaleFactor.b.i = 1.0;
	device.ScaleFactor.b.p = 1.0;
	device.ScaleFactor.b.e = 1.0;
	device.ScaleFactor.b.ap = 1.0;

  	int cmdResult;

  	//TODO: to config
  	cmdResult = HLW8112_SetMainChannel(HLW8112_CHANNEL_A);
  	if (cmdResult < 0) {
    	return cmdResult;
  	}

  	HLW8112_UpdateCoeff();
	HLW8112_compute_scale_factor();

  	cmdResult = HLW8112_CheckCoeffs();
  	if (cmdResult > 0) {
    	ADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "HLW8112_InitReg Chksum mismatch");
    	return -2;
  	}
  	return 0;
}

#pragma endregion
#pragma endregion

void HLW8112SPI_Stop(void) {
	HLW8112_Save_Statistics();
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	HLW8112_BK7238_PollSpiShutdown();
#else
	SPI_Deinit();
	SPI_DriverDeinit();
#endif
}

void HLW8112_Init(void) {
	HLW8112_Restore_Stats();
	HLW8112_Init_Channels();
  	HLW8112_addCommads();
  	HLW8112_Init_Pins();

}

void HLW8112SPI_Init(void) {
	HLW8112_Init();
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	HLW8112_BK7238_PollSpiConfigure();
#else
	SPI_DriverInit();
	spi_config_t cfg;
	cfg.role = SPI_ROLE_MASTER;
	cfg.bit_width = SPI_BIT_WIDTH_8BITS;
	cfg.polarity = SPI_POLARITY_HIGH;
	cfg.phase = SPI_PHASE_1ST_EDGE; /* IONE_BK7238_SPI_FIX5 mode2 */
	cfg.wire_mode = SPI_3WIRE_MODE;
	cfg.baud_rate = HLW8112_SPI_BAUD_RATE;
	cfg.bit_order = SPI_MSB_FIRST;
	OBK_SPI_Init(&cfg);
#endif
  	int result = HLW8112_InitReg();
  	ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "HLW8112_InitReg result %i", result);
 
}
#pragma endregion

#pragma region scalers

void HLW8112_ScaleVoltage(uint32_t regValue, int32_t* value){
	if (regValue == 0) {
		*value = 0;
	}
	else if( regValue & HLW8112_INVALID_REGVALUE) {
		*value = 0;
	}
	else {
		double scale = device.ScaleFactor.v_rms;
		int32_t rv = HLW8112_24BitTo32Bit(regValue);
		double v = rv*scale;

		*value = (int32_t)v;
	}
	
}

void HLW8112_ScaleFrequency(uint32_t regValue, int32_t* value){
	if (regValue == 0) {
		*value = 0;
	} else {
		*value = device.ScaleFactor.freq / regValue;
	}
}

void HLW8112_ScaleCurrent(HLW8112_Channel_t channel, uint32_t regValue, int32_t* value){
if (regValue == 0) {
		*value = 0;
	}
	else if( regValue & HLW8112_INVALID_REGVALUE) {
		*value = 0;
	}
	 else {
		double scale = channel == HLW8112_CHANNEL_B ? device.ScaleFactor.b.i : device.ScaleFactor.a.i;
		int32_t rv = HLW8112_24BitTo32Bit(regValue);
		double v = rv*scale;
  
		*value = (int32_t)v;
	}
}

#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
/* IONE_BK7238_REGFIX23: 32-bit 전력 signed — bit23은 부호, INVALID 아님 (0W 고정 버그) */
static int32_t HLW8112_BK7238_ParsePower32(uint32_t raw) {
	if ((raw & 0x00FFFFFF) == 0x00FFFFFF || raw == 0xFFFFFFFF)
		return 0;
	return (int32_t)raw;
}
#endif

void HLW8112_ScalePower(HLW8112_Channel_t channel, uint32_t regValue, int32_t* value){
	if (regValue == 0) {
		*value = 0;
	}
	else if ((regValue & 0x00FFFFFF) == 0x00FFFFFF) {
		*value = 0;
	}
	else {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
		int32_t rv = HLW8112_BK7238_ParsePower32(regValue);
#else
		int32_t rv = (int32_t)regValue;
#endif
		double scale = channel == HLW8112_CHANNEL_B ? device.ScaleFactor.b.p : device.ScaleFactor.a.p;
		double v = rv*scale;
		*value = (int32_t)v;
	}

}

void HLW8112_ScaleEnergy(HLW8112_Channel_t channel, uint32_t regValue, int32_t* value){
	if (regValue == 0) {
		*value = 0;
	} else if ((regValue & 0x00FFFFFF) == 0x00FFFFFF || (regValue & HLW8112_INVALID_REGVALUE)) {
		/* IONE_BK7238_REGFIX19: 무효 에너지 레지스터 */
		*value = 0;
	} else {
		int32_t rv = HLW8112_24BitTo32Bit(regValue);
		double scale = channel == HLW8112_CHANNEL_B ? device.ScaleFactor.b.e : device.ScaleFactor.a.e;
		double v = rv*scale;
		*value = (int32_t)v;
	}
}

void HLW8112_ScaleAparentPower(HLW8112_Channel_t channel, uint32_t regValue, int32_t* value){
	
	if (regValue == 0) {
		*value = 0;
	}
	else if ((regValue & 0x00FFFFFF) == 0x00FFFFFF) {
		*value = 0;
	}
	else {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
		int32_t rv = HLW8112_BK7238_ParsePower32(regValue);
#else
		int32_t rv = (int32_t)regValue;
#endif
		double scale = channel == HLW8112_CHANNEL_B ? device.ScaleFactor.b.ap : device.ScaleFactor.a.ap;
		double v = rv*scale;
		*value = (int32_t)v;
	}
}


void HLW8112_ScalePowerFactor(uint32_t regValue, int16_t* value){
		if (regValue == 0) {
		*value = 0;
	} else {
		int32_t rv = HLW8112_24BitTo32Bit(regValue);
		double scale =  device.ScaleFactor.pf;
		double v = rv*scale;
		*value = (int32_t)v;
	}
}

#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
/* IONE_BK7238_REGFIX25: RoundChPower 스케일 수정 (채널 전력 10배 오류) */
/* IONE_BK7238_REGFIX24: 채널/MQTT 0.1 단위 반올림 (227.1V, 3.6A) */
static float HLW8112_RoundChVoltage(int32_t v_mV) {
	return roundf(v_mV / 1000.0f * 10.0f) * 10.0f;
}
static float HLW8112_RoundChCurrent(int32_t i_mA) {
	return roundf(i_mA / 1000.0f * 10.0f) * 100.0f;
}
static float HLW8112_RoundChFreq(int32_t f) {
	return roundf(f / 100.0f * 10.0f) * 10.0f;
}
static float HLW8112_RoundChPower(int32_t p_mW) {
	/* ChType_Power_div100 + 기존 pa/10 — 채널값×100=W, 0.1W 반올림 */
	return roundf(p_mW / 1000.0f * 10.0f) * 10.0f;
}
static float HLW8112_RoundChPF(int32_t pf) {
	return roundf(pf / 1000.0f * 10.0f) * 100.0f;
}

/* IONE_BK7238_REGFIX27: tele/Energy_Meta_2CH/SENSOR (2CH 미터 전용, STM32 Energy_Meta와 분리) */
#ifndef IONE_MQTT_ENERGY_TOPIC
#define IONE_MQTT_ENERGY_TOPIC "Energy_Meta_2CH"
#endif

static void HLW8112_IoneMqttPublishEnergy(void) {
	char payload[420];
	const char *timeStr;
	float v, cur, p, s, pf, freq, total, reactive;
	char topic[48];

	if (!Main_HasMQTTConnected())
		return;

	v = last_update_data.v_rms / 1000.0f;
	cur = last_update_data.ia_rms / 1000.0f;
	p = last_update_data.pa / 1000.0f;
	s = last_update_data.ap / 1000.0f;
	pf = last_update_data.pf / 1000.0f;
	freq = last_update_data.freq / 100.0f;
	total = (float)last_update_data.ea->Import;

	{
		float pkw = p / 1000.0f;
		float skw = s / 1000.0f;
		float q2 = skw * skw - pkw * pkw;
		reactive = (q2 > 0.0f) ? sqrtf(q2) * 1000.0f : 0.0f;
		if (p < 0.0f)
			reactive = -reactive;
	}

	timeStr = TS2STR(TIME_GetCurrentTime(), TIME_FORMAT_ISO_8601);
	snprintf(payload, sizeof(payload),
		"{\"Time\":\"%s\",\"ENERGY\":{"
		"\"Total\":%.3f,\"Yesterday\":0,\"Today\":0,"
		"\"Power\":%.1f,\"ApparentPower\":%.1f,\"ReactivePower\":%.1f,"
		"\"Factor\":%.2f,\"Voltage\":%.1f,\"Current\":%.3f,\"Frequency\":%.1f}}",
		timeStr, total, p, s, reactive, pf, v, cur, freq);

	snprintf(topic, sizeof(topic), "tele/%s", IONE_MQTT_ENERGY_TOPIC);
	MQTT_Publish(topic, "SENSOR", payload, 0);
}
#endif

static void HLW8112_ScaleAndUpdate(HLW8112_Data_t* data) {

	int16_t power_factor;
	int32_t voltage, frequency, current_a, current_b, power_a, power_b, apparent_power ,energy_a, energy_b;

	HLW8112_ScaleVoltage(data->v_rms, &voltage);
	HLW8112_ScaleFrequency(data->freq, &frequency);
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	/* AC 미인가(<50V) 시 UFREQ 무시 — SPI idle 바이트가 6.82Hz로 고정되는 문제 방지 */
	if (voltage < 50000)
		frequency = 0;
#endif

  	HLW8112_ScaleCurrent(HLW8112_CHANNEL_A, data->ia_rms, &current_a);
  	HLW8112_ScaleCurrent(HLW8112_CHANNEL_B, data->ib_rms, &current_b);

  	HLW8112_ScalePower(HLW8112_CHANNEL_A, data->pa, &power_a);
  	HLW8112_ScalePower(HLW8112_CHANNEL_B, data->pb, &power_b);


  	HLW8112_ScaleEnergy(HLW8112_CHANNEL_A, data->ea, &energy_a);
  	HLW8112_ScaleEnergy(HLW8112_CHANNEL_B, data->eb, &energy_b);


  	HLW8112_ScalePowerFactor(data->pf, &power_factor);

  	HLW8112_ScaleAparentPower(HLW8112_CHANNEL_A, data->ap, &apparent_power);

	//ADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, 
	//	"Values X v=%d f=%d pf=%d ca=%d pa=%d ap=%d ea=%d cb=%d pb=%d eb=%d",
	//	voltage, frequency, power_factor, current_a, power_a, apparent_power, energy_a, current_b, power_b, energy_b);

	last_update_data.v_rms = voltage;
	last_update_data.freq = frequency;
	last_update_data.pf = power_factor;
	last_update_data.ap = apparent_power;
	last_update_data.ia_rms = current_a;
	last_update_data.ib_rms = current_b;
	last_update_data.pa = power_a;
	last_update_data.pb = power_b;

	HLW8112_SaveFlags_t save =  HLW8112_SAVE_NONE;
	if (energy_a != 0) {
		ADDLOG_DEBUG(LOG_FEATURE_ENERGYMETER, "EA val %08X scaled %08X", data->ea, energy_a);
		if (power_a > 0) {
			energy_acc_a.Import += (double)energy_a / 10000000.0;
			save |= HLW8112_SAVE_A_IMP;
		} else {
			energy_acc_a.Export += (double)energy_a / 10000000.0;
			save |= HLW8112_SAVE_A_EXP;
		}
	}
	if (energy_b !=0.0f ) {
		if (power_b > 0) {
			energy_acc_b.Import +=  energy_b / 10000000.0;
			save |= HLW8112_SAVE_B_IMP;
		}else {
			energy_acc_b.Export +=  energy_b/ 10000000.0;
			save |= HLW8112_SAVE_B_EXP;
		}
	}
	if (save != HLW8112_SAVE_NONE) {
		HLW8112_save_stats(save);
	}
    // BL_ProcessUpdate(voltage, current_a, power_a, frequency, energy_a);

	// update
	
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	CHANNEL_Set(HLW8112_Channel_Voltage, HLW8112_RoundChVoltage(last_update_data.v_rms), 0);
	CHANNEL_Set(HLW8112_Channel_Frequency, HLW8112_RoundChFreq(last_update_data.freq), 0);
	CHANNEL_Set(HLW8112_Channel_PowerFactor, HLW8112_RoundChPF(last_update_data.pf), 0);
	CHANNEL_Set(HLW8112_Channel_current_B, HLW8112_RoundChCurrent(last_update_data.ib_rms), 0);
	CHANNEL_Set(HLW8112_Channel_current_A, HLW8112_RoundChCurrent(last_update_data.ia_rms), 0);
	CHANNEL_Set(HLW8112_Channel_power_B, HLW8112_RoundChPower(last_update_data.pb), 0);
	CHANNEL_Set(HLW8112_Channel_power_A, HLW8112_RoundChPower(last_update_data.pa), 0);
	CHANNEL_Set(HLW8112_Channel_apparent_power_A, HLW8112_RoundChPower(last_update_data.ap), 0);
#else
	CHANNEL_Set(HLW8112_Channel_Voltage, last_update_data.v_rms / 10.0, 0);
	CHANNEL_Set(HLW8112_Channel_Frequency,last_update_data.freq , 0);
	CHANNEL_Set(HLW8112_Channel_PowerFactor, last_update_data.pf, 0);
	CHANNEL_Set(HLW8112_Channel_current_B, last_update_data.ib_rms, 0);
	CHANNEL_Set(HLW8112_Channel_current_A,last_update_data.ia_rms , 0);
	CHANNEL_Set(HLW8112_Channel_power_B, last_update_data.pb / 10.0, 0);
	CHANNEL_Set(HLW8112_Channel_power_A, last_update_data.pa / 10.0, 0);
	CHANNEL_Set(HLW8112_Channel_apparent_power_A, last_update_data.ap / 10.0, 0);
#endif
	CHANNEL_Set(HLW8112_Channel_export_B, last_update_data.eb->Export * 1000, 0);
	CHANNEL_Set(HLW8112_Channel_export_A, last_update_data.ea->Export * 1000, 0);
	CHANNEL_Set(HLW8112_Channel_import_B, last_update_data.eb->Import * 1000, 0);
	CHANNEL_Set(HLW8112_Channel_import_A, last_update_data.ea->Import * 1000, 0);
}

#pragma endregion


void HLW8112_RunEverySecond(void) {
	HLW8112_Data_t data;

	HLW8112_ReadRegister24(HLW8112_REG_RMSU, &data.v_rms);
	HLW8112_ReadRegister16(HLW8112_REG_UFREQ, &data.freq);

	HLW8112_ReadRegister24(HLW8112_REG_RMSIA, &data.ia_rms);
	HLW8112_ReadRegister32(HLW8112_REG_POWER_PA, &data.pa);
	HLW8112_ReadRegister24(HLW8112_REG_ENERGY_PA, &data.ea);

	HLW8112_ReadRegister24(HLW8112_REG_RMSIB, &data.ib_rms);

	HLW8112_ReadRegister32(HLW8112_REG_POWER_PB, &data.pb);
	HLW8112_ReadRegister24(HLW8112_REG_ENERGY_PB, &data.eb);

	HLW8112_ReadRegister24(HLW8112_REG_POWER_FACTOR, &data.pf);
	HLW8112_ReadRegister32(HLW8112_REG_POWER_S, &data.ap);
	
	HLW8112_ReadRegister8(HLW8112_REG_SYSSTATUS, &data.sysstat);
	HLW8112_ReadRegister24(HLW8112_REG_EMUSTATUS, &data.emustat);
	HLW8112_ReadRegister16(HLW8112_REG_IF, &data.int_f);



#if HLW8112_SPI_RAWACCESS
	READ_REG(SYSCON,16);
	READ_REG(EMUCON,16);
	READ_REG(HFCONST,16);
	READ_REG(PSTARTA,16);
	READ_REG(PSTARTB,16);
	READ_REG(PAGAIN,16);
	READ_REG(PBGAIN,16);
	READ_REG(PHASEA,8);
	READ_REG(PHASEB,8);
	READ_REG(PAOS,16);
	READ_REG(PBOS,16);
	READ_REG(RMSIAOS,16);
	READ_REG(RMSIBOS,16);
	READ_REG(IBGAIN,16);
	READ_REG(PSGAIN,16);
	READ_REG(PSOS,16);
	READ_REG(EMUCON2,16);
#endif
	
	last_data = data;

    HLW8112_ScaleAndUpdate(&data);
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	HLW8112_IoneMqttPublishEnergy();
#endif
}


#pragma region http ui

void appendBitFlag(char *name, uint32_t regValue, uint8_t bitNum, http_request_t *request) {
	hprintf255(request, "<div class='reg-flag'><span>%s</span><span>%d</span></div>", name, ((regValue & ( 1 << bitNum)) > 0 ? 1 : 0) );
  
}

void appendTableRow(http_request_t *request, char *name,char* unit, int32_t value, int precision, float factor) {
	hprintf255(request,
        "<tr><td><b>%s</b></td><td style='text-align:right;min-width:8em;font-variant-numeric:tabular-nums;'>%.*f</td><td>%s</td></tr>",
		name,   precision, value / factor, unit);
}



void appendChannelTableRow(http_request_t *request, char *name,char* unit, float value_a, float value_b, int precision, float factor) {
	hprintf255(request,
        "<tr><td><b>%s</b></td><td style='text-align:right;min-width:7em;font-variant-numeric:tabular-nums;'>%.*f</td><td>%s</td><td style='text-align:right;min-width:7em;font-variant-numeric:tabular-nums;'>%.*f</td><td>%s</td></tr>",
		name, precision, value_a/ factor, unit,precision, value_b/ factor, unit);
}

void appendRegEdit(http_request_t *request, char *name,uint16_t reg, bool readonly, 
	int32_t currentVal, uint16_t width, bool comp) {
	
	poststr(request,"<form >");
    hprintf255(request,"<label> %s </label>",name);
    hprintf255(request,"<input type='text' name='reg_value' value='%d'>",currentVal);
    hprintf255(request,"<input type='hidden' name='reg' value='%d'/> ",reg);
    hprintf255(request,"<input type='hidden' name='reg_width' value='%d'/> ",width);
    hprintf255(request,"<input type='hidden' name='compliment' value='%d'> ",comp);
    poststr(request,"<input type='hidden' name='reg_edit' value='1'> ");
    poststr(request,"<input type='submit' value='Save' style='width: 80px;'>");
    poststr(request,"</form>");
}

void HLW8112_AppendInformationToHTTPIndexPage(http_request_t *request, int bPreState) {
	if (bPreState) {
		if (http_getArgInteger(request->url, "clear_energy")) {
			char channel[2];
			if (http_getArg(request->url, "channel", channel, sizeof(channel))) {
				if (!strcmp("a" , channel)) {
					HLW8112_Set_EnergyStat(HLW8112_CHANNEL_A,0,0);
				} else {
					HLW8112_Set_EnergyStat(HLW8112_CHANNEL_B,0,0);
				}
			}
		}
		else if (http_getArgInteger(request->url, "reg_edit")) {
			//TODO fix this 
			u16_t reg = http_getArgInteger(request->url, "reg");
			uint32_t val = http_getArgInteger(request->url, "reg_value");
			uint16_t width = http_getArgInteger(request->url, "reg_width");
			bool comp = http_getArgInteger(request->url, "compliment") ==1;
			switch (width){
				case 8: {
					HLW8112_WriteRegister8(reg, val);
					break;
				}
				case 16: {
					HLW8112_WriteRegister16(reg, val);
					break;
				}
			}
		}
		//?action=reg_edit&reg_value=&reg=100&reg_width=24&compliment=1
		return;
	}

	poststr(request, "<hr><table style='width:100%'>");
	appendTableRow(request, "Voltage", "V", last_update_data.v_rms, 1,1000.0f );
	appendTableRow(request, "Frequency", "Hz", last_update_data.freq, 1, 100.0f );
	appendTableRow(request, "Active Power", "W", last_update_data.pa, 1,1000.0f );
	appendTableRow(request, "Apparent Power", "VA", last_update_data.ap, 1, 1000.0f );
	appendTableRow(request, "Power Factor", "", last_update_data.pf, 1, 1000.0f );
	poststr(request, "</table>");

	poststr(request, "<hr><table style='width:100%'>");
	poststr(request, "<tr><th></th><th>Channel A</th><th></th><th>Channel B</th><th></th></tr>");
	appendChannelTableRow(request, "Current", "A", last_update_data.ia_rms, last_update_data.ib_rms, 1,1000 );
	appendChannelTableRow(request, "Active Power", "W", last_update_data.pa, last_update_data.pb, 1,1000 );
	appendChannelTableRow(request, "Import Energy", "KWh", last_update_data.ea->Import, last_update_data.eb->Import, 4 , 1 );
	appendChannelTableRow(request, "Export Energy", "KWh", last_update_data.ea->Export, last_update_data.eb->Export, 4 , 1 );

	poststr(request,
          "<tr><td><b>Actions</b></td><td style='text-align: right;'> \
		  <button style='background-color:red;' onclick='location.href=\"?clear_energy=1&channel=a\"'>Clear</button> \
		  </td><td></td><td style='text-align: right;'>\
		  <button style='background-color:red;' onclick='location.href=\"?clear_energy=1&channel=b\"'>Clear </button> \
		  </td><td></td></tr>");

	poststr(request, "</table>");
#if HLW8112_SPI_RAWACCESS
	poststr(request,"<style> \
                div form { \
                    display: flex; align-items: stretch; gap: 10px;justify-content: center; \
                }\
                div form label {\
                    flex: 1;text-align: right;align-self: center; max-width: 220px; min-width: 100px;\
                    min-width: 90px;\
                }\
				div form input {\
                    width: 100px;\
                }\
            </style>\
            <div style='display: flex; flex-wrap: wrap;'>");
	
	REG_EDIT(SYSCON, 16, false, false);
	REG_EDIT(EMUCON, 16, false, false);
	REG_EDIT(EMUCON2, 16, false, false);
	REG_EDIT(HFCONST, 16, false, false);
	REG_EDIT(PSTARTA, 16, false, false);
	REG_EDIT(PSTARTB, 16, false, false);
	REG_EDIT(PAGAIN, 16, false, false);
	REG_EDIT(PBGAIN, 16, false, false);
	REG_EDIT(PHASEA, 16, false, false);
	REG_EDIT(PHASEB, 16, false, false);
	REG_EDIT(PAOS, 16, false, false);
	REG_EDIT(PBOS, 16, false, false);
	REG_EDIT(RMSIAOS, 16, false, false);
	REG_EDIT(RMSIBOS, 16, false, false);
	REG_EDIT(IBGAIN, 16, false, false);
	REG_EDIT(PSOS, 16, false, false);

	poststr(request, "</div>");
	poststr(request, "<style>\
        div.reg-flag {\
            display: flex;\
            flex-direction: column;\
            align-items: center;\
        }\
        div.flags {\
            display: flex;\
            flex-wrap: wrap;\
        }\
        </style>");


	poststr(request, "<hr><h2>System Status</h4><div class='flags'>");
	appendBitFlag("RST", last_data.sysstat, HLW8112_REG_SYSSTATUS_RST, request);
	appendBitFlag("WREN", last_data.sysstat, HLW8112_REG_SYSSTATUS_WREN, request);
	appendBitFlag("clksel", last_data.sysstat, HLW8112_REG_SYSSTATUS_CLKSEL, request);
	poststr(request, "</div>");
	
	hprintf255(request, "<hr><h2>Emu Status</h4><div class='flags'>");
	// TODO: check sum
	appendBitFlag("ChksumBusy", last_data.emustat, HLW8112_REG_EMUSTATUS_CHKSUMBSY, request);
	appendBitFlag("REVPA", last_data.emustat, HLW8112_REG_EMUSTATUS_REVPA, request);
	appendBitFlag("REVPB", last_data.emustat, HLW8112_REG_EMUSTATUS_REVPB, request);
	appendBitFlag("NopldA", last_data.emustat, HLW8112_REG_EMUSTATUS_NOPLDA, request);
	appendBitFlag("NopldB", last_data.emustat, HLW8112_REG_EMUSTATUS_NOPLDB, request);
	appendBitFlag("Channel_sel", last_data.emustat, HLW8112_REG_EMUSTATUS_CHA_SEL, request);
	poststr(request, "</div>");

	hprintf255(request, "<hr><h2>Interrupt status</h4><div class='flags'>");

	appendBitFlag("DUPDIF", last_data.int_f, HLW8112_REG_IF_DUPDIF, request);
	appendBitFlag("PFBIF", last_data.int_f, HLW8112_REG_IF_PFAIF, request);
	appendBitFlag("PFBIF", last_data.int_f, HLW8112_REG_IF_PFBIF, request);
	appendBitFlag("PEAOIF", last_data.int_f, HLW8112_REG_IF_PEAOIF, request);
	appendBitFlag("PEBOIF", last_data.int_f, HLW8112_REG_IF_PEBOIF, request);
	appendBitFlag("INSTANIF", last_data.int_f, HLW8112_REG_IF_INSTANIF, request);
	appendBitFlag("OIAIF", last_data.int_f, HLW8112_REG_IF_OIAIF, request);
	appendBitFlag("OIBIF", last_data.int_f, HLW8112_REG_IF_OIBIF, request);
	appendBitFlag("OVIF", last_data.int_f, HLW8112_REG_IF_OVIF, request);
	appendBitFlag("OPIF", last_data.int_f, HLW8112_REG_IF_OPIF, request);
	appendBitFlag("SAGIF", last_data.int_f, HLW8112_REG_IF_SAGIF, request);
	appendBitFlag("ZX_IAIF", last_data.int_f, HLW8112_REG_IF_ZX_IAIF, request);
	appendBitFlag("ZX_IBIF", last_data.int_f, HLW8112_REG_IF_ZX_IBIF, request);
	appendBitFlag("ZX_UIF ", last_data.int_f, HLW8112_REG_IF_ZX_UIF, request);
	appendBitFlag("LeakageIF ", last_data.int_f, HLW8112_REG_IF_LEAKAGEIF, request);
	poststr(request, "</div>");
	#endif
}


#pragma endregion


void HLW8112_OnHassDiscovery(const char *topic) {
	//TODO clear energy buttons

    ADDLOG_ERROR(LOG_FEATURE_ENERGYMETER, "HLW8112_OnHassDiscovery");
	HassDeviceInfo* dev_info = NULL;
	dev_info = hass_init_button_device_info("Clear Energy A", "clear_energy", "channel_a", HASS_CATEGORY_DIAGNOSTIC);
	MQTT_QueuePublish(topic, dev_info->channel, hass_build_discovery_json(dev_info), OBK_PUBLISH_FLAG_RETAIN);
	dev_info = hass_init_button_device_info("Clear Energy B", "clear_energy", "channel_b", HASS_CATEGORY_DIAGNOSTIC);
	MQTT_QueuePublish(topic, dev_info->channel, hass_build_discovery_json(dev_info), OBK_PUBLISH_FLAG_RETAIN);
	hass_free_device_info(dev_info);
}

void HLW8112_Save_Statistics() {
	if (DRV_IsRunning("HLW8112SPI")){
		HLW8112_save_stats(HLW8112_SAVE_FORCE);
	}
}
#endif // ENABLE_DRIVER_HLW8112SPI

#pragma GCC diagnostic pop