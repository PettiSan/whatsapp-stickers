@echo off
rem Wrapper: stickers.cmd <pasta-do-pacote> [opcoes]
"%~dp0.venv\Scripts\python.exe" "%~dp0make_stickers.py" %*
