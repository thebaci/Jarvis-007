#!/usr/bin/env bash
# ============================================================================
# Jarvis 007 - update to the latest version from GitHub.
#   ./update.sh            (auto-detects Docker or native)
#   ./update.sh docker     (force Docker mode)
#   ./update.sh native     (force native/systemd mode)
# ============================================================================
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
MODE="${1:-auto}"
SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

# Name of the Jarvis 007 instance IN THIS FOLDER. With several instances on one VPS, each has its own .env; if
# we do not read the .env here, this instance's `./update.sh` restarts another instance's container/service.
if [ -z "${JAVIS_NAME:-}" ] && [ -f .env ]; then
  JAVIS_NAME="$(sed -n 's/^[[:space:]]*JAVIS_NAME[[:space:]]*=[[:space:]]*//p' .env | tail -1)"
fi
NAME="${JAVIS_NAME:-javis}"

echo "==> Pulling the latest code from GitHub..."
git pull --ff-only

is_docker() {
  command -v docker >/dev/null 2>&1 && [ -f docker-compose.yml ] && \
  docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$NAME"
}

if [ "$MODE" = "docker" ] || { [ "$MODE" = "auto" ] && is_docker; }; then
  echo "==> Docker → pulling the new image from GHCR and restarting..."
  # HTTPS (Caddy) enabled? Keep the override so the update does NOT remove Caddy.
  HTTPS_ARGS=""
  if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$NAME-caddy"; then
    HTTPS_ARGS="-f docker-compose.yml -f docker-compose.https.yml"
    echo "==> Caddy (HTTPS) detected → keeping the HTTPS setup."
  fi
  # Behind a shared proxy (several instances, one domain each)? Keep the multi override too,
  # otherwise this update drops the Caddy label and that instance falls off the proxy.
  if [ -f docker-compose.multi.yml ] && docker network inspect javis-web >/dev/null 2>&1; then
    HTTPS_ARGS="-f docker-compose.yml -f docker-compose.multi.yml"
    echo "==> Shared proxy (javis-web) detected → keeping the multi-instance setup."
  fi
  docker compose $HTTPS_ARGS pull
  docker compose $HTTPS_ARGS up -d
  echo "==> Done. Follow the logs:  docker compose logs -f"
else
  echo "==> Native → updating Python libraries and restarting the service..."
  [ -d .venv ] && ./.venv/bin/pip install -r requirements.txt -q || true
  # Updating Python alone leaves the ChatGPT model catalog on an old Codex CLI.
  if command -v npm >/dev/null 2>&1; then
    if ! npm install -g @openai/codex@latest && ! $SUDO npm install -g @openai/codex@latest; then
      echo "[!] Could not update Codex; the ChatGPT model list may be out of date."
    fi
  else
    echo "[!] npm not found; update Codex by hand to get the newest ChatGPT models."
  fi
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q "^$NAME\.service"; then
    $SUDO systemctl restart "$NAME"
    echo "==> Restarted. Follow the logs:  journalctl -u $NAME -f"
  elif [ "$(uname)" = "Darwin" ] && \
       launchctl print "gui/$(id -u)/${JAVIS_LAUNCHD_LABEL:-com.javis.os}" >/dev/null 2>&1; then
    # Mac running under launchd (KeepAlive): killing the PID and starting nohup ourselves races the
    # launchd respawn for the port ([Errno 48], incident of 14/08/2026). Let launchd swap shifts with kickstart -k.
    TARGET="gui/$(id -u)/${JAVIS_LAUNCHD_LABEL:-com.javis.os}"
    echo "==> launchd ($TARGET) detected → kickstart -k..."
    launchctl kickstart -k "$TARGET"
    echo "==> Asked launchd to restart Jarvis 007. Logs: server/javis.log"
  else
    # Mac / Linux without systemd: kill the process holding the port, then restart in the background (like install.sh)
    PORT="${JAVIS_PORT:-7777}"
    PIDS="$(lsof -ti tcp:"$PORT" 2>/dev/null || true)"
    if [ -n "$PIDS" ]; then
      echo "==> Stopping the old process (PID: $PIDS)..."
      kill $PIDS 2>/dev/null || true
      sleep 2
    fi
    ( cd server && JAVIS_STATE_DIR="$PWD" nohup ../.venv/bin/python -m uvicorn main:app \
        --host "${JAVIS_HOST:-127.0.0.1}" --port "$PORT" > javis.log 2>&1 & )
    echo "==> Restarted (nohup). Logs: server/javis.log"
  fi
fi
