#!/usr/bin/env sh
# Wrapper: ./stickers.sh <pacote> [opcoes]   (<pacote> = nome da pasta em packs/)
exec "$(dirname "$0")/.venv/bin/python" "$(dirname "$0")/make_stickers.py" "$@"
