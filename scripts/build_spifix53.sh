#!/usr/bin/env bash
set -euo pipefail
cd /mnt/c/ST/WORKS/OpenBK7238_Energy

if [[ ! -f sdk/beken_freertos_sdk/build.sh ]]; then
  echo "beken submodule init..."
  git submodule update --init --depth 1 sdk/beken_freertos_sdk
fi

for s in spi tune tune7 tune8 tune9 tune10 tune11 tune12 tune13 tune14 tune15 tune16 \
  tune17 tune18 tune19 tune20 tune21 tune22 tune23 tune24 tune25 tune26 tune27 tune28 \
  tune29 tune30 tune31 tune32 tune33 tune34 tune35 tune36 tune37 tune38 tune39 tune40 \
  tune41 tune42 tune43 tune44 tune45 tune46 tune47 tune48 tune49 tune50 tune51 tune52 tune53; do
  python3 "OpenBK7238_Energy_Version1/scripts/hlw8112_bk7238_${s}.py"
done

SHA="$(git rev-parse --short=12 HEAD 2>/dev/null || echo nogit)"
APP_VER="${SHA}_hlw8112_spifix53"
echo "make APP_VER=${APP_VER}"
make -j"$(nproc)" APP_VERSION="${APP_VER}" APP_NAME=OpenBK7238 VARIANT=hlw8112 OpenBK7238

RBL="output/${APP_VER}/OpenBK7238_${APP_VER}.rbl"
echo "BUILD OK: ${RBL}"
ls -la "${RBL}"
