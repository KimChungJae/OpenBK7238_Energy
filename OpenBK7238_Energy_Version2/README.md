# OpenBK7238 Energy Version2

**대상:** PJ-1103C (Tuya dual meter, TuyaMCU UART)

| 항목 | 값 |
|------|-----|
| 폴더 | `OpenBK7238_Energy_Version2/` (PJ-1103C 전용) |
| CI | [Build OpenBK7238 Energy Version2](../.github/workflows/OpenBK7238_Energy_Version2.yml) |
| 펌웨어 | Actions Artifacts → `OpenBK7238_Energy_Version2_UA_*.bin` |
| VARIANT | `energy_v2` |
| Startup | [startup/autoexec.txt](startup/autoexec.txt) |
| 드라이버 | `startDriver TuyaMCU` + `startDriver IONEEnergy` |

## 로컬 빌드

저장소 루트에서:

```bash
make APP_VERSION=local_v2 APP_NAME=OpenBK7238_Energy_Version2 VARIANT=energy_v2 OpenBK7238
```

## MQTT

Version1과 동일: `tele/IONE-Energy-Meta-2CH_XXXXXX/SENSOR` JSON (H750 호환).  
채널 `/1/get` … `/13/get` 개별 발행은 차단됩니다.

전체 비교: [docs/IONE_Energy_Versions.md](../docs/IONE_Energy_Versions.md)
