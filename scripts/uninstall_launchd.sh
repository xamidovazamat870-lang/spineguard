#!/bin/bash
# TGF avtostartini o'chiradi. Ishlatish: scripts/uninstall_launchd.sh [stable|dev]
set -euo pipefail

CHANNEL="${1:-stable}"
case "$CHANNEL" in
    stable) LABEL="com.tgf.posture" ;;
    dev)    LABEL="com.tgf.posture.dev" ;;
    *) echo "Kanal: stable yoki dev" >&2; exit 2 ;;
esac
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [ -f "$DEST" ]; then
    rm -f "$DEST"
    echo "O'chirildi [$CHANNEL]: $DEST"
else
    echo "Topilmadi: $DEST (allaqachon o'chirilgan bo'lishi mumkin)"
fi
