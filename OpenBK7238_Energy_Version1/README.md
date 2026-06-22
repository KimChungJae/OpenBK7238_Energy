# OpenBK7238 Energy Version1

**대상:** PM01_A003 / T1-U-HL + HLW8112 SPI (기존 IONE Energy Meta)

| 항목 | 값 |
|------|-----|
| 폴더 | `OpenBK7238_Energy_Version1/` (HLW8112 전용) |
| CI | [Build OpenBK7238 Energy Version1](../.github/workflows/OpenBK7238_Energy_Version1.yml) |
| 펌웨어 | Actions Artifacts → `OpenBK7238_Energy_Version1_UA_*.bin` |
| VARIANT | `energy_v1` |
| 패치 스크립트 | [scripts/](scripts/) |
| Startup 예시 | [startup/example.txt](startup/example.txt) |
| 드라이버 | `startDriver HLW8112` |

## 로컬 빌드

저장소 루트에서:

```bash
# HLW8112 패치 (CI와 동일 순서)
V1=OpenBK7238_Energy_Version1/scripts
python3 $V1/hlw8112_bk7238_spi.py
# … tune*.py 순서는 .github/workflows/OpenBK7238_Energy_Version1.yml 참고

make APP_VERSION=local_v1 APP_NAME=OpenBK7238_Energy_Version1 VARIANT=energy_v1 OpenBK7238
```

## MQTT

- Client Topic: `IONE-Energy-Meta-2CH` → 부팅 시 MAC 접미사 자동
- 발행: `tele/IONE-Energy-Meta-2CH_XXXXXX/SENSOR` + `ENERGY` JSON (H750 호환)

전체 비교: [docs/IONE_Energy_Versions.md](../docs/IONE_Energy_Versions.md)
