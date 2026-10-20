#!/usr/bin/env bash
# ============================================================================
# Jarvis 007 - Linux/macOS native installer (no Docker)
#   ./install.sh
# Installs python3 + node + Claude Code CLI, creates a venv, installs deps,
# seeds .env, and registers a systemd service (or falls back to nohup).
#
# NHIEU BAN TREN CUNG MOT MAY: clone vao THU MUC KHAC roi dat hai bien truoc khi chay.
#   JAVIS_NAME=javis-shop JAVIS_PORT=7778 ./install.sh
# JAVIS_NAME dat ten dich vu systemd (javis-shop.service); JAVIS_PORT la cong nghe.
# Bo trong ca hai = javis.service + cong 7777, y het truoc day.
# ============================================================================
set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${CYAN}->${NC} $*"; }
ok()   { echo -e "${GREEN}OK${NC} $*"; }
warn() { echo -e "${YELLOW}!!${NC} $*"; }
err()  { echo -e "${RED}xx${NC} $*" >&2; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

# Ten dich vu + cong cua BAN NAY. Truoc day ca hai deu dong cung, nen cai ban thu hai la ghi de
# /etc/systemd/system/javis.service cua ban thu nhat va hai ban tranh nhau cong 7777.
SVC="${JAVIS_NAME:-javis}"
PORT="${JAVIS_PORT:-7777}"
case "$SVC" in
  *[!A-Za-z0-9._-]*) err "JAVIS_NAME may only contain letters, digits, '.', '_' and '-' (got: $SVC)"; exit 1;;
esac

SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

# --- 1. python3 >= 3.10 + venv + pip ---
# HARD FLOOR 3.10: uvicorn pinned in requirements.txt needs >=3.10 (every release from
# 0.40 up dropped 3.9). Do NOT trust a bare `python3` here - macOS ships /usr/bin/python3
# = 3.9 and it sits AHEAD of Homebrew in PATH, so the old code happily printed
# "OK Python 3.9.6" and then died 40 lines later with the useless pip error
# "No matching distribution found for uvicorn==0.51.0". Probe for a real interpreter.
PY_MIN="3.10"
py_ok() { "$1" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)' >/dev/null 2>&1; }

PYTHON_BIN=""
find_python() {
  local c d
  # NOT newest-first. requirements.txt pins hard (fastapi 0.141.1, cryptography, uvloop,
  # watchfiles, pydantic-core - all need compiled wheels), so prefer the versions with the
  # widest wheel coverage and fall back to a bleeding-edge interpreter only if nothing else
  # exists: on a brand-new 3.x, pip finds no wheel and tries to BUILD from source, which
  # fails on any machine without a compiler toolchain. 3.11/3.12 is the verified sweet spot.
  for c in python3.12 python3.11 python3.13 python3.10 python3 python3.14 python; do
    if py_ok "$c"; then PYTHON_BIN="$(command -v "$c")"; return 0; fi
  done
  # Homebrew python is keg-only on some setups (never linked into PATH); look directly.
  # Same preference order, explicit rather than a glob (a glob sorts 3.10 ahead of 3.12).
  for d in /opt/homebrew/bin /usr/local/bin; do
    for c in python3.12 python3.11 python3.13 python3.10 python3.14; do
      if py_ok "$d/$c"; then PYTHON_BIN="$d/$c"; return 0; fi
    done
  done
  return 1
}

log "Checking Python >= $PY_MIN..."
if ! find_python; then
  log "No Python >= $PY_MIN found - installing..."
  if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update -qq && $SUDO apt-get install -y python3 python3-venv python3-pip
  elif command -v dnf >/dev/null 2>&1; then $SUDO dnf install -y python3 python3-pip
  elif command -v brew >/dev/null 2>&1; then brew install python
  else err "Install Python $PY_MIN or newer manually, then re-run."; exit 1; fi
  find_python || {
    err "Still no Python >= $PY_MIN after install (found: $(python3 --version 2>&1 || echo none))."
    err "Install it manually (macOS: brew install python), then re-run."
    exit 1
  }
fi
"$PYTHON_BIN" -m venv --help >/dev/null 2>&1 || { command -v apt-get >/dev/null 2>&1 && $SUDO apt-get install -y python3-venv; }
ok "$("$PYTHON_BIN" --version) ($PYTHON_BIN)"

# --- 2. system deps: git, ripgrep, ffmpeg (best-effort) ---
log "Installing system deps (git, ripgrep, ffmpeg)..."
if command -v apt-get >/dev/null 2>&1; then
  $SUDO apt-get install -y git ripgrep ffmpeg curl >/dev/null 2>&1 || warn "some deps skipped"
elif command -v dnf >/dev/null 2>&1; then
  $SUDO dnf install -y git ripgrep ffmpeg curl >/dev/null 2>&1 || warn "some deps skipped"
elif command -v brew >/dev/null 2>&1; then
  brew install git ripgrep ffmpeg >/dev/null 2>&1 || warn "some deps skipped"
fi

# --- 3. Node.js 22 LTS (system pkg -> nodejs.org tarball fallback) ---
need_node() { ! command -v node >/dev/null 2>&1 || [ "$(node -v | sed 's/v//;s/\..*//')" -lt 20 ]; }
if need_node; then
  log "Installing Node.js 22 LTS..."
  if command -v apt-get >/dev/null 2>&1; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | $SUDO -E bash - >/dev/null 2>&1 && $SUDO apt-get install -y nodejs || true
  elif command -v brew >/dev/null 2>&1; then brew install node@22 || true; fi
  if need_node; then
    arch=$(uname -m); case "$arch" in x86_64) na=x64;; aarch64|arm64) na=arm64;; *) err "unsupported arch $arch"; exit 1;; esac
    tb=$(curl -fsSL https://nodejs.org/dist/latest-v22.x/ | grep -oE "node-v22\.[0-9]+\.[0-9]+-linux-${na}\.tar\.xz" | head -1)
    tmp=$(mktemp -d); curl -fsSL "https://nodejs.org/dist/latest-v22.x/${tb}" -o "$tmp/n.tar.xz"
    mkdir -p "$HOME/.javis"; rm -rf "$HOME/.javis/node"
    tar xf "$tmp/n.tar.xz" -C "$tmp"; mv "$tmp"/node-v22* "$HOME/.javis/node"; rm -rf "$tmp"
    mkdir -p "$HOME/.local/bin"
    ln -sf "$HOME/.javis/node/bin/node" "$HOME/.local/bin/node"
    ln -sf "$HOME/.javis/node/bin/npm"  "$HOME/.local/bin/npm"
    ln -sf "$HOME/.javis/node/bin/npx"  "$HOME/.local/bin/npx"
    export PATH="$HOME/.local/bin:$PATH"
  fi
fi
ok "Node $(node -v)"

# --- 4. Claude Code CLI (the brain) ---
if ! command -v claude >/dev/null 2>&1; then
  log "Installing Claude Code CLI globally via npm..."
  if ! npm install -g @anthropic-ai/claude-code >/dev/null 2>&1; then
    warn "global npm install needs sudo; retrying..."
    $SUDO npm install -g @anthropic-ai/claude-code
  fi
fi
ok "Claude CLI $(claude --version 2>/dev/null || echo installed)"

# --- 4b. Codex CLI (ChatGPT plan) ---
#
# BEST-EFFORT, deliberately different from Claude above: without Claude, Jarvis 007 has no default brain left
# to run, while a missing Codex only loses exactly one engine. So a failure here only warns and does not let
# `set -e` kill the whole install.
#
# The Google brain for a personal account is now Antigravity CLI (`agy`), NOT installed here:
# Google's installer is a download-and-run script, left for the machine owner to decide. The Models page has
# the install command ready on its card.
cai_them_cli() {   # <npm package> <binary name> <display name>
  # Codex supplies the live model catalog; an installed old CLI must be upgraded.
  if [ "$2" != "codex" ] && command -v "$2" >/dev/null 2>&1; then return 0; fi
  log "Installing $3 globally via npm (best-effort)..."
  if npm install -g "$1" >/dev/null 2>&1 || $SUDO npm install -g "$1" >/dev/null 2>&1; then
    ok "$3 $("$2" --version 2>/dev/null || echo installed)"
  else
    warn "Could not install $3 - that engine will not show on the Models page. Install it by hand: npm i -g $1"
  fi
}
# The Gemini CLI engine was REMOVED entirely in 0.50.0 (Google cut off every personal account from 2026-06-18).
cai_them_cli @openai/codex@latest codex "Codex CLI"

# --- 4c. agy (Antigravity CLI, the Google route) + grok (Grok Build, the xAI route) ---
#
# These two engines are NOT installed with npm: each vendor ships a download-and-run script. Before 0.59.13, after
# installing Jarvis 007 the user still had to open a terminal and type two lines from two different vendors, and the owner
# of the project reported that exact spot as where non-technical people got stuck on the Models screen with two "CLI not
# installed" cards (16/09). Now both are installed in one go.
#
# Absolutely BEST-EFFORT: this runs a third party's script, so failure is normal (network, unusual machine,
# vendor changed the URL) - on failure say one line and move on, never kill the install.
# SIGN-IN is still the user's job, done on the Models page after Jarvis 007 is running.
cai_cli_script() {   # <binary name> <display name> <install script URL>
  if command -v "$1" >/dev/null 2>&1; then ok "$2 already installed"; return 0; fi
  log "Installing $2 (best-effort, the vendor script)..."
  if curl -fsSL "$3" | bash >/dev/null 2>&1; then
    export PATH="$HOME/.local/bin:$PATH"
    if command -v "$1" >/dev/null 2>&1; then ok "$2"; else
      warn "$2: the installer finished but binary '$1' is not on PATH yet. Open a new terminal and retry: curl -fsSL $3 | bash"
    fi
  else
    warn "Could not install $2 - that engine will not show on the Models page. Install it by hand: curl -fsSL $3 | bash"
  fi
}
cai_cli_script agy "Antigravity CLI (Google)" https://antigravity.google/cli/install.sh
cai_cli_script grok "Grok Build (xAI)" https://x.ai/cli/install.sh

# --- 5. venv + python deps ---
log "Creating virtualenv (.venv)..."
# A .venv left over from a failed run can be built on 3.9 - reusing it reproduces the
# exact uvicorn resolve error the probe above exists to prevent. Rebuild instead.
if [ -d .venv ] && ! py_ok ./.venv/bin/python; then
  warn ".venv runs $(./.venv/bin/python --version 2>&1 || echo 'an unusable Python') - rebuilding with $PYTHON_BIN"
  rm -rf .venv
fi
[ -d .venv ] || "$PYTHON_BIN" -m venv .venv
./.venv/bin/pip install --upgrade pip -q
./.venv/bin/pip install -r requirements.txt -q
ok "Python deps installed"

# --- 6. .env (chmod 600 - holds tokens) ---
if [ ! -f .env ]; then cp env.example .env; chmod 600 .env; ok "Created .env from template"; else chmod 600 .env 2>/dev/null || true; ok ".env exists"; fi

# --- 7. minimal config prompt ---
if [ -t 0 ]; then
  read -rp "Vault path [blank = in-repo vault/]: " VP || true
  if [ -n "${VP:-}" ]; then
    if grep -q '^OBSIDIAN_VAULT_PATH=' .env; then sed -i.bak "s|^OBSIDIAN_VAULT_PATH=.*|OBSIDIAN_VAULT_PATH=$VP|" .env && rm -f .env.bak; else echo "OBSIDIAN_VAULT_PATH=$VP" >> .env; fi
  fi
fi
grep -q '^JAVIS_HOST=' .env || echo "JAVIS_HOST=127.0.0.1" >> .env

# --- 7b. Admin account: PRESET right at install time ---
#
# Before, this step did not exist, so anyone who opened Jarvis 007 publicly ran into the "SETUP CODE":
# the server printed a random string to the log at startup, and the user had to SSH into the VPS, read the log
# and paste it into the browser before they could create an account. That code exists for a reason - it stops a
# stranger who only has the URL from taking over admin on first run - but making people go read logs is a bad
# experience, and bad at EXACTLY the moment they have just finished installing and know nothing yet.
#
# Presetting the account here solves both ends: the person running this script is ALREADY sitting at the
# server, so asking them one question adds no step; and the server boots with an admin already in place, so
# `setup_token_required()` returns false and the SETUP CODE never shows up.
#
# Do NOT drop the code mechanism entirely: it is still the safety net for anyone deploying another way (manual compose, bare image).
# Removing it would leave `/auth/setup` wide open to anyone who hits the URL before the machine owner - and what they would take
# over is a machine with Bash, running with full rights, plugged into the owner's POS/ads/email.
_gen_pw() { python3 -c "import secrets,string; a=string.ascii_letters+string.digits; print(''.join(secrets.choice(a) for _ in range(20)))"; }

# Write .env with python, not sed: a password the user types can contain | & \ " '
# and every one of those characters breaks a sed command written the usual way. The value goes through argv so
# it never passes through the shell; it is written in escaped double quotes so python-dotenv reads it back correctly.
_env_set() {
  python3 - "$1" "$2" <<'PY'
import pathlib, sys
key, val = sys.argv[1], sys.argv[2]
esc = val.replace("\\", "\\\\").replace('"', '\\"')
p = pathlib.Path(".env")
lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
out, done = [], False
for ln in lines:
    if ln.split("=", 1)[0].strip() == key and not ln.lstrip().startswith("#"):
        if not done:
            out.append(f'{key}="{esc}"')
            done = True
    else:
        out.append(ln)
if not done:
    out.append(f'{key}="{esc}"')
p.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
}

_env_has() { grep -qE "^[[:space:]]*$1=[\"']?[^\"'[:space:]]" .env 2>/dev/null; }

ADMIN_PW_SINH=""      # only set when the script GENERATED it - so it is printed exactly once at the end
if _env_has JAVIS_ADMIN_PASSWORD; then
  ok "Admin account already set in .env - keeping it"
else
  ADMIN_USER="admin"
  ADMIN_PW=""
  if [ -t 0 ]; then
    echo ""
    log "Jarvis 007 admin account (required: the AI brain runs with full rights on this machine):"
    read -rp "  Username [admin]: " AU || true
    [ -n "${AU:-}" ] && ADMIN_USER="$AU"
    while :; do
      read -rsp "  Password (Enter = generate a strong one): " AP || true; echo ""
      if [ -z "${AP:-}" ]; then ADMIN_PW="$(_gen_pw)"; ADMIN_PW_SINH="$ADMIN_PW"; break; fi
      # The server also rejects under 8 characters (main.py /auth/setup). Reject it here too so people know
      # at typing time, instead of discovering at first login that .env holds a password that cannot be used.
      if [ "${#AP}" -lt 8 ]; then warn "  At least 8 characters."; continue; fi
      read -rsp "  Repeat it: " AP2 || true; echo ""
      if [ "$AP" = "${AP2:-}" ]; then ADMIN_PW="$AP"; break; fi
      warn "  The two entries do not match, try again."
    done
  else
    # Running without a keyboard (curl | bash, CI, another script calling in). Generate one, do NOT leave it empty:
    # leaving it empty sends the user back to the exact read-the-log screen this step exists to remove.
    ADMIN_PW="$(_gen_pw)"; ADMIN_PW_SINH="$ADMIN_PW"
  fi
  _env_set JAVIS_ADMIN_USER "$ADMIN_USER"
  _env_set JAVIS_ADMIN_PASSWORD "$ADMIN_PW"
  chmod 600 .env
  ok "Admin account saved in .env"
fi

# --- 7c. Two-factor authentication: ASK here, TURN ON in the browser ---
#
# Deliberately not done fully in the terminal. Turning on 2FA needs scanning a QR code, and drawing a QR in a terminal
# renders wrong on half of machines (font, cell ratio, light/dark background) and the user would have to hold their phone up to the
# SSH window. Meanwhile in a few seconds they will open the browser to sign in - the right place to show a QR.
#
# So this step only writes the INTENT into .env. The server reads that flag and opens the 2FA setup screen ready on the
# Account page. The flag is NOT a security barrier and turns nothing on by itself: 2FA is only really on after the
# user scans the QR and enters one correct code, because turning it on before they prove the app generates the right code is
# locking them out of the very machine they just installed.
if ! _env_has JAVIS_SETUP_2FA && [ -t 0 ]; then
  read -rp "  Turn on two-factor sign-in (Google Authenticator)? [y/N]: " TFA || true
  case "${TFA:-}" in
    [yY]*)
      _env_set JAVIS_SETUP_2FA 1
      ok "Noted - the first time you open the dashboard, the Account page will show the QR code to scan"
      ;;
    *) log "Skipped - you can turn it on any time under Dashboard → Account" ;;
  esac
fi

# --- 8. one-time Claude auth reminder ---
if ! claude auth status >/dev/null 2>&1; then
  warn "Claude CLI is not logged in. Run this ONCE (opens a browser-login URL):"
  echo "      claude auth login --claudeai"
fi

# --- 9. service: systemd if available, else nohup ---
PY="$APP_DIR/.venv/bin/python"
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  log "Installing systemd service ($SVC.service, port $PORT)..."
  $SUDO tee "/etc/systemd/system/$SVC.service" >/dev/null <<UNIT
[Unit]
Description=Jarvis 007 ($SVC)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$APP_DIR/server
Environment="JAVIS_HOST=127.0.0.1"
Environment="JAVIS_PORT=$PORT"
Environment="JAVIS_STATE_DIR=$APP_DIR/server"
Environment="PATH=$APP_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PY -m uvicorn main:app --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=5
KillSignal=SIGTERM
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable --now "$SVC.service"
  ok "Service installed. Logs: journalctl -u $SVC -f"
else
  warn "systemd not available - starting under nohup..."
  ( cd "$APP_DIR/server" && JAVIS_STATE_DIR="$APP_DIR/server" JAVIS_PORT="$PORT" nohup "$PY" -m uvicorn main:app --host 127.0.0.1 --port "$PORT" > "$APP_DIR/server/javis.log" 2>&1 & )
  ok "Started. Logs: $APP_DIR/server/javis.log"
fi

echo ""
ok "Jarvis 007 is up at: http://127.0.0.1:$PORT"
log "Remote access (SSH tunnel): ssh -L $PORT:localhost:$PORT $(whoami)@<vps-ip>"

# The generated password is printed ONLY here, exactly once. It is not written to the service log and not printed
# again on later runs - `.env` (chmod 600) is where it is kept. It is printed after the startup output so it sits at the
# bottom of the screen, where people are sure to still be looking.
if [ -n "${ADMIN_PW_SINH:-}" ]; then
  echo ""
  echo "=================================================================="
  echo "  ADMIN ACCOUNT (saved in .env, shown only ONCE):"
  echo "      Username:  ${ADMIN_USER:-admin}"
  echo "      Password:  $ADMIN_PW_SINH"
  echo "  Copy it somewhere safe now. You can change it later under Dashboard → Account."
  echo "=================================================================="
fi
echo ""
log "Remote access through a Cloudflare Tunnel (no open port, HTTPS included):"
echo "    1) Sign in with the admin account above (the AI brain runs with full rights!)."
if command -v cloudflared >/dev/null 2>&1; then
  echo "    2) cloudflared tunnel --url http://localhost:$PORT   → open https://<random>.trycloudflare.com"
else
  echo "    2) Install cloudflared:  curl -fsSL https://pkg.cloudflare.com/cloudflared.deb -o /tmp/cf.deb && $SUDO dpkg -i /tmp/cf.deb"
  echo "       Then:  cloudflared tunnel --url http://localhost:$PORT"
fi
