#!/usr/bin/env sh
# Wrapper: ./stickers.sh <pasta-do-pacote> [opcoes]
exec "$(dirname "$0")/.venv/bin/python" "$(dirname "$0")/make_stickers.py" "$@"
