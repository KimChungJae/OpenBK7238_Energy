# GitHub 저장소 이름 → OpenBK7238_Energy

로컬 폴더(`C:\ST\WORKS\OpenBK7238_Energy`)와 GitHub repo 이름을 맞춥니다.

## 방법 A — 스크립트 (권장)

```powershell
cd C:\ST\WORKS\OpenBK7238_Energy
.\scripts\rename_github_repo.ps1
```

처음 실행 시 브라우저로 GitHub 로그인(`gh auth login`) 후 자동 rename + push 됩니다.

## 방법 B — GitHub 웹

1. https://github.com/KimChungJae/OpenBK7231T_App/settings  
2. **General** → **Repository name** → `OpenBK7238_Energy` → **Rename**

로컬 PC:

```powershell
cd C:\ST\WORKS\OpenBK7238_Energy
git remote set-url origin https://github.com/KimChungJae/OpenBK7238_Energy.git
git fetch origin
```

## 저장소 안 Version 구분

GitHub repo는 **`OpenBK7238_Energy` 하나**이고, 제품별 폴더는 저장소 내부에서 나눕니다.

| 폴더 | 제품 |
|------|------|
| `OpenBK7238_Energy_Version1/` | PM01 / HLW8112 |
| `OpenBK7238_Energy_Version2/` | PJ-1103C / TuyaMCU |
