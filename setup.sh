#!/usr/bin/env sh
# Cria .venv e instala as dependencias (Linux/WSL). Idempotente: rodar de novo so atualiza.
# Sem sudo: o venv nasce sem pip (Ubuntu nao traz ensurepip) e o pip do usuario instala dentro dele.
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv --without-pip .venv
PIP="python3 -m pip --python .venv/bin/python"
$PIP install --quiet --upgrade torch torchvision --index-url https://download.pytorch.org/whl/cpu
$PIP install --quiet --upgrade -r requirements.txt
.venv/bin/python -c "import rembg, ultralytics, rapidocr, torch; print('ok: torch', torch.__version__)"
