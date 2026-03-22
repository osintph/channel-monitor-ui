#!/usr/bin/env bash
set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

echo ""
echo -e "${CYAN}${BOLD}════════════════════════════════════════${RESET}"
echo -e "${CYAN}${BOLD}   📡  Channel Monitor  ·  Installer    ${RESET}"
echo -e "${CYAN}${BOLD}════════════════════════════════════════${RESET}"
echo ""

step()  { echo -e "${GREEN}[+]${RESET} ${BOLD}$1${RESET}"; }
info()  { echo -e "${CYAN}[i]${RESET} $1"; }
warn()  { echo -e "${YELLOW}[!]${RESET} $1"; }
fail()  { echo -e "${RED}[✗]${RESET} ${BOLD}$1${RESET}"; exit 1; }

# ── 1. Python check ──────────────────────────────────────────────────────────
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

# ── 2. Virtual environment ───────────────────────────────────────────────────
step "Creating virtual environment..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  info "Created .venv/"
else
  info "Already exists — skipping"
fi

# ── 3. Dependencies ──────────────────────────────────────────────────────────
step "Installing dependencies..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
info "All packages installed ✓"

# ── 4. Environment config ────────────────────────────────────────────────────
step "Configuring environment..."
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo -e "  ${YELLOW}${BOLD}⚠ Action required:${RESET} Fill in your Telegram credentials in .env before continuing."
  echo ""
  echo -e "  ${BOLD}Required fields:${RESET}"
  echo -e "  ${CYAN}  TELEGRAM_API_ID${RESET}   → from https://my.telegram.org"
  echo -e "  ${CYAN}  TELEGRAM_API_HASH${RESET}  → from https://my.telegram.org"
  echo -e "  ${CYAN}  TELEGRAM_PHONE${RESET}     → e.g. +15551234567"
  echo ""

  if command -v nano &>/dev/null; then
    read -rp "  Open .env in nano now? [Y/n] " EDIT
    EDIT="${EDIT:-Y}"
    if [[ "$EDIT" =~ ^[Yy]$ ]]; then
      nano .env
    else
      echo ""
      warn "Edit .env manually then re-run: bash install.sh"
      exit 0
    fi
  else
    warn "Edit .env manually then re-run: bash install.sh"
    exit 0
  fi
else
  info ".env already exists — keeping it"
fi

# ── 5. Validate credentials are filled in ───────────────────────────────────
step "Validating credentials..."

API_ID=$(grep -E "^TELEGRAM_API_ID=" .env | cut -d= -f2 | tr -d '[:space:]')
API_HASH=$(grep -E "^TELEGRAM_API_HASH=" .env | cut -d= -f2 | tr -d '[:space:]')
PHONE=$(grep -E "^TELEGRAM_PHONE=" .env | cut -d= -f2 | tr -d '[:space:]')

if [ -z "$API_ID" ] || [ "$API_ID" = "your_api_id_here" ]; then
  fail "TELEGRAM_API_ID is not set in .env. Edit it and re-run: bash install.sh"
fi
if [ -z "$API_HASH" ] || [ "$API_HASH" = "your_api_hash_here" ]; then
  fail "TELEGRAM_API_HASH is not set in .env. Edit it and re-run: bash install.sh"
fi
if [ -z "$PHONE" ] || [ "$PHONE" = "+your_phone_number" ]; then
  fail "TELEGRAM_PHONE is not set in .env. Edit it and re-run: bash install.sh"
fi

info "Credentials look good ✓"

# ── 6. Telegram authentication ───────────────────────────────────────────────
mkdir -p data

if [ -f "data/channel_monitor.session" ]; then
  info "Telegram session already exists — skipping auth ✓"
else
  step "Authenticating with Telegram..."
  info "Telegram will send a login code to your phone or app."
  info "Enter it when prompted below."
  echo ""

  .venv/bin/python3 - << 'PYEOF'
import os, asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))

api_id   = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
phone    = os.getenv("TELEGRAM_PHONE")

async def auth():
    client = TelegramClient("data/channel_monitor", int(api_id), api_hash)
    await client.start(phone=phone)
    me = await client.get_me()
    print(f"\n[✓] Logged in as @{me.username or me.first_name}")
    await client.disconnect()

asyncio.run(auth())
PYEOF
fi

# ── 7. Done ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✓ Installation complete!${RESET}"
echo ""
echo -e "  Run manually:       ${CYAN}${BOLD}bash run.sh${RESET}"
echo -e "  Install as service: ${CYAN}${BOLD}sudo bash install-service.sh${RESET}"
echo -e "  Then open:          ${CYAN}${BOLD}http://localhost:5000${RESET}"
echo ""
