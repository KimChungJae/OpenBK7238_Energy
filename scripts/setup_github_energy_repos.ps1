# GitHub 저장소 Version1 rename + Version2 remote push (로컬)
# 사전 조건: GitHub 웹에서
#   1) OpenBK7231T_App → OpenBK7238_Energy_Version1 rename 완료
#   2) OpenBK7238_Energy_Version2 빈 repo 생성 완료

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$OriginV1 = "https://github.com/KimChungJae/OpenBK7238_Energy_Version1.git"
$RemoteV2 = "https://github.com/KimChungJae/OpenBK7238_Energy_Version2.git"

Write-Host "origin -> $OriginV1"
git remote set-url origin $OriginV1

if (-not (git remote | Select-String -Pattern '^version2$' -Quiet)) {
    git remote add version2 $RemoteV2
} else {
    git remote set-url version2 $RemoteV2
}

Write-Host "fetch origin..."
git fetch origin

Write-Host "push origin main..."
git push -u origin main

Write-Host "push version2 main..."
git push -u version2 main

Write-Host "완료. GitHub 대시보드에서 두 저장소 이름을 확인하세요."
