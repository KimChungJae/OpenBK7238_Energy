# GitHub 대시보드에 Version1 / Version2 보이게 하기

**코드 push만으로는 저장소 목록 이름이 바뀌지 않습니다.**  
아래 **GitHub 웹에서 2단계**를 해야 `Top repositories`에 구분됩니다.

---

## 1단계 — Version1: 저장소 이름 변경

1. 브라우저: https://github.com/KimChungJae/OpenBK7231T_App/settings  
2. **General** → **Repository name**  
3. `OpenBK7238_Energy_Version1` 입력 → **Rename**

로컬 PC (한 번만):

```powershell
cd C:\ST\WORKS\OpenBK7238_Energy
git remote set-url origin https://github.com/KimChungJae/OpenBK7238_Energy_Version1.git
git fetch origin
```

---

## 2단계 — Version2: 새 저장소 만들기

1. https://github.com/new  
2. Repository name: **`OpenBK7238_Energy_Version2`**  
3. Public, **README 추가 안 함** (빈 repo) → Create  

로컬 PC — 같은 소스 push:

```powershell
cd C:\ST\WORKS\OpenBK7238_Energy
git remote add version2 https://github.com/KimChungJae/OpenBK7238_Energy_Version2.git
git push -u version2 main
```

또는 스크립트:

```powershell
cd C:\ST\WORKS\OpenBK7238_Energy
.\scripts\setup_github_energy_repos.ps1
```

---

## 결과 (GitHub 대시보드)

| 저장소 | 용도 |
|--------|------|
| `KimChungJae/OpenBK7238_Energy_Version1` | HLW8112 (PM01) — Actions: Energy Version1 |
| `KimChungJae/OpenBK7238_Energy_Version2` | PJ-1103C — Actions: Energy Version2 |

두 repo 모두 **동일 main 브랜치**를 써도 됩니다. CI 워크플로는 각각 Version1/Version2 bin을 빌드합니다.

저장소 **안**에서는 이미 다음 폴더로 제품을 나눕니다:

- `OpenBK7238_Energy_Version1/` — HLW8112 패치 스크립트, PM01 Startup
- `OpenBK7238_Energy_Version2/` — PJ-1103C Startup (`startup/autoexec.txt`)

---

## Description (선택)

각 repo **About** (⚙) 에 한 줄:

- Version1: `BK7238 HLW8112 Energy Meta — OpenBK7238 Energy Version1`
- Version2: `BK7238 PJ-1103C TuyaMCU — OpenBK7238 Energy Version2`
