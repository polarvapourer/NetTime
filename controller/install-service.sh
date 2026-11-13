#!/bin/sh
# Run with: sh ./install-service.sh
# Installs NetTime as a systemd service for the current (non-root) user.
# Does NOT switch blocking on, upgrade the OS, install packages, or touch other installed software.
set -eu
if [ "$(id -u)" = "0" ]; then echo "Run as your normal user (e.g. pi), not root."; exit 1; fi
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3)"
USER_NAME="$(id -un)"
DATA="${NETTIME_DATA:-$HOME/.local/share/nettime}"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,7) else 1)' || { echo "Python 3.7+ needed"; exit 1; }
[ -f "$DATA/config.json" ] || { echo "Run 'python3 -m nettime setup' first."; exit 1; }
mkdir -p "$DATA"; chmod 700 "$DATA"; chmod 600 "$DATA"/*.json
UNIT="${NETTIME_UNIT_PATH:-/etc/systemd/system/nettime.service}"  # override only for tests
TMP="$(mktemp)"
cat > "$TMP" <<UNITEOF
[Unit]
Description=NetTime home controller (loopback only)
After=network-online.target time-sync.target
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$DIR
Environment=TZ=Europe/London
Environment=NETTIME_DATA=$DATA
Environment=PYTHONUNBUFFERED=1
ExecStart=$PY -m nettime serve
Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
UMask=0077

[Install]
WantedBy=multi-user.target
UNITEOF
if [ -e "$UNIT" ] && ! cmp -s "$TMP" "$UNIT"; then
  if ! grep -q "NetTime home controller" "$UNIT"; then
    echo "$UNIT exists and is not NetTime's. Not overwriting."; rm -f "$TMP"; exit 1
  fi
  echo "Updating existing NetTime service file."
fi
sudo install -m 644 "$TMP" "$UNIT"
rm -f "$TMP"
sudo systemctl daemon-reload
sudo systemctl enable nettime
sudo systemctl restart nettime
sleep 2
systemctl --no-pager --lines=3 status nettime || true
echo
echo "Installed. A fresh install stays OFF (observation only). If you had already switched blocking on,"
echo "it resumes only after the Pi re-checks the router and the iPad; otherwise it pauses."
echo "On your laptop:  ssh -N -L 8787:127.0.0.1:8787 $USER_NAME@$(hostname).local"
echo "Then open        http://127.0.0.1:8787"
