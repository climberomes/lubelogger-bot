#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  LubeLogger Discord Bot — installer for Debian/Ubuntu LXC
# ─────────────────────────────────────────────────────────────
set -euo pipefail

INSTALL_DIR="/opt/lubelogger-bot"
SERVICE_USER="lubebot"
SERVICE_FILE="lubelogger-bot.service"

echo "==> Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip

echo "==> Creating service user '${SERVICE_USER}'..."
id "${SERVICE_USER}" &>/dev/null || useradd -r -s /usr/sbin/nologin "${SERVICE_USER}"

echo "==> Copying bot files to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
cp bot.py requirements.txt "${INSTALL_DIR}/"

echo "==> Creating Python virtual environment..."
python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install -q --upgrade pip
"${INSTALL_DIR}/venv/bin/pip" install -q -r "${INSTALL_DIR}/requirements.txt"

if [ ! -f "${INSTALL_DIR}/.env" ]; then
    echo "==> Copying .env.example → ${INSTALL_DIR}/.env"
    cp .env.example "${INSTALL_DIR}/.env"
    echo ""
    echo "  ⚠️  Edit ${INSTALL_DIR}/.env before starting the service!"
    echo "      Fill in DISCORD_TOKEN and LUBELOGGER_URL at minimum."
    echo ""
fi

echo "==> Setting permissions..."
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"
chmod 600 "${INSTALL_DIR}/.env"

echo "==> Installing systemd service..."
cp "${SERVICE_FILE}" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "${SERVICE_FILE%.service}"

echo ""
echo "✅  Install complete!"
echo ""
echo "  Next steps:"
echo "  1.  nano ${INSTALL_DIR}/.env          ← add your tokens"
echo "  2.  systemctl start lubelogger-bot"
echo "  3.  journalctl -u lubelogger-bot -f   ← watch logs"
