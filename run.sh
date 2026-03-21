#!/usr/bin/env bash
CYAN="\033[0;36m"
GREEN="\033[0;32m"
RED="\033[0;31m"
BOLD="\033[1m"
RESET="\033[0m"

if [ ! -d ".venv" ]; then
  echo -e "${RED}[✗]${RESET} Run bash install.sh first."
  exit 1
fi
if [ ! -f ".env" ]; then
  echo -e "${RED}[✗]${RESET} .env not found. Run bash install.sh first."
  exit 1
fi

PORT="${PORT:-5000}"
echo ""
echo -e "${CYAN}${BOLD}📡 Channel Monitor${RESET}"
echo -e "${GREEN}[+]${RESET} Starting on ${CYAN}${BOLD}http://localhost:${PORT}${RESET}"
echo -e "${GREEN}[+]${RESET} Press Ctrl+C to stop."
echo ""
.venv/bin/python app.py
