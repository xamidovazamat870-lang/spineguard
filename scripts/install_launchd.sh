#!/bin/bash
# TGF ni macOS launchd (LaunchAgent) orqali o'rnatadi. Headless rejim.
# Ishlatish: scripts/install_launchd.sh [stable|dev]
set -euo pipefail

CHANNEL="${1:-stable}"
case "$CHANNEL" in
    stable) LABEL="com.tgf.posture";     TGF_HOME_DIR="$HOME/.tgf" ;;
    dev)    LABEL="com.tgf.posture.dev"; TGF_HOME_DIR="$HOME/.tgf-dev" ;;
    *) echo "Kanal: stable yoki dev" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
DEST_DIR="$HOME/Library/LaunchAgents"
DEST="$DEST_DIR/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "Venv topilmadi: $PYTHON_BIN — avval 'make install' ni ishga tushiring." >&2
    exit 1
fi
if ! "$PYTHON_BIN" -c "import tgf, cv2, mediapipe" 2>/dev/null; then
    echo "Venv'da bog'liqliklar yo'q. 'make install' ni qayta ishga tushiring." >&2
    exit 1
fi

mkdir -p "$DEST_DIR" "$TGF_HOME_DIR"

# Xavfsiz almashtirish (sed emas): yo'l ichidagi &, #, bo'shliq muammo bermaydi.
PYTHON_BIN="$PYTHON_BIN" PROJECT_DIR="$PROJECT_DIR" LABEL="$LABEL" CHANNEL="$CHANNEL" \
TGF_HOME_DIR="$TGF_HOME_DIR" SRC="$SCRIPT_DIR/com.tgf.posture.plist" DEST="$DEST" \
"$PYTHON_BIN" - <<'PY'
import os
from xml.sax.saxutils import escape
s = open(os.environ["SRC"], encoding="utf-8").read()
for key, env in (("__PYTHON_BIN__", "PYTHON_BIN"), ("__PROJECT_DIR__", "PROJECT_DIR"),
                 ("__LABEL__", "LABEL"), ("__CHANNEL__", "CHANNEL"), ("__TGF_HOME__", "TGF_HOME_DIR")):
    s = s.replace(key, escape(os.environ[env]))
open(os.environ["DEST"], "w", encoding="utf-8").write(s)
PY

plutil -lint "$DEST" >/dev/null

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$DEST"
launchctl enable "$DOMAIN/$LABEL"
launchctl kickstart -k "$DOMAIN/$LABEL"

echo "O'rnatildi [$CHANNEL]: $DEST"
echo "Holat:   launchctl print $DOMAIN/$LABEL | head -20"
echo "Loglar:  $TGF_HOME_DIR/stdout.log, $TGF_HOME_DIR/stderr.log"
