# IONE OpenBK7238 Energy Meta — Version1 / Version2

## 저장소 폴더 구조

Version1과 Version2는 **완전히 다른 최상위 폴더**로 구분합니다.  
OpenBeken 공통 소스(`src/`, `Makefile`)는 루트에 두고, **제품별 문서·스크립트·Startup**은 각 폴더에 둡니다.

```
OpenBK7238_Energy/
├── OpenBK7238_Energy_Version1/    ← PM01 / HLW8112
│   ├── README.md
│   ├── scripts/                   ← hlw8112_bk7238_*.py 패치
│   └── startup/
├── OpenBK7238_Energy_Version2/    ← PJ-1103C / TuyaMCU
│   ├── README.md
│   └── startup/autoexec.txt
├── src/                           ← 공통 펌웨어 소스
└── .github/workflows/
    ├── OpenBK7238_Energy_Version1.yml
    └── OpenBK7238_Energy_Version2.yml
```

| 어디서 구분? | Version1 | Version2 |
|--------------|----------|----------|
| **폴더** | [OpenBK7238_Energy_Version1/](../OpenBK7238_Energy_Version1/) | [OpenBK7238_Energy_Version2/](../OpenBK7238_Energy_Version2/) |
| **Actions** | `Build OpenBK7238 Energy Version1` | `Build OpenBK7238 Energy Version2` |
| **Artifacts** | `OpenBK7238_Energy_Version1_UA_*.bin` | `OpenBK7238_Energy_Version2_UA_*.bin` |

GitHub 저장소: **[KimChungJae/OpenBK7238_Energy](https://github.com/KimChungJae/OpenBK7238_Energy)**  
rename 절차: [GITHUB_저장소_OpenBK7238_Energy_이름변경.md](GITHUB_저장소_OpenBK7238_Energy_이름변경.md)

---

## Version1 — OpenBK7238_Energy_Version1

| 항목 | 내용 |
|------|------|
| 대상 | PM01_A003 / T1-U-HL + **HLW8112 SPI** |
| Makefile | `VARIANT=energy_v1` |
| CI | `.github/workflows/OpenBK7238_Energy_Version1.yml` |
| 패치 | `OpenBK7238_Energy_Version1/scripts/` |
| 드라이버 | `startDriver HLW8112` |
| MQTT | `tele/IONE-Energy-Meta-2CH_XXXXXX/SENSOR` + `ENERGY` JSON |

## Version2 — OpenBK7238_Energy_Version2

| 항목 | 내용 |
|------|------|
| 대상 | **PJ-1103C** (Tuya dual meter, **TuyaMCU** UART) |
| Makefile | `VARIANT=energy_v2` |
| CI | `.github/workflows/OpenBK7238_Energy_Version2.yml` |
| Startup | `OpenBK7238_Energy_Version2/startup/autoexec.txt` |
| 드라이버 | `startDriver TuyaMCU` + `startDriver IONEEnergy` |
| MQTT | Version1과 동일 `tele/…/SENSOR` JSON (H750 호환) |

## H750 MQTT (공통)

- **Client Topic:** `IONE-Energy-Meta-2CH` → 부팅 시 MAC 3바이트: `IONE-Energy-Meta-2CH_7DC112`
- **구독:** `tele/IONE-Energy-Meta-2CH_XXXXXX/SENSOR`

## 로컬 빌드

```bash
# Version1 (HLW8112 — 패치 후)
make APP_VERSION=local_v1 APP_NAME=OpenBK7238_Energy_Version1 VARIANT=energy_v1 OpenBK7238

# Version2 (PJ-1103C)
make APP_VERSION=local_v2 APP_NAME=OpenBK7238_Energy_Version2 VARIANT=energy_v2 OpenBK7238
```
