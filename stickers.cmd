@echo off
rem Wrapper: stickers.cmd <pacote> [opcoes]   (<pacote> = nome da pasta em packs/)
"%~dp0.venv\Scripts\python.exe" "%~dp0make_stickers.py" %*
