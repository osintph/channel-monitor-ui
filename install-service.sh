#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────────
#  Channel Monitor — Install as systemd service
#  Usage:  sudo bash install-service.sh
# ────────────────────────────────────────────────────────────────────────────
set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
RED="\033[0;31m"
RESET="\033[0m"

step() { echo -e "${GREEN}[+]${RESET} ${BOLD}$1${RESET}"; }
info() { echo -e "${CYAN}[i]${RESET} $1"; }
fail() { echo -e "${RED}[✗]${RESET} ${BOLD}$1${RESET}"; exit 1; }

# Must be run as root
if [ "$EUID" -ne 0 ]; then
  fail "Run this with sudo: sudo bash install-service.sh"
fi

# Detect the real user (the one who called sudo)
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(eval echo "~$REAL_USER")
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$APP_DIR/.venv"
PORT="${PORT:-5000}"
SERVICE_NAME="channel-monitor"

step "Installing systemd service..."
info "App dir:  $APP_DIR"
info "User:     $REAL_USER"
info "Port:     $PORT"

# Make sure gunicorn is installed
if [ ! -f "$VENV/bin/gunicorn" ]; then
  info "Installing gunicorn..."
  sudo -u "$REAL_USER" "$VENV/bin/pip" install gunicorn -q
fi

# Write the service file
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Channel Monitor — Telegram channel scraper
After=network.target

[Service]
Type=simple
User=${REAL_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${VENV}/bin/gunicorn app:app --bind 0.0.0.0:${PORT} --workers 2 --timeout 300 --access-logfile - --error-logfile -
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

echo ""
echo -e "${GREEN}${BOLD}✓ Service installed and started!${RESET}"
echo ""
echo -e "  Status:   ${CYAN}sudo systemctl status ${SERVICE_NAME}${RESET}"
echo -e "  Logs:     ${CYAN}sudo journalctl -u ${SERVICE_NAME} -f${RESET}"
echo -e "  Stop:     ${CYAN}sudo systemctl stop ${SERVICE_NAME}${RESET}"
echo -e "  Restart:  ${CYAN}sudo systemctl restart ${SERVICE_NAME}${RESET}"
echo ""
HOSTNAME_VAL=$(hostname)
echo -e "  Access via:"
echo -e "    ${CYAN}http://localhost:${PORT}${RESET}"
echo -e "    ${CYAN}http://${HOSTNAME_VAL}:${PORT}${RESET}"
echo -e "    ${CYAN}http://$(hostname -I | awk '{print $1}'):${PORT}${RESET}"
echo ""
