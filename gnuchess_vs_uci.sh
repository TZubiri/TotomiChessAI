#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${script_dir}/uci_match.py" --our-engine "${script_dir}/chess_uci.sh" --gnuchess "/usr/games/gnuchess --uci" "$@"
