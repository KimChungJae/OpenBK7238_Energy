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
#include "../mqtt/new_mqtt.h"
#include "../hal/hal_wifi.h"
#include "../driver/drv_deviceclock.h"
#include "../httpserver/new_http.h"
#include "drv_public.h"
#include "drv_ione_energy_mqtt.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

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

static uint16_t g_ione_teleperiod_sec = IONE_PJ_TELE_DEFAULT_SEC;
static uint16_t g_ione_tele_tick;
static uint8_t g_ione_mqtt_was_up;
static int g_ione_last_ymd;
static float g_ione_today_a;
static float g_ione_today_b;
static float g_ione_yesterday_a;
static float g_ione_yesterday_b;
static int g_ione_channels_private_done;

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
	int ymd = IONE_LocalYmd();
	if (ymd < 0)
		return;
	if (g_ione_last_ymd < 0) {
		g_ione_last_ymd = ymd;
		return;
	}
	if (ymd == g_ione_last_ymd)
		return;
	g_ione_yesterday_a = g_ione_today_a;
	g_ione_yesterday_b = g_ione_today_b;
	g_ione_today_a = 0.0f;
	g_ione_today_b = 0.0f;
	g_ione_last_ymd = ymd;
	ADDLOG_INFO(LOG_FEATURE, "Version2: 일별 리셋 Yesterday_A=%.3f Yesterday_B=%.3f",
		g_ione_yesterday_a, g_ione_yesterday_b);
}

static void IONE_PJ1103C_AddTodayKwh(float pa_w, float pb_w) {
	if (pa_w >= IONE_PJ_PWR_TODAY_MIN_W)
		g_ione_today_a += pa_w / 3600000.0f;
	if (pb_w >= IONE_PJ_PWR_TODAY_MIN_W)
		g_ione_today_b += pb_w / 3600000.0f;
}

static float IONE_PJ1103C_ScaleChannel(int ch, float div) {
	return CHANNEL_GetFinalValue(ch) / div;
}

static void IONE_PJ1103C_ReadSnapshot(ione_energy_mqtt_snapshot_t *snap) {
	float pa, pb, pfa, pfb;

	memset(snap, 0, sizeof(*snap));

	snap->voltage = IONE_PJ1103C_ScaleChannel(IONE_PJ_CH_VOLTAGE, 10.0f);
	snap->frequency = IONE_PJ1103C_ScaleChannel(IONE_PJ_CH_FREQ, 100.0f);
	snap->power_a = IONE_PJ1103C_ScaleChannel(IONE_PJ_CH_PWR_A, 10.0f);
	snap->power_b = IONE_PJ1103C_ScaleChannel(IONE_PJ_CH_PWR_B, 10.0f);
	snap->current_a = IONE_PJ1103C_ScaleChannel(IONE_PJ_CH_CUR_A, 1000.0f);
	snap->current_b = IONE_PJ1103C_ScaleChannel(IONE_PJ_CH_CUR_B, 1000.0f);
	snap->factor_a = IONE_PJ1103C_ScaleChannel(IONE_PJ_CH_PF_A, 100.0f);
	snap->factor_b = IONE_PJ1103C_ScaleChannel(IONE_PJ_CH_PF_B, 100.0f);
	snap->total_a = IONE_PJ1103C_ScaleChannel(IONE_PJ_CH_KWH_A, 100.0f);
	snap->total_b = IONE_PJ1103C_ScaleChannel(IONE_PJ_CH_KWH_B, 100.0f);

	pa = snap->power_a;
	pb = snap->power_b;
	pfa = snap->factor_a;
	pfb = snap->factor_b;

	IONE_PJ1103C_AddTodayKwh(pa, pb);

	snap->export_a = 0.0f;
	snap->export_b = 0.0f;
	snap->energy_total_a = snap->total_a;
	snap->energy_total_b = snap->total_b;
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
	(void)IONE_PJ1103C_ScaleChannel(IONE_PJ_CH_NET_PWR, 10.0f);
}

static void IONE_TeleTryPublish(void) {
	ione_energy_mqtt_snapshot_t snap;

	if (!Main_HasMQTTConnected())
		return;
	IONE_PJ1103C_ReadSnapshot(&snap);
	IONE_EnergyMqtt_PublishTeleSensor(&snap);
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
	ADDLOG_INFO(LOG_FEATURE, "teleperiod: tele/%s/SENSOR every %u s",
		CFG_GetMQTTClientId(), (unsigned)g_ione_teleperiod_sec);
	IONE_TeleTryPublish();
	return CMD_RES_OK;
}

void IONEEnergyMqtt_Init(void) {
	g_ione_last_ymd = -1;
	g_ione_tele_tick = g_ione_teleperiod_sec;
	g_ione_mqtt_was_up = 0;
	IONE_PJ1103C_BlockPerChannelMqtt();
	if (!DRV_IsRunning("TuyaMCU"))
		DRV_StartDriver("TuyaMCU");
	CMD_RegisterCommand("teleperiod", CMD_IONE_Teleperiod, NULL);
	ADDLOG_INFO(LOG_FEATURE, "OpenBK7238 Energy Version2 (PJ-1103C TuyaMCU) MQTT ready");
}

void IONEEnergyMqtt_RunEverySecond(void) {
	int mqtt_up = Main_HasMQTTConnected() ? 1 : 0;

	IONE_PJ1103C_BlockPerChannelMqtt();
	IONE_PJ1103C_CheckDailyRollover();

	if (mqtt_up && !g_ione_mqtt_was_up)
		IONE_TeleTryPublish();
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

void IONEEnergyMqtt_AppendInformationToHTTPIndexPage(http_request_t *request, int bPreState) {
	if (bPreState)
		poststr(request, "<h4 style=\"margin:8px 0 4px 0;color:#1565c0\">OpenBK7238 Energy Version2 (PJ-1103C TuyaMCU)</h4>");
	else
		hprintf255(request, "<p>Energy Version2 · tele/%s/SENSOR · %u s</p>",
			CFG_GetMQTTClientId(), (unsigned)g_ione_teleperiod_sec);
}
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

void IONE_EnergyMqtt_PublishTeleSensor(const ione_energy_mqtt_snapshot_t *snap) {
	char payload[800];
	char topic[64];
	const char *timeStr;
	const char *mqttTopic;

	if (!snap || !Main_HasMQTTConnected())
		return;

	timeStr = TS2STR(TIME_GetCurrentTime(), TIME_FORMAT_ISO_8601);
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
		"\"Frequency\":%.1f}}",
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
		snap->frequency);

	mqttTopic = CFG_GetMQTTClientId();
	snprintf(topic, sizeof(topic), "tele/%s", mqttTopic);
	MQTT_Publish(topic, "SENSOR", payload, 0);
	ADDLOG_INFO(LOG_FEATURE, "tele/%s/SENSOR A=%.0fW B=%.0fW Today_A=%.3f",
		mqttTopic, snap->power_a, snap->power_b, snap->today_a);
}

#endif /* ENABLE_IONE_ENERGY_MQTT || ENABLE_DRIVER_IONE_ENERGY_MQTT */
