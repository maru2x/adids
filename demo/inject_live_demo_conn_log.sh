#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
ROOT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

ts="$(date +%s)"
uid="Cmanual${ts}"
src_ip="${1:-192.168.10.50}"
dst_ip="${2:-192.168.10.112}"

docker compose -p adids-demo -f "$ROOT_DIR/docker-compose.demo.yml" stop zeek-local-live >/dev/null 2>&1 || true

docker run --rm \
    -v "$ROOT_DIR/data/logs/zeek/live/local_iot:/logs" \
    alpine:3.20 \
    sh -lc "mkdir -p /logs/current && printf '%s\\n' '{\"ts\":${ts}.0,\"uid\":\"${uid}\",\"id.orig_h\":\"${src_ip}\",\"id.orig_p\":42310,\"id.resp_h\":\"${dst_ip}\",\"id.resp_p\":2223,\"proto\":\"tcp\",\"conn_state\":\"OTH\",\"local_orig\":true,\"local_resp\":true,\"missed_bytes\":0,\"orig_pkts\":1,\"orig_ip_bytes\":40,\"resp_pkts\":0,\"resp_ip_bytes\":0,\"duration\":0.02}' >> /logs/current/conn.log"

echo "[demo-live-inject] appended synthetic 2223/tcp record uid=${uid}"
echo "[demo-live-inject] zeek-local-live was stopped to avoid concurrent writes; run 'make demo-live-up' to resume capture"
