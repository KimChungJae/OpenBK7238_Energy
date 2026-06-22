# GitHub remote를 OpenBK7238_Energy로 맞춤 (rename 완료 후)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Origin = "https://github.com/KimChungJae/OpenBK7238_Energy.git"

Write-Host "origin -> $Origin"
git remote set-url origin $Origin
git fetch origin
git push -u origin main

Write-Host "완료: $Origin"
