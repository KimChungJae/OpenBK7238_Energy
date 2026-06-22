# IONE OpenBK7238 Energy Meta — Version1 / Version2

동일 Git 저장소(`KimChungJae/OpenBK7231T_App`) 안에서 **제품별 펌웨어 빌드**를 나눕니다.  
**별도 GitHub 포크는 필요 없습니다.**

## Version1 — OpenBK7238_Energy_Version1

| 항목 | 내용 |
|------|------|
| 대상 | PM01_A003 / T1-U-HL + **HLW8112 SPI** |
| Makefile | `VARIANT=energy_v1` (구 `hlw8112`와 동일) |
| CI | `.github/workflows/build-bk7238-hlw8112.yml` |
| 산출물 | `OpenBK7238_Energy_Version1_UA_*.bin`, `*.rbl` |
| 드라이버 | `startDriver HLW8112` |
| MQTT | `tele/IONE-Energy-Meta-2CH_XXXXXX/SENSOR` + `ENERGY` JSON |

## Version2 — OpenBK7238_Energy_Version2

| 항목 | 내용 |
|------|------|
| 대상 | **PJ-1103C** (Tuya dual meter, **TuyaMCU** UART) |
| Makefile | `VARIANT=energy_v2` |
| CI | `.github/workflows/build-bk7238-energy-v2.yml` |
| 산출물 | `OpenBK7238_Energy_Version2_UA_*.bin`, `*.rbl` |
| 드라이버 | `startDriver TuyaMCU` + `startDriver IONEEnergy` |
| MQTT | **Version1과 동일** `tele/…/SENSOR` JSON (H750 호환) |

## H750 MQTT (공통)

- **Client Topic (Web Config):** `IONE-Energy-Meta-2CH` → 부팅 시 MAC 3바이트 자동: `IONE-Energy-Meta-2CH_7DC112`
- **구독 토픽:** `tele/IONE-Energy-Meta-2CH_XXXXXX/SENSOR`
- **H750 TouchGFX 슬롯:** suffix `7DC112` 등 6자리 MAC 접미사

Version2는 채널 `/1/get` … `/13/get` 개별 발행을 막고 **tele/SENSOR만** 사용합니다.

## PJ-1103C Startup Command 예시

`docs/IONE_Energy_V2_PJ1103C_startup.txt` 참고.

## 로컬 빌드

```bash
# Version1 (HLW8112)
make APP_VERSION=local_v1 APP_NAME=OpenBK7238_Energy_Version1 VARIANT=energy_v1 OpenBK7238

# Version2 (PJ-1103C)
make APP_VERSION=local_v2 APP_NAME=OpenBK7238_Energy_Version2 VARIANT=energy_v2 OpenBK7238
```
