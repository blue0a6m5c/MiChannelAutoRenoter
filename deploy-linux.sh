#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="michannel-autorenoter"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ $EUID -ne 0 ]]; then
  echo "Run this script as root" >&2
  exit 1
fi

cp "$(dirname "$0")/michannel-autorenoter.service.example" "$SERVICE_FILE"

sed -i "s|/home/your-user/MiChannelAutoRenoter|$(cd "$(dirname "$0")" && pwd)|g" "$SERVICE_FILE"
sed -i "s|your-user|$(logname 2>/dev/null || echo root)|g" "$SERVICE_FILE"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

systemctl status "$SERVICE_NAME" --no-pager
