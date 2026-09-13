@echo off
rem Cria .venv e instala as dependencias (Windows). Idempotente.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -m venv .venv
.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.venv\Scripts\python.exe -m pip install --quiet --upgrade -r requirements.txt
.venv\Scripts\python.exe -c "import rembg, ultralytics, rapidocr, torch; print('ok: torch', torch.__version__)"
