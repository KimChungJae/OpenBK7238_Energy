/*
 * IONE BK7238 Energy Meta MQTT — Version1(HLW8112) / Version2(PJ-1103C TuyaMCU) 공통
 * H750 구독: tele/IONE-Energy-Meta-2CH_XXXXXX/SENSOR
 */
#include "../obk_config.h"

#if defined(ENABLE_IONE_ENERGY_MQTT) || defined(ENABLE_DRIVER_IONE_ENERGY_MQTT)

#include "../new_common.h"
#include "../new_pins.h"
#include "../new_cfg.h"
#include "../logging/logging.h"
#include "../libraries/obktime/obktime.h"
#include "../mqtt/new_mqtt.h"
#include "../hal/hal_wifi.h"
#include "../hal/hal_flashVars.h"
#include "../driver/drv_deviceclock.h"
#include "../httpserver/new_http.h"
#include "../cmnds/cmd_public.h"
#include "drv_public.h"
#include "drv_ione_energy_mqtt.h"
#if ENABLE_LITTLEFS
#include "../littlefs/our_lfs.h"
#endif
#include <math.h>
#include <stdio.h>
#include <string.h>

#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
#include <easyflash.h>
#endif

#define LOG_FEATURE LOG_FEATURE_ENERGYMETER

extern int g_doNotPublishChannels;

#if ENABLE_DRIVER_IONE_ENERGY_MQTT
/* PJ-1103C TuyaMCU 채널 매핑 (Document/Tuya 가이드와 동일) */
#define IONE_PJ_CH_VOLTAGE   1
#define IONE_PJ_CH_FREQ      2
#define IONE_PJ_CH_PWR_A     3
#define IONE_PJ_CH_CUR_A     4
#define IONE_PJ_CH_PF_A      5
#define IONE_PJ_CH_KWH_A     6
#define IONE_PJ_CH_PWR_B     7
#define IONE_PJ_CH_CUR_B     8
#define IONE_PJ_CH_PF_B      9
#define IONE_PJ_CH_KWH_B     10
#define IONE_PJ_CH_NET_PWR   13

#define IONE_PJ_TELE_DEFAULT_SEC  10
#define IONE_PJ_PWR_TODAY_MIN_W    5.0f
#define IONE_PJ_TODAY_SANITY_KWH   500.0f
#define IONE_PJ_YESTERDAY_SANITY_KWH 500.0f
#define IONE_MONTH_SANITY_KWH         3000.0f
#define IONE_MONTH_B_ENV               "IONE_MON_B"
#define IONE_IMP_B_ENV                 "IONE_IMP_B"

#define IONE_TELE_SENSOR_MIN_MS        800U   /* SENSOR 연속 발행 간격 — 페이로드 이중·병합 방지 */

static uint16_t g_ione_teleperiod_sec = IONE_PJ_TELE_DEFAULT_SEC;
static uint16_t g_ione_tele_tick;
static uint8_t g_ione_mqtt_was_up;
static uint32_t g_ione_last_sensor_pub_ms;
static uint32_t g_ione_daily_ymd;
static uint8_t g_ione_daily_save_cd;
static float g_ione_today_a;
static float g_ione_today_b;
static float g_ione_yesterday_a;
static float g_ione_yesterday_b;
static float g_ione_import_b;
static float g_ione_month_a;
static float g_ione_month_b;
static uint8_t g_ione_clear_busy;
static uint32_t g_ione_last_clear_ms;
static int g_ione_channels_private_done;

extern int OTA_GetProgress(void);

static void IONE_SanitizeMonthEnergy(float *kwh);
static void IONE_LoadMonthEnergyB(void);
static void IONE_SaveMonthEnergyB(void);
static void IONE_SaveImportB(void);
static void IONE_LoadImportB(void);
static void IONE_SaveDailyEnergy(void);
static void IONE_TeleTryPublish(void);
static int IONE_TeleSensorPublishAllowed(void);
static void IONE_ResetMonthEnergy(void);
static float IONE_EnergyTotalA(void);
static float IONE_EnergyTotalB(void);
static int IONE_ClearEnergyTryBegin(void);
static void IONE_ClearEnergyTryEnd(void);
static void IONE_ClearEnergyChannelA(void);
static void IONE_ClearEnergyChannelB(void);
static void IONE_ClearEnergyBoth(void);
static commandResult_t CMD_IONE_ClearEnergy(const void *context, const char *cmd, const char *args, int cmdFlags);
static commandResult_t CMD_IONE_SetEnergyStat(const void *context, const char *cmd, const char *args, int cmdFlags);
static commandResult_t CMD_IONE_EnergyTotal(const void *context, const char *cmd, const char *args, int cmdFlags);

static int IONE_YmdValid(uint32_t ymd) {
	uint16_t y = (uint16_t)(ymd / 10000u);
	uint8_t m = (uint8_t)((ymd / 100u) % 100u);
	uint8_t d = (uint8_t)(ymd % 100u);

	if (ymd < 20000101u)
		return 0;
	return isValidDate(y, m, d) ? 1 : 0;
}

static void IONE_SanitizeDailyEnergy(void) {
	if (g_ione_today_a < 0.0f || g_ione_today_a > IONE_PJ_TODAY_SANITY_KWH)
		g_ione_today_a = 0.0f;
	if (g_ione_today_b < 0.0f || g_ione_today_b > IONE_PJ_TODAY_SANITY_KWH)
		g_ione_today_b = 0.0f;
	if (g_ione_yesterday_a < 0.0f || g_ione_yesterday_a > IONE_PJ_YESTERDAY_SANITY_KWH)
		g_ione_yesterday_a = 0.0f;
	if (g_ione_yesterday_b < 0.0f || g_ione_yesterday_b > IONE_PJ_YESTERDAY_SANITY_KWH)
		g_ione_yesterday_b = 0.0f;
}

static void IONE_SanitizeMonthEnergy(float *kwh) {
	if (*kwh < 0.0f || *kwh > IONE_MONTH_SANITY_KWH)
		*kwh = 0.0f;
}

static void IONE_LoadMonthEnergyB(void) {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	size_t len = 0;

	g_ione_month_b = 0.0f;
	ef_get_env_blob(IONE_MONTH_B_ENV, &g_ione_month_b, sizeof(g_ione_month_b), &len);
	if (len != sizeof(g_ione_month_b))
		g_ione_month_b = 0.0f;
	IONE_SanitizeMonthEnergy(&g_ione_month_b);
#endif
}

static void IONE_SaveMonthEnergyB(void) {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	ef_set_env_blob(IONE_MONTH_B_ENV, &g_ione_month_b, sizeof(g_ione_month_b));
#endif
}

static void IONE_LoadImportB(void) {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	size_t len = 0;
	float stored = 0.0f;

	ef_get_env_blob(IONE_IMP_B_ENV, &stored, sizeof(stored), &len);
	if (len == sizeof(stored) && stored >= 0.0f && stored <= 999999.0f)
		g_ione_import_b = stored;
#endif
}

static void IONE_SaveImportB(void) {
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	ef_set_env_blob(IONE_IMP_B_ENV, &g_ione_import_b, sizeof(g_ione_import_b));
#endif
}

static void IONE_ResetMonthEnergy(void) {
	g_ione_month_a = 0.0f;
	g_ione_month_b = 0.0f;
	IONE_SaveDailyEnergy();
	IONE_SaveMonthEnergyB();
}

static float IONE_EnergyTotalA(void) {
	return g_ione_month_a + g_ione_yesterday_a + g_ione_today_a;
}

static float IONE_EnergyTotalB(void) {
	return g_ione_month_b + g_ione_yesterday_b + g_ione_today_b;
}

static int IONE_ClearEnergyTryBegin(void) {
	uint32_t now = (uint32_t)rtos_get_time();

	if (g_ione_clear_busy) {
		ADDLOG_WARN(LOG_FEATURE, "clear_energy: 처리 중 — 잠시 후 다시");
		return 0;
	}
	if (g_ione_last_clear_ms != 0U && (now - g_ione_last_clear_ms) < 3000U) {
		ADDLOG_WARN(LOG_FEATURE, "clear_energy: 3초 간격 필요 (all 사용 권장)");
		return 0;
	}
	g_ione_clear_busy = 1;
	return 1;
}

static void IONE_ClearEnergyTryEnd(void) {
	g_ione_last_clear_ms = (uint32_t)rtos_get_time();
	g_ione_clear_busy = 0;
}

static void IONE_ClearEnergyChannelA(void) {
	CHANNEL_SetSmart(IONE_PJ_CH_KWH_A, 0.0f, CHANNEL_SET_FLAG_SILENT);
	g_ione_today_a = 0.0f;
	IONE_SaveDailyEnergy();
	ADDLOG_INFO(LOG_FEATURE, "clear_energy: channel_a Import/Today=0");
}

static void IONE_ClearEnergyChannelB(void) {
	CHANNEL_SetSmart(IONE_PJ_CH_KWH_B, 0.0f, CHANNEL_SET_FLAG_SILENT);
	g_ione_import_b = 0.0f;
	g_ione_today_b = 0.0f;
	IONE_SaveDailyEnergy();
	IONE_SaveImportB();
	ADDLOG_INFO(LOG_FEATURE, "clear_energy: channel_b Import/Today=0");
}

static void IONE_ClearEnergyBoth(void) {
	IONE_ClearEnergyChannelA();
	IONE_ClearEnergyChannelB();
	ADDLOG_INFO(LOG_FEATURE, "clear_energy: A·B Import/Today=0 (flash)");
}

/* Today·Yesterday·Month·Import(Tuya) 전부 0 — 공장 전력 초기화 */
static void IONE_ClearEnergyFactory(void) {
	g_ione_yesterday_a = 0.0f;
	g_ione_yesterday_b = 0.0f;
	g_ione_month_a = 0.0f;
	g_ione_month_b = 0.0f;
	IONE_ClearEnergyBoth();
	IONE_SaveMonthEnergyB();
	ADDLOG_INFO(LOG_FEATURE, "clear_energy factory: Today/Yesterday/Month/Import A·B=0");
}

static void IONE_LoadDailyEnergy(void) {
	ENERGY_METERING_DATA em;
	uint32_t stored;

	memset(&em, 0, sizeof(em));
	HAL_GetEnergyMeterStatus(&em);
	g_ione_today_a = em.TodayConsumpion;
	g_ione_yesterday_a = em.YesterdayConsumption;
	g_ione_today_b = em.ConsumptionHistory[0];
	g_ione_yesterday_b = em.ConsumptionHistory[1];
	IONE_SanitizeDailyEnergy();
#if PLATFORM_BEKEN_NEW && PLATFORM_BK7238
	{
		size_t len_mon_b = 0;
		size_t len_imp_b = 0;
		float probe = 0.0f;

		ef_get_env_blob(IONE_MONTH_B_ENV, &probe, sizeof(probe), &len_mon_b);
		ef_get_env_blob(IONE_IMP_B_ENV, &probe, sizeof(probe), &len_imp_b);
		if (len_mon_b == 0 && len_imp_b == 0) {
			/* 구버전: TotalConsumption = Import_B */
			g_ione_import_b = em.TotalConsumption;
			g_ione_month_a = 0.0f;
		} else {
			g_ione_month_a = em.TotalConsumption;
			IONE_LoadImportB();
		}
	}
#else
	g_ione_import_b = em.TotalConsumption;
	g_ione_month_a = 0.0f;
#endif
	IONE_SanitizeMonthEnergy(&g_ione_month_a);
	if (g_ione_import_b < 0.0f || g_ione_import_b > 999999.0f)
		g_ione_import_b = 0.0f;
	IONE_LoadMonthEnergyB();
	stored = (uint32_t)em.ConsumptionResetTime;
	g_ione_daily_ymd = IONE_YmdValid(stored) ? stored : 0u;
	ADDLOG_INFO(LOG_FEATURE, "Version2: flash Today_A=%.3f Yesterday_A=%.3f Month_A=%.3f Import_B=%.3f ymd=%u",
		g_ione_today_a, g_ione_yesterday_a, g_ione_month_a, g_ione_import_b, (unsigned)g_ione_daily_ymd);
}

static void IONE_SaveDailyEnergy(void) {
	ENERGY_METERING_DATA em;
	int pg;

	pg = OTA_GetProgress();
	if (pg != -1) {
		ADDLOG_WARN(LOG_FEATURE, "Version2: OTA 중 flash 저장 생략 pg=%d", pg);
		return;
	}
	memset(&em, 0, sizeof(em));
	HAL_GetEnergyMeterStatus(&em);
	em.TodayConsumpion = g_ione_today_a;
	em.YesterdayConsumption = g_ione_yesterday_a;
	em.ConsumptionHistory[0] = g_ione_today_b;
	em.ConsumptionHistory[1] = g_ione_yesterday_b;
	em.TotalConsumption = g_ione_month_a;
	em.ConsumptionResetTime = (time_t)g_ione_daily_ymd;
	em.actual_mday = (char)(g_ione_daily_ymd > 0 ? (g_ione_daily_ymd % 100u) : 0);
	HAL_SetEnergyMeterStatus(&em);
}

static int IONE_LocalYmd(void) {
	TimeComponents tc;

	if (!TIME_IsTimeSynced())
		return -1;
	tc = calculateComponents(TIME_GetCurrentTime());
	return (int)((uint32_t)tc.year * 10000u + (uint32_t)tc.month * 100u + tc.day);
}

static void IONE_ChannelSetPrivate(int ch) {
	if (ch < 0 || ch >= 32)
		return;
	BIT_SET(g_doNotPublishChannels, ch);
}

static void IONE_PJ1103C_BlockPerChannelMqtt(void) {
	int ch;
	if (g_ione_channels_private_done)
		return;
	for (ch = 1; ch <= 13; ch++)
		IONE_ChannelSetPrivate(ch);
	g_ione_channels_private_done = 1;
	ADDLOG_INFO(LOG_FEATURE, "Version2: ch1-13 /get MQTT 차단, tele/SENSOR만 사용");
}

static void IONE_PJ1103C_CheckDailyRollover(void) {
	uint32_t ymd;

	if (!TIME_IsTimeSynced())
		return;
	ymd = (uint32_t)IONE_LocalYmd();
	if (ymd == 0 || !IONE_YmdValid(ymd))
		return;
	if (g_ione_daily_ymd == 0) {
		g_ione_daily_ymd = ymd;
		return;
	}
	if (g_ione_daily_ymd == ymd)
		return;
	g_ione_month_a += g_ione_yesterday_a;
	g_ione_month_b += g_ione_yesterday_b;
	IONE_SanitizeMonthEnergy(&g_ione_month_a);
	IONE_SanitizeMonthEnergy(&g_ione_month_b);
	g_ione_yesterday_a = g_ione_today_a;
	g_ione_yesterday_b = g_ione_today_b;
	g_ione_today_a = 0.0f;
	g_ione_today_b = 0.0f;
	g_ione_daily_ymd = ymd;
	IONE_SaveDailyEnergy();
	IONE_SaveMonthEnergyB();
	IONE_SaveImportB();
	ADDLOG_INFO(LOG_FEATURE, "Version2: 일별 리셋 %u Yesterday_A=%.3f Yesterday_B=%.3f Month_A=%.3f Month_B=%.3f",
		(unsigned)ymd, g_ione_yesterday_a, g_ione_yesterday_b,
		g_ione_month_a, g_ione_month_b);
}

static void IONE_PJ1103C_AddDailyImportKwh(float kwh_a, float kwh_b) {
	IONE_PJ1103C_CheckDailyRollover();
	if (kwh_a > 0.0f)
		g_ione_today_a += kwh_a;
	if (kwh_b > 0.0f) {
		g_ione_today_b += kwh_b;
		/* import_b는 IntegratePerSecond에서 이미 더함 */
	}
	if (kwh_a <= 0.0f && kwh_b <= 0.0f)
		return;
	g_ione_daily_save_cd++;
	if (g_ione_daily_save_cd >= 30) {
		g_ione_daily_save_cd = 0;
		IONE_SaveDailyEnergy();
		IONE_SaveImportB();
	}
}

/* autoexec setChannelType이 이미 나눗셈 적용 — GetFinalValue만 사용 (이중 스케일 방지) */
static float IONE_PJ1103C_GetChannel(int ch) {
	return CHANNEL_GetFinalValue(ch);
}

/* PJ-1103C: DP108(Forward B) 미전송·DP107(Reverse A) 오매핑 시 ch10=0 보완 */
static float IONE_PJ1103C_ResolveTotalBkWh(void) {
	float meter_b = IONE_PJ1103C_GetChannel(IONE_PJ_CH_KWH_B);

	if (meter_b > g_ione_import_b + 0.0005f)
		g_ione_import_b = meter_b;
	if (g_ione_import_b > meter_b + 0.0005f)
		return g_ione_import_b;
	return meter_b;
}

static void IONE_PJ1103C_SyncTotalB(void) {
	float total_b = IONE_PJ1103C_ResolveTotalBkWh();
	float meter_b = IONE_PJ1103C_GetChannel(IONE_PJ_CH_KWH_B);

	if (total_b <= meter_b + 0.0005f)
		return;
	CHANNEL_SetSmart(IONE_PJ_CH_KWH_B, total_b, CHANNEL_SET_FLAG_SILENT);
}

/* Version1(HLW8112)와 동일: 1초마다 유효전력(W) 적분 */
static void IONE_PJ1103C_IntegratePerSecond(void) {
	float pa, pb;
	float kwh_a = 0.0f;
	float kwh_b = 0.0f;

	pa = IONE_PJ1103C_GetChannel(IONE_PJ_CH_PWR_A);
	pb = IONE_PJ1103C_GetChannel(IONE_PJ_CH_PWR_B);
	if (pa >= IONE_PJ_PWR_TODAY_MIN_W)
		kwh_a = pa / 3600000.0f;
	if (pb >= IONE_PJ_PWR_TODAY_MIN_W)
		kwh_b = pb / 3600000.0f;

	/* Import_B·Today: B는 NTP 없어도 누적 (DP108/107 오매핑 대비) */
	if (kwh_b > 0.0f) {
		g_ione_import_b += kwh_b;
		g_ione_daily_save_cd++;
		if (g_ione_daily_save_cd >= 30) {
			g_ione_daily_save_cd = 0;
			IONE_SaveDailyEnergy();
			IONE_SaveImportB();
		}
	}

	if (TIME_IsTimeSynced()) {
		if (kwh_a > 0.0f || kwh_b > 0.0f)
			IONE_PJ1103C_AddDailyImportKwh(kwh_a, kwh_b);
	}

	IONE_PJ1103C_SyncTotalB();
}

static void IONE_PJ1103C_ReadSnapshot(ione_energy_mqtt_snapshot_t *snap) {
	float pa, pb, pfa, pfb;

	memset(snap, 0, sizeof(*snap));

	snap->voltage = IONE_PJ1103C_GetChannel(IONE_PJ_CH_VOLTAGE);
	snap->frequency = IONE_PJ1103C_GetChannel(IONE_PJ_CH_FREQ);
	snap->power_a = IONE_PJ1103C_GetChannel(IONE_PJ_CH_PWR_A);
	snap->power_b = IONE_PJ1103C_GetChannel(IONE_PJ_CH_PWR_B);
	snap->current_a = IONE_PJ1103C_GetChannel(IONE_PJ_CH_CUR_A);
	snap->current_b = IONE_PJ1103C_GetChannel(IONE_PJ_CH_CUR_B);
	snap->factor_a = IONE_PJ1103C_GetChannel(IONE_PJ_CH_PF_A);
	snap->factor_b = IONE_PJ1103C_GetChannel(IONE_PJ_CH_PF_B);
	IONE_PJ1103C_SyncTotalB();
	snap->total_a = IONE_PJ1103C_GetChannel(IONE_PJ_CH_KWH_A);
	snap->total_b = IONE_PJ1103C_ResolveTotalBkWh();

	pa = snap->power_a;
	pb = snap->power_b;
	pfa = snap->factor_a;
	pfb = snap->factor_b;

	snap->export_a = 0.0f;
	snap->export_b = 0.0f;
	snap->energy_total_a = IONE_EnergyTotalA();
	snap->energy_total_b = IONE_EnergyTotalB();
	snap->today_a = g_ione_today_a;
	snap->today_b = g_ione_today_b;
	snap->yesterday_a = g_ione_yesterday_a;
	snap->yesterday_b = g_ione_yesterday_b;

	if (pfa > 0.01f) {
		snap->apparent_a = pa / pfa;
		if (snap->apparent_a > 0.0f) {
			float pkw = pa / 1000.0f;
			float skw = snap->apparent_a / 1000.0f;
			float q2 = skw * skw - pkw * pkw;
			snap->reactive_a = (q2 > 0.0f) ? sqrtf(q2) * 1000.0f : 0.0f;
		}
	}
	(void)pfb;
	(void)IONE_PJ1103C_GetChannel(IONE_PJ_CH_NET_PWR);
}

/* tele/SENSOR 최소 발행 간격 — MQTT 재연결+teleperiod 동시·연속 발행 시 구독측 키 중복 병합 완화 */
static int IONE_TeleSensorPublishAllowed(void) {
	uint32_t now = (uint32_t)rtos_get_time();

	if (g_ione_last_sensor_pub_ms != 0U &&
		(now - g_ione_last_sensor_pub_ms) < IONE_TELE_SENSOR_MIN_MS) {
		return 0;
	}
	g_ione_last_sensor_pub_ms = now;
	return 1;
}

static void IONE_TeleTryPublish(void) {
	ione_energy_mqtt_snapshot_t snap;

	if (!Main_HasMQTTConnected())
		return;
	IONE_EnergyMqtt_PublishTeleState();
	if (!IONE_TeleSensorPublishAllowed())
		return;
	IONE_PJ1103C_ReadSnapshot(&snap);
	IONE_EnergyMqtt_PublishTeleSensor(&snap);
}

static commandResult_t CMD_IONE_ClearEnergy(const void *context, const char *cmd, const char *args, int cmdFlags) {
	const char *channel;

	Tokenizer_TokenizeString(args, TOKENIZER_ALLOW_QUOTES);
	if (Tokenizer_CheckArgsCountAndPrintWarning(cmd, 1))
		return CMD_RES_NOT_ENOUGH_ARGUMENTS;
	channel = Tokenizer_GetArg(0);
	if (!strcmp("factory", channel) || !strcmp("full", channel)) {
		if (!IONE_ClearEnergyTryBegin())
			return CMD_RES_BAD_ARGUMENT;
		IONE_ClearEnergyFactory();
		IONE_ClearEnergyTryEnd();
		IONE_TeleTryPublish();
		return CMD_RES_OK;
	}
	if (!strcmp("all", channel) || !strcmp("both", channel) || !strcmp("channel_ab", channel)) {
		if (!IONE_ClearEnergyTryBegin())
			return CMD_RES_BAD_ARGUMENT;
		IONE_ClearEnergyBoth();
		IONE_ClearEnergyTryEnd();
		IONE_TeleTryPublish();
		return CMD_RES_OK;
	}
	if (!strcmp("channel_a", channel) || !strcmp("a", channel)) {
		IONE_ClearEnergyChannelA();
		IONE_TeleTryPublish();
		return CMD_RES_OK;
	}
	if (!strcmp("channel_b", channel) || !strcmp("b", channel)) {
		IONE_ClearEnergyChannelB();
		IONE_TeleTryPublish();
		return CMD_RES_OK;
	}
	ADDLOG_WARN(LOG_FEATURE, "clear_energy: channel_a|channel_b|all|factory");
	return CMD_RES_BAD_ARGUMENT;
}

static commandResult_t CMD_IONE_SetEnergyStat(const void *context, const char *cmd, const char *args, int cmdFlags) {
	float imp_a, exp_a, imp_b, exp_b;

	Tokenizer_TokenizeString(args, TOKENIZER_ALLOW_QUOTES);
	if (Tokenizer_CheckArgsCountAndPrintWarning(cmd, 4))
		return CMD_RES_NOT_ENOUGH_ARGUMENTS;
	imp_a = Tokenizer_GetArgFloat(0);
	exp_a = Tokenizer_GetArgFloat(1);
	imp_b = Tokenizer_GetArgFloat(2);
	exp_b = Tokenizer_GetArgFloat(3);
	(void)exp_a;
	(void)exp_b;
	CHANNEL_SetSmart(IONE_PJ_CH_KWH_A, imp_a, CHANNEL_SET_FLAG_SILENT);
	CHANNEL_SetSmart(IONE_PJ_CH_KWH_B, imp_b, CHANNEL_SET_FLAG_SILENT);
	g_ione_import_b = imp_b;
	if (imp_a == 0.0f)
		g_ione_today_a = 0.0f;
	if (imp_b == 0.0f)
		g_ione_today_b = 0.0f;
	IONE_SaveDailyEnergy();
	IONE_SaveImportB();
	ADDLOG_INFO(LOG_FEATURE, "HLW8112_SetEnergyStat: A=%.3f B=%.3f kWh", imp_a, imp_b);
	IONE_TeleTryPublish();
	return CMD_RES_OK;
}

static commandResult_t CMD_IONE_EnergyTotal(const void *context, const char *cmd, const char *args, int cmdFlags) {
	int val;

	Tokenizer_TokenizeString(args, 0);
	if (Tokenizer_GetArg(0)[0] == 0) {
		ADDLOG_INFO(LOG_FEATURE, "EnergyTotal A=%.3f B=%.3f kWh",
			IONE_EnergyTotalA(), IONE_EnergyTotalB());
		return CMD_RES_OK;
	}
	val = Tokenizer_GetArgInteger(0);
	if (val == 0) {
		IONE_ResetMonthEnergy();
		ADDLOG_INFO(LOG_FEATURE, "EnergyTotal: month A/B reset (H750 검침일)");
		IONE_TeleTryPublish();
		return CMD_RES_OK;
	}
	ADDLOG_WARN(LOG_FEATURE, "EnergyTotal: 0 only (month reset)");
	return CMD_RES_BAD_ARGUMENT;
}

static commandResult_t CMD_IONE_Teleperiod(const void *context, const char *cmd, const char *args, int cmdFlags) {
	uint32_t sec;

	Tokenizer_TokenizeString(args, 0);
	if (Tokenizer_GetArgsCount() < 1)
		return CMD_RES_NOT_ENOUGH_ARGUMENTS;
	sec = (uint32_t)Tokenizer_GetArgInteger(0);
	if (sec < 1)
		sec = 1;
	if (sec > 3600)
		sec = 3600;
	g_ione_teleperiod_sec = (uint16_t)sec;
	g_ione_tele_tick = g_ione_teleperiod_sec;
	ADDLOG_INFO(LOG_FEATURE, "teleperiod: tele/%s/SENSOR+STATE every %u s",
		CFG_GetMQTTClientId(), (unsigned)g_ione_teleperiod_sec);
	IONE_TeleTryPublish();
	return CMD_RES_OK;
}

void IONEEnergyMqtt_Init(void) {
	g_ione_daily_ymd = 0;
	g_ione_daily_save_cd = 0;
	IONE_LoadDailyEnergy();
	g_ione_tele_tick = g_ione_teleperiod_sec;
	g_ione_mqtt_was_up = 0;
	IONE_PJ1103C_BlockPerChannelMqtt();
	if (!DRV_IsRunning("TuyaMCU"))
		DRV_StartDriver("TuyaMCU");
	CMD_RegisterCommand("teleperiod", CMD_IONE_Teleperiod, NULL);
	CMD_RegisterCommand("clear_energy", CMD_IONE_ClearEnergy, NULL);
	CMD_RegisterCommand("HLW8112_SetEnergyStat", CMD_IONE_SetEnergyStat, NULL);
	CMD_RegisterCommand("EnergyTotal", CMD_IONE_EnergyTotal, NULL);
	ADDLOG_INFO(LOG_FEATURE, "OpenBK7238 Energy Version2 (PJ-1103C TuyaMCU) MQTT ready");
}

void IONEEnergyMqtt_RunEverySecond(void) {
	int mqtt_up = Main_HasMQTTConnected() ? 1 : 0;

	IONE_PJ1103C_BlockPerChannelMqtt();
	IONE_PJ1103C_IntegratePerSecond();

	if (mqtt_up && !g_ione_mqtt_was_up) {
		IONE_TeleTryPublish();
		/* 재연결 직후 tele_tick==0이면 같은 초에 teleperiod 발행이 겹침 */
		g_ione_tele_tick = g_ione_teleperiod_sec;
	}
	g_ione_mqtt_was_up = (uint8_t)mqtt_up;

	if (!mqtt_up)
		return;

	if (g_ione_tele_tick > 0)
		g_ione_tele_tick--;
	if (g_ione_tele_tick == 0) {
		g_ione_tele_tick = g_ione_teleperiod_sec;
		IONE_TeleTryPublish();
	}
}

static void IONE_V2_AppendWebTableStyles(http_request_t *request) {
	poststr(request,
		"<style>"
		"#main>h1{max-width:580px;margin:0.35em auto 0.2em;text-align:left;padding:0}"
		".ione-v2-tbl{width:100%;max-width:580px;margin:0.35em auto;border-collapse:collapse;table-layout:fixed}"
		".ione-v2-tbl td,.ione-v2-tbl th{padding:6px 8px;vertical-align:middle}"
		".ione-v2-tbl .ione-lbl{text-align:left;white-space:nowrap;font-weight:bold;padding-left:0}"
		".ione-v2-tbl .ione-ch{text-align:right;font-variant-numeric:tabular-nums;"
		"padding-right:4px;white-space:nowrap}"
		".ione-v2-tbl .ione-line{text-align:left;padding-left:0;padding-right:0}"
		".ione-v2-tbl .ione-line .ione-val{font-variant-numeric:tabular-nums;font-weight:bold}"
		".ione-v2-tbl th.ione-ch{text-align:right;font-weight:normal;color:#ccc}"
		".ione-v2-tbl .ione-unit{color:#b0b0b0;font-size:0.9em;margin-left:3px;font-weight:normal}"
		".ione-v2-tbl tr.ione-hdr th{border-bottom:1px solid #5a5a5a;padding-bottom:8px}"
		".ione-v2-tbl tr.ione-sec td{border-top:1px solid #5a5a5a;padding-top:10px;color:#ccc;"
		"font-size:0.9em;text-align:left;padding-left:0}"
		".ione-v2-tbl tr.ione-sum td{border-top:1px solid #5a5a5a;padding-top:8px}"
		".ione-v2-tbl tr.ione-act td{padding-top:10px;text-align:center}"
		".ione-v2-tbl .ione-btn{background-color:#d43535;color:#fff;border:0;border-radius:4px;"
		"padding:4px 10px;cursor:pointer;width:auto;max-width:130px;"
		"font-size:0.85rem;line-height:1.5rem;display:inline-block}"
		".ione-v2-tbl .ione-btn-sec{background-color:#555}"
		"</style>");
}

static void IONE_V2_AppendSummaryRow(http_request_t *request, const char *name, const char *unit,
		float value, int precision) {
	hprintf255(request,
		"<tr><td class='ione-lbl'>%s</td>"
		"<td class='ione-ch' colspan='2'>%.*f<span class='ione-unit'>%s</span></td></tr>",
		name, precision, value, unit);
}

static void IONE_V2_AppendChannelRow(http_request_t *request, const char *name, const char *unit,
		float value_a, float value_b, int precision) {
	hprintf255(request,
		"<tr><td class='ione-lbl'>%s</td>"
		"<td class='ione-ch'>%.*f<span class='ione-unit'>%s</span></td>"
		"<td class='ione-ch'>%.*f<span class='ione-unit'>%s</span></td></tr>",
		name, precision, value_a, unit, precision, value_b, unit);
}

static void IONE_V2_AppendTotalRow(http_request_t *request, const char *name, const char *unit,
		float total, int precision) {
	hprintf255(request,
		"<tr class='ione-sum'><td colspan='3' class='ione-line'>"
		"<span class='ione-lbl'>%s</span>&nbsp;&nbsp;"
		"<span class='ione-val'>%.*f<span class='ione-unit'>%s</span></span>"
		"</td></tr>",
		name, precision, total, unit);
}

static void IONE_V2_HandleWebActions(http_request_t *request) {
	if (http_getArgInteger(request->url, "clear_energy")) {
		char channel[16];

		if (http_getArg(request->url, "channel", channel, sizeof(channel))) {
			if (!strcmp("factory", channel) || !strcmp("full", channel)) {
				if (IONE_ClearEnergyTryBegin()) {
					IONE_ClearEnergyFactory();
					IONE_ClearEnergyTryEnd();
					IONE_TeleTryPublish();
				}
			} else if (!strcmp("all", channel) || !strcmp("both", channel)) {
				if (IONE_ClearEnergyTryBegin()) {
					IONE_ClearEnergyBoth();
					IONE_ClearEnergyTryEnd();
					IONE_TeleTryPublish();
				}
			} else if (!strcmp("a", channel) || !strcmp("channel_a", channel)) {
				IONE_ClearEnergyChannelA();
				IONE_TeleTryPublish();
			} else if (!strcmp("b", channel) || !strcmp("channel_b", channel)) {
				IONE_ClearEnergyChannelB();
				IONE_TeleTryPublish();
			}
		}
		return;
	}
	if (http_getArgInteger(request->url, "energy_total_reset")) {
		IONE_ResetMonthEnergy();
		IONE_TeleTryPublish();
	}
}

void IONEEnergyMqtt_AppendInformationToHTTPIndexPage(http_request_t *request, int bPreState) {
	ione_energy_mqtt_snapshot_t snap;

	if (bPreState) {
		IONE_V2_HandleWebActions(request);
		return;
	}

	IONE_PJ1103C_ReadSnapshot(&snap);
	IONE_V2_AppendWebTableStyles(request);
	poststr(request, "<h4 style=\"margin:8px 0 4px 0;color:#1565c0\">OpenBK7238 Energy Version2 (PJ-1103C TuyaMCU)</h4>");
	hprintf255(request, "<p style=\"max-width:580px;margin:0.2em auto 0.6em\">tele/%s/SENSOR+STATE · %u s</p>",
		CFG_GetMQTTClientId(), (unsigned)g_ione_teleperiod_sec);
	poststr(request, "<table class='ione-v2-tbl'>");
	poststr(request, "<colgroup>"
		"<col style='width:28%'>"
		"<col style='width:36%'>"
		"<col style='width:36%'>"
		"</colgroup>");
	poststr(request, "<tr class='ione-hdr'><th class='ione-lbl'></th>"
		"<th class='ione-ch'>Channel A</th>"
		"<th class='ione-ch'>Channel B</th></tr>");

	poststr(request, "<tr class='ione-sec'><td colspan='3'>Common</td></tr>");
	IONE_V2_AppendSummaryRow(request, "Voltage", "V", snap.voltage, 1);
	IONE_V2_AppendSummaryRow(request, "Frequency", "Hz", snap.frequency, 2);

	poststr(request, "<tr class='ione-sec'><td colspan='3'>Per Channel</td></tr>");
	IONE_V2_AppendChannelRow(request, "Current", "A", snap.current_a, snap.current_b, 3);
	IONE_V2_AppendChannelRow(request, "Active Power", "W", snap.power_a, snap.power_b, 1);
	IONE_V2_AppendChannelRow(request, "Power Factor", "%", snap.factor_a, snap.factor_b, 1);
	IONE_V2_AppendChannelRow(request, "Import (Tuya)", "kWh", snap.total_a, snap.total_b, 3);
	IONE_V2_AppendChannelRow(request, "Today", "kWh", snap.today_a, snap.today_b, 3);
	IONE_V2_AppendChannelRow(request, "Yesterday", "kWh", snap.yesterday_a, snap.yesterday_b, 3);
	IONE_V2_AppendChannelRow(request, "Energy Total", "kWh",
		snap.energy_total_a, snap.energy_total_b, 3);

	poststr(request, "<tr class='ione-sec'><td colspan='3'>Daily Total (A+B)</td></tr>");
	IONE_V2_AppendTotalRow(request, "Today Total", "kWh", snap.today_a + snap.today_b, 3);
	IONE_V2_AppendTotalRow(request, "Yesterday Total", "kWh", snap.yesterday_a + snap.yesterday_b, 3);
	IONE_V2_AppendTotalRow(request, "Energy Total (A+B)", "kWh",
		snap.energy_total_a + snap.energy_total_b, 3);

	if (!TIME_IsTimeSynced())
		poststr(request,
			"<tr><td colspan='3' class='ione-lbl' style='color:#e65100'>"
			"NTP 미동기 — Today/Yesterday 자정 리셋 불가</td></tr>");

	poststr(request,
		"<tr class='ione-act'><td class='ione-lbl'>Clear Import/Today</td>"
		"<td><button class='ione-btn' onclick='location.href=\"?clear_energy=1&channel=a\"'>Clear A</button></td>"
		"<td><button class='ione-btn' onclick='location.href=\"?clear_energy=1&channel=b\"'>Clear B</button></td>"
		"</tr>");
	poststr(request,
		"<tr class='ione-act'><td class='ione-lbl'>Clear All / Month</td>"
		"<td><button class='ione-btn ione-btn-sec' onclick='location.href=\"?clear_energy=1&channel=all\"'>Clear All</button></td>"
		"<td><button class='ione-btn ione-btn-sec' onclick='location.href=\"?energy_total_reset=1\"'>Reset EnergyTotal</button></td>"
		"</tr>");

	poststr(request,
		"<tr class='ione-act'><td class='ione-lbl'>Full Reset</td>"
		"<td><button class='ione-btn ione-btn-sec' "
		"onclick='if(confirm(\"Today·Yesterday·Month·Import 전부 0으로 초기화합니다.\"))location.href=\"?clear_energy=1&channel=factory\"'>"
		"Factory Reset</button></td>"
		"<td></td>"
		"</tr>");

	poststr(request, "</table>");
}

#if ENABLE_LITTLEFS
/* OTA 시 LFS 영역이 wipe 되면 autoexec.bat이 사라짐 — OpenBK7238_Energy_Version2/startup/autoexec.txt 와 동일 */
static const char g_ione_v2_default_autoexec[] =
	"startDriver TuyaMCU\r\n"
	"startDriver IONEEnergy\r\n"
	"tuyaMcu_setBaudRate 9600\r\n"
	"tuyaMcu_defWiFiState 4\r\n"
	"addRepeatingEvent 10 -1 uartSendHex 55AA0008000007\r\n"
	"setChannelType 1 Voltage_div10\r\n"
	"setChannelType 2 Frequency_div100\r\n"
	"setChannelType 3 Power_div10\r\n"
	"setChannelType 4 Current_div1000\r\n"
	"setChannelType 5 PowerFactor_div100\r\n"
	"setChannelType 6 EnergyTotal_kWh_div100\r\n"
	"setChannelType 7 Power_div10\r\n"
	"setChannelType 8 Current_div1000\r\n"
	"setChannelType 9 PowerFactor_div100\r\n"
	"setChannelType 10 EnergyTotal_kWh_div100\r\n"
	"setChannelType 11 ReadOnly\r\n"
	"setChannelType 12 ReadOnly\r\n"
	"setChannelType 13 Power_div10\r\n"
	"linkTuyaMCUOutputToChannel 112 val 1\r\n"
	"linkTuyaMCUOutputToChannel 111 val 2\r\n"
	"linkTuyaMCUOutputToChannel 101 val 3\r\n"
	"linkTuyaMCUOutputToChannel 113 val 4\r\n"
	"linkTuyaMCUOutputToChannel 110 val 5\r\n"
	"linkTuyaMCUOutputToChannel 106 val 6\r\n"
	"linkTuyaMCUOutputToChannel 105 val 7\r\n"
	"linkTuyaMCUOutputToChannel 114 val 8\r\n"
	"linkTuyaMCUOutputToChannel 121 val 9\r\n"
	"linkTuyaMCUOutputToChannel 108 val 10\r\n"
	"linkTuyaMCUOutputToChannel 102 raw 11\r\n"
	"linkTuyaMCUOutputToChannel 104 raw 12\r\n"
	"linkTuyaMCUOutputToChannel 115 val 13\r\n"
	"setChannelLabel 1 \"Tension\"\r\n"
	"setChannelLabel 2 \"Frequence\"\r\n"
	"setChannelLabel 3 \"Puissance A\"\r\n"
	"setChannelLabel 4 \"Courant A\"\r\n"
	"setChannelLabel 5 \"PowerFactor A\"\r\n"
	"setChannelLabel 6 \"Energie A\"\r\n"
	"setChannelLabel 7 \"Puissance B\"\r\n"
	"setChannelLabel 8 \"Courant B\"\r\n"
	"setChannelLabel 9 \"PowerFactor B\"\r\n"
	"setChannelLabel 10 \"Energie B\"\r\n"
	"setChannelLabel 11 \"Direction A\"\r\n"
	"setChannelLabel 12 \"Direction B\"\r\n"
	"setChannelLabel 13 \"Puissance nette\"\r\n"
	"teleperiod 10\r\n"
	"startDriver NTP\r\n"
	"time_setTZ 9\r\n";

void IONE_EnergyV2_SeedAutoexecIfMissing(void) {
	byte *existing;
	int need_seed = 0;

	/* OTA wipe 후 init_lfs(0)은 마운트 실패 → create=1 로 포맷·마운트 필요 */
	if (!lfs_present())
		init_lfs(1);
	if (!lfs_present()) {
		ADDLOG_ERROR(LOG_FEATURE_ENERGYMETER,
			"IONE V2: LFS 없음 — autoexec.bat 복원 불가");
		return;
	}

	existing = LFS_ReadFile("autoexec.bat");
	if (existing == NULL) {
		need_seed = 1;
	} else {
		if (existing[0] == '\0' || strstr((char *)existing, "startDriver IONEEnergy") == NULL)
			need_seed = 1;
		free(existing);
	}

	if (!need_seed)
		return;

	if (LFS_WriteFile("autoexec.bat",
			(const byte *)g_ione_v2_default_autoexec,
			(int)strlen(g_ione_v2_default_autoexec), false) >= 0) {
		ADDLOG_INFO(LOG_FEATURE_ENERGYMETER,
			"IONE V2: OTA/LFS wipe 후 autoexec.bat 기본값 복원");
	} else {
		ADDLOG_ERROR(LOG_FEATURE_ENERGYMETER,
			"IONE V2: autoexec.bat 기본값 기록 실패");
	}
}
#endif /* ENABLE_LITTLEFS */
#endif /* ENABLE_DRIVER_IONE_ENERGY_MQTT */

static int IONE_TopicBaseMatches(const char *cur, const char *base) {
	size_t blen = strlen(base);

	if (strcmp(cur, base) == 0)
		return 1;
	if (strncmp(cur, base, blen) != 0)
		return 0;
	if (cur[blen] == '\0')
		return 1;
	return (cur[blen] == '_');
}

void IONE_EnergyMqtt_ApplyTopicMacSuffix(void) {
	static const char *bases[] = {
		"IONE-Energy-Meta-2CH",
		"IONE-Energy-Meta-1CH",
		"IONE-Energy-Meta_2CH",
		"IONE-Energy-Meta_1CH",
		"Energy_Meta_2CH",
		"Energy_Meta_1CH",
	};
	unsigned char mac[6];
	char expected[CGF_MQTT_CLIENT_ID_SIZE];
	const char *cur = CFG_GetMQTTClientId();
	size_t i;

	WiFI_GetMacAddress((char *)mac);

	for (i = 0; i < sizeof(bases) / sizeof(bases[0]); i++) {
		const char *base = bases[i];

		if (!IONE_TopicBaseMatches(cur, base))
			continue;

		snprintf(expected, sizeof(expected), "%s_%02X%02X%02X",
			base, mac[3], mac[4], mac[5]);
		if (strcmp(cur, expected) != 0) {
			ADDLOG_INFO(LOG_FEATURE_MAIN, "MQTT Client Topic: %s -> %s", cur, expected);
			CFG_SetMQTTClientId(expected);
		}
		return;
	}
}

/* Tasmota-15.2 support_tasmota.ino MqttShowState()와 동일 구조 */
static void IONE_FormatUptimeStr(int total_seconds, char *out, int outLen) {
	int days = total_seconds / 86400;
	int hours = (total_seconds / 3600) % 24;
	int minutes = (total_seconds / 60) % 60;
	int seconds = total_seconds % 60;

	snprintf(out, outLen, "%dT%02d:%02d:%02d", days, hours, minutes, seconds);
}

void IONE_EnergyMqtt_PublishTeleState(void) {
	char payload[960];
	char topic[64];
	char uptime[20];
	char sleepMode[12];
	const char *timeStr;
	const char *mqttTopic;
	const char *hostname;
	const char *ipStr;
	const char *ssid;
	int heapKb;
	int sleepVal;
	int wifiSignal;
	int wifiRssi;
	int len;

	if (!Main_HasMQTTConnected())
		return;

	timeStr = TS2STR(TIME_GetCurrentTime(), TIME_FORMAT_ISO_8601);
	IONE_FormatUptimeStr(g_secondsElapsed, uptime, sizeof(uptime));
	heapKb = xPortGetFreeHeapSize() / 1024;
	if (g_powersave) {
		strcpy(sleepMode, "Dynamic");
		sleepVal = 50;
	} else {
		strcpy(sleepMode, "None");
		sleepVal = 0;
	}
	wifiSignal = HAL_GetWifiStrength();
	wifiRssi = (wifiSignal + 100) * 2;
	if (wifiRssi < 0)
		wifiRssi = 0;
	if (wifiRssi > 100)
		wifiRssi = 100;
	hostname = CFG_GetShortDeviceName();
	ipStr = HAL_GetMyIPString();
	ssid = CFG_GetWiFiSSID();

	len = snprintf(payload, sizeof(payload),
		"{\"Time\":\"%s\",\"Uptime\":\"%s\",\"UptimeSec\":%d,\"Heap\":%d,"
		"\"SleepMode\":\"%s\",\"Sleep\":%d,\"LoadAvg\":%d,\"MqttCount\":%d,"
		"\"POWER\":\"ON\","
		"\"Wifi\":{\"AP\":1,\"SSId\":\"%s\",\"BSSId\":\"%s\",\"Channel\":%u,"
		"\"Mode\":\"11n\",\"RSSI\":%d,\"Signal\":%d,\"LinkCount\":%d,"
		"\"Downtime\":\"0T00:00:04\"},"
		"\"Hostname\":\"%s\",\"IPAddress\":\"%s\"}",
		timeStr, uptime, g_secondsElapsed, heapKb,
		sleepMode, sleepVal, 19, MQTT_GetConnectEvents(),
		ssid, g_wifi_bssid, (unsigned)g_wifi_channel,
		wifiRssi, wifiSignal, 1,
		hostname, ipStr);
	if (len <= 0 || len >= (int)sizeof(payload))
		return;

	mqttTopic = CFG_GetMQTTClientId();
	snprintf(topic, sizeof(topic), "tele/%s", mqttTopic);
	MQTT_Publish(topic, "STATE", payload, 0);
	ADDLOG_INFO(LOG_FEATURE, "tele/%s/STATE UptimeSec=%d Heap=%d",
		mqttTopic, g_secondsElapsed, heapKb);
}

void IONE_EnergyMqtt_PublishTeleSensor(const ione_energy_mqtt_snapshot_t *snap) {
	char payload[900];
	char topic[64];
	const char *timeStr;
	const char *mqttTopic;
	const char *hostname;
	const char *ipStr;

	if (!snap || !Main_HasMQTTConnected())
		return;

	timeStr = TS2STR(TIME_GetCurrentTime(), TIME_FORMAT_ISO_8601);
	hostname = CFG_GetShortDeviceName();
	ipStr = HAL_GetMyIPString();
	/* ENERGY 키는 각 1회만 — H750/Tasmota 파서 호환 (중복 키 JSON 금지) */
	snprintf(payload, sizeof(payload),
		"{\"Time\":\"%s\",\"ENERGY\":{"
		"\"Total_A\":%.3f,\"Total_B\":%.3f,"
		"\"EnergyTotal_A\":%.3f,\"EnergyTotal_B\":%.3f,"
		"\"Export_A\":%.3f,\"Export_B\":%.3f,"
		"\"Yesterday_A\":%.3f,\"Yesterday_B\":%.3f,"
		"\"Today\":%.3f,\"Yesterday\":%.3f,"
		"\"Today_A\":%.3f,\"Today_B\":%.3f,"
		"\"Power_A\":%.1f,\"Power_B\":%.1f,"
		"\"ApparentPower_A\":%.1f,\"ReactivePower_A\":%.1f,"
		"\"Factor_A\":%.2f,\"Voltage\":%.1f,"
		"\"Current_A\":%.3f,\"Current_B\":%.3f,"
		"\"Frequency\":%.1f},"
		"\"Hostname\":\"%s\",\"IPAddress\":\"%s\"}",
		timeStr,
		snap->total_a, snap->total_b,
		snap->energy_total_a, snap->energy_total_b,
		snap->export_a, snap->export_b,
		snap->yesterday_a, snap->yesterday_b,
		snap->today_a + snap->today_b,
		snap->yesterday_a + snap->yesterday_b,
		snap->today_a, snap->today_b,
		snap->power_a, snap->power_b,
		snap->apparent_a, snap->reactive_a,
		snap->factor_a, snap->voltage,
		snap->current_a, snap->current_b,
		snap->frequency,
		hostname, ipStr);

	mqttTopic = CFG_GetMQTTClientId();
	snprintf(topic, sizeof(topic), "tele/%s", mqttTopic);
	MQTT_Publish(topic, "SENSOR", payload, 0);
	ADDLOG_INFO(LOG_FEATURE, "tele/%s/SENSOR A=%.0fW B=%.0fW Today_A=%.3f",
		mqttTopic, snap->power_a, snap->power_b, snap->today_a);
}

#endif /* ENABLE_IONE_ENERGY_MQTT || ENABLE_DRIVER_IONE_ENERGY_MQTT */
