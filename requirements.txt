#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────────
#  Channel Monitor — One-Click Install & Run
#  Usage:  bash install.sh
# ────────────────────────────────────────────────────────────────────────────
set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

print_header() {
  echo ""
  echo -e "${CYAN}${BOLD}════════════════════════════════════════${RESET}"
  echo -e "${CYAN}${BOLD}   📡  Channel Monitor  ·  Installer    ${RESET}"
  echo -e "${CYAN}${BOLD}════════════════════════════════════════${RESET}"
  echo ""
}

step() { echo -e "${GREEN}[+]${RESET} ${BOLD}$1${RESET}"; }
info() { echo -e "${CYAN}[i]${RESET} $1"; }
warn() { echo -e "${YELLOW}[!]${RESET} $1"; }
fail() { echo -e "${RED}[✗]${RESET} ${BOLD}$1${RESET}"; exit 1; }

print_header

# ── 1. Check Python ──────────────────────────────────────────────────────────
step "Checking Python version..."
if ! command -v python3 &>/dev/null; then
  fail "Python 3 is not installed. Please install Python 3.10+ and re-run."
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
  fail "Python 3.10+ required. Found: $PY_VERSION"
fi

info "Found Python $PY_VERSION ✓"

# ── 2. Create virtualenv ─────────────────────────────────────────────────────
step "Creating virtual environment..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  info "Virtual environment created in .venv/"
else
  info "Virtual environment already exists — skipping"
fi

# ── 3. Install dependencies ──────────────────────────────────────────────────
step "Installing dependencies..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
info "All packages installed ✓"

# ── 4. Set up .env ───────────────────────────────────────────────────────────
step "Configuring environment..."
if [ ! -f ".env" ]; then
  cp .env.example .env
  warn ".env file created from template."
  echo ""
  echo -e "  ${BOLD}You must edit .env with your Telegram credentials before running:${RESET}"
  echo -e "  ${CYAN}  TELEGRAM_API_ID   ${RESET}→ from https://my.telegram.org"
  echo -e "  ${CYAN}  TELEGRAM_API_HASH ${RESET}→ from https://my.telegram.org"
  echo -e "  ${CYAN}  TELEGRAM_PHONE    ${RESET}→ your phone number (e.g. +15551234567)"
  echo ""

  # Try to open editor
  if command -v nano &>/dev/null; then
    read -rp "  Open .env in nano now? [Y/n] " EDIT
    EDIT="${EDIT:-Y}"
    if [[ "$EDIT" =~ ^[Yy]$ ]]; then
      nano .env
    fi
  else
    info "Edit .env manually, then run:  bash run.sh"
  fi
else
  info ".env already exists — keeping existing configuration"
fi

# ── 5. Done ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✓ Installation complete!${RESET}"
echo ""
echo -e "  To start the app:   ${CYAN}${BOLD}bash run.sh${RESET}"
echo -e "  Then open:          ${CYAN}${BOLD}http://localhost:5000${RESET}"
echo ""
