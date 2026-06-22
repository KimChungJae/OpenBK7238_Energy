#ifndef __DRV_IONE_ENERGY_MQTT_H__
#define __DRV_IONE_ENERGY_MQTT_H__

/* IONE BK7238 Energy Meta — H750 tele/{ClientTopic}/SENSOR ENERGY JSON 공통 */

#if defined(ENABLE_IONE_ENERGY_MQTT) || defined(ENABLE_DRIVER_IONE_ENERGY_MQTT)

typedef struct {
	float voltage;
	float frequency;
	float power_a;
	float power_b;
	float current_a;
	float current_b;
	float factor_a;
	float factor_b;
	float total_a;
	float total_b;
	float export_a;
	float export_b;
	float energy_total_a;
	float energy_total_b;
	float today_a;
	float today_b;
	float yesterday_a;
	float yesterday_b;
	float apparent_a;
	float reactive_a;
} ione_energy_mqtt_snapshot_t;

/* Web Client Topic 베이스 + MAC 하위 3바이트 (Version1/2 공통) */
void IONE_EnergyMqtt_ApplyTopicMacSuffix(void);

/* Tasmota tele/STATE — 보일러(Tasmota MqttShowState)와 동일 필드 */
void IONE_EnergyMqtt_PublishTeleState(void);

#if ENABLE_DRIVER_IONE_ENERGY_MQTT
void IONEEnergyMqtt_Init(void);
void IONEEnergyMqtt_RunEverySecond(void);
void IONEEnergyMqtt_AppendInformationToHTTPIndexPage(http_request_t *request, int bPreState);
#endif

/* HLW8112(Version1)에서도 동일 JSON 발행용 */
void IONE_EnergyMqtt_PublishTeleSensor(const ione_energy_mqtt_snapshot_t *snap);

#endif

#endif /* __DRV_IONE_ENERGY_MQTT_H__ */
