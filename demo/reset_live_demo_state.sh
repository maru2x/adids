#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
ROOT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

mkdir -p \
    "$ROOT_DIR/data/logs/zeek/live/local_iot/current" \
    "$ROOT_DIR/data/csv/live/local_iot_demo" \
    "$ROOT_DIR/data/live/state"

find \
    "$ROOT_DIR/data/logs/zeek/live/local_iot/current" \
    "$ROOT_DIR/data/csv/live/local_iot_demo" \
    "$ROOT_DIR/data/live/state" \
    -type f -delete

echo "[demo-live-reset] cleared generated logs, CSVs, and state files"
