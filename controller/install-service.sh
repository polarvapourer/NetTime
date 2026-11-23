#!/bin/sh
# Run with: sh ./install-service.sh
# Installs NetTime as a systemd service for the current (non-root) user.
# Does NOT switch blocking on, upgrade the OS, install packages, or touch other installed software.
set -eu
if [ "$(id -u)" = "0" ]; then echo "Run as your normal user (e.g. pi), not root."; exit 1; fi
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${NETTIME_PYTHON:-$(command -v python3)}"
USER_NAME="$(id -un)"
DATA="${NETTIME_DATA:-$HOME/.local/share/nettime}"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,7) else 1)' || { echo "Python 3.7+ needed"; exit 1; }
cd "$DIR"
"$PY" - "$DATA" <<'DATAPY'
import sys
from nettime.store import Store

store = Store(sys.argv[1])
try:
    config = store.load_config()
    if config is None:
        raise ValueError("Run 'python3 -m nettime setup' first.")
    store.load_state()
except (OSError, ValueError) as exc:
    sys.exit(str(exc))
DATAPY
UNIT="${NETTIME_UNIT_PATH:-/etc/systemd/system/nettime.service}"  # override only for tests
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
"$PY" - "$DIR" "$PY" "$USER_NAME" "$DATA" > "$TMP" <<'UNITPY'
import sys

def quoted(value):
    if any(c in value for c in "\n\r\0"):
        raise ValueError("Service paths must not contain control characters")
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'

package, python, user, data = sys.argv[1:]
print("""[Unit]
Description=NetTime home controller (loopback only)
After=network-online.target time-sync.target
Wants=network-online.target

[Service]
User=%s
WorkingDirectory=%s
Environment=%s
Environment=PYTHONUNBUFFERED=1
ExecStart=%s -m nettime serve
Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
UMask=0077

[Install]
WantedBy=multi-user.target
""" % (user, quoted(package), quoted("NETTIME_DATA=" + data), quoted(python)))
UNITPY
if [ -e "$UNIT" ] && ! cmp -s "$TMP" "$UNIT"; then
  if ! grep -q "NetTime home controller" "$UNIT"; then
    echo "$UNIT exists and is not NetTime's. Not overwriting."; exit 1
  fi
  echo "Updating existing NetTime service file."
fi
sudo install -m 644 "$TMP" "$UNIT"
sudo systemctl daemon-reload
sudo systemctl enable nettime
sudo systemctl restart nettime
sleep 2
systemctl --no-pager --lines=3 status nettime || true
echo
echo "Installed. A fresh install stays OFF (observation only). If you had already switched blocking on,"
echo "it resumes only after the controller re-checks the router and selected device; otherwise it pauses."
echo "On your laptop:  ssh -N -L 8787:127.0.0.1:8787 $USER_NAME@$(hostname).local"
echo "Then open        http://127.0.0.1:8787"
