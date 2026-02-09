#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
gcc -O3 -shared -fPIC "${script_dir}/ai_eval.c" -o "${script_dir}/ai_eval.so"
exec python3 "${script_dir}/chess_uci.py" "$@"
