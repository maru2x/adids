#!/bin/sh
set -eu

find_live_interface() {
    if [ -n "${ZEEK_LIVE_INTERFACE:-}" ] && [ -e "/sys/class/net/$ZEEK_LIVE_INTERFACE" ]; then
        printf '%s\n' "$ZEEK_LIVE_INTERFACE"
        return 0
    fi

    default_if="$(ip route show default 2>/dev/null | awk '/default/ {print $5; exit}')"
    if [ -n "$default_if" ] && [ -e "/sys/class/net/$default_if" ]; then
        printf '%s\n' "$default_if"
        return 0
    fi

    for candidate in $(ls /sys/class/net); do
        case "$candidate" in
            lo|docker*|br-*|veth*|tailscale*)
                continue
                ;;
        esac
        state="$(cat "/sys/class/net/$candidate/operstate" 2>/dev/null || true)"
        if [ "$state" = "up" ] || [ "$state" = "unknown" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

iface="$(find_live_interface)" || {
    echo "[zeek-local-live] 監視インターフェースを自動検出できませんでした" >&2
    echo "[zeek-local-live] 候補一覧:" >&2
    for candidate in $(ls /sys/class/net); do
        state="$(cat "/sys/class/net/$candidate/operstate" 2>/dev/null || true)"
        echo "  - $candidate ($state)" >&2
    done
    exit 1
}

mkdir -p /logs/current
cd /logs/current
echo "[zeek-local-live] interface=$iface checksum_mode=ignore"
exec /usr/local/zeek/bin/zeek -C -i "$iface" LogAscii::use_json=T
