#!/usr/bin/env bash
gcc -O3 -shared -fPIC "$(dirname "$0")/ai_eval.c" -o "$(dirname "$0")/ai_eval.so" && python3 "$(dirname "$0")/chess.py" "$@"
