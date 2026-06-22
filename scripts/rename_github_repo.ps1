# GitHub 저장소 이름: OpenBK7231T_App → OpenBK7238_Energy
# 사전: gh auth login (또는 GITHUB_TOKEN 환경 변수)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$NewName = "OpenBK7238_Energy"
$OldRepo = "KimChungJae/OpenBK7231T_App"
$NewUrl = "https://github.com/KimChungJae/$NewName.git"

if ($env:GITHUB_TOKEN) {
    gh api -X PATCH "repos/$OldRepo" -f "name=$NewName" | Out-Null
} else {
    gh auth status 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "GitHub 로그인 필요: gh auth login"
        gh auth login -h github.com -p https -w
    }
    gh api -X PATCH "repos/$OldRepo" -f "name=$NewName" | Out-Null
}

Write-Host "origin -> $NewUrl"
git remote set-url origin $NewUrl
git fetch origin
git push -u origin main

Write-Host "완료: https://github.com/KimChungJae/$NewName"
