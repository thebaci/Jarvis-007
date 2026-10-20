#!/usr/bin/env bash
# ============================================================================
# Jarvis 007 - watchdog for a Mac running under launchd.
#
# Why this file exists: the hang of 14/08/2026. The server was ALIVE (still holding port 7777, the kernel
# still accepting TCP) but the event loop was frozen - /health did not answer, SIGTERM was ignored, and it
# took kill -9. launchd's KeepAlive only rescues a DEAD process, not a hung one. This watchdog
# calls /health every minute; after NGUONG consecutive failures it runs `launchctl kickstart -k` - launchd
# takes the old process down itself (SIGKILL if stubborn) and starts a fresh one, with nobody typing at 4am.
#
#   ./watchdog.sh install     install the LaunchAgent com.javis.watchdog (runs check every 60 seconds)
#   ./watchdog.sh uninstall   remove the LaunchAgent
#   ./watchdog.sh check       one check pass (launchd calls it periodically; running it by hand is fine too)
#   ./watchdog.sh status      whether it is installed + failure count + the last few log lines
#
# Configure through env or a .env in the same folder: JAVIS_PORT (7777), JAVIS_LAUNCHD_LABEL
# (com.javis.os), JAVIS_STATE_DIR (./server), JAVIS_WATCHDOG_FAILS (3).
# ============================================================================
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Read .env like update.sh: with several Jarvis 007 instances on one machine, each has its own port/label.
# Env passed in wins over .env (`:=` only assigns when the variable is unset).
if [ -f .env ]; then
  _env() { sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" .env | tail -1; }
  : "${JAVIS_PORT:=$(_env JAVIS_PORT)}"
  : "${JAVIS_LAUNCHD_LABEL:=$(_env JAVIS_LAUNCHD_LABEL)}"
  : "${JAVIS_STATE_DIR:=$(_env JAVIS_STATE_DIR)}"
fi
PORT="${JAVIS_PORT:-7777}"
LABEL="${JAVIS_LAUNCHD_LABEL:-com.javis.os}"
STATE_DIR="${JAVIS_STATE_DIR:-$PWD/server}"
TARGET="gui/$(id -u)/$LABEL"
NGUONG="${JAVIS_WATCHDOG_FAILS:-3}"
DEM_FILE="$STATE_DIR/watchdog-fails"
LOG="$STATE_DIR/watchdog.log"
PLIST="$HOME/Library/LaunchAgents/com.javis.watchdog.plist"
# The kick command is split into a variable so tests can replace it with `echo` - nobody else needs to change it.
KICK_CMD="${JAVIS_WATCHDOG_KICK_CMD:-launchctl kickstart -k $TARGET}"

ghi() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

dang_cap_nhat() {
  # /health being red WHILE the updater runs is legitimate (the updater handles its own rollback) -
  # a watchdog kick cutting in would only wreck the update. But only trust update_state.json while it
  # is fresh (<15 minutes): a phase stuck since long ago must never silence the watchdog forever.
  local us="$STATE_DIR/update_state.json"
  [ -f "$us" ] || return 1
  grep -qE '"phase":[[:space:]]*"(preparing|pulling|installing|restarting|health_check|rolling_back)"' "$us" || return 1
  [ -n "$(find "$us" -mmin -15 2>/dev/null)" ]
}

check() {
  mkdir -p "$STATE_DIR"
  # The log is fed by launchd (StandardOutPath), so trim it ourselves to keep it from growing without limit.
  if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 1000000 ]; then
    tail -c 100000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
  fi
  if dang_cap_nhat; then
    ghi "an update is in progress (update_state.json) - skipping this check"
    echo 0 > "$DEM_FILE"
    return 0
  fi
  if curl -sf -m 10 -o /dev/null "http://127.0.0.1:$PORT/health"; then
    if [ -s "$DEM_FILE" ] && [ "$(cat "$DEM_FILE")" != "0" ]; then
      ghi "/health is green again"
    fi
    echo 0 > "$DEM_FILE"
    return 0
  fi
  local dem
  dem=$(( $(cat "$DEM_FILE" 2>/dev/null || echo 0) + 1 ))
  echo "$dem" > "$DEM_FILE"
  ghi "/health on port $PORT did NOT answer (failure $dem/$NGUONG in a row)"
  if [ "$dem" -ge "$NGUONG" ]; then
    ghi "threshold exceeded → $KICK_CMD"
    echo 0 > "$DEM_FILE"
    if ! $KICK_CMD; then
      ghi "kick FAILED - does job $TARGET exist? Check with: launchctl print $TARGET"
    fi
  fi
}

install() {
  if [ "$(uname)" != "Darwin" ]; then
    echo "install is for Mac only (launchd). On Linux use systemd: WatchdogSec / Restart=always."
    exit 1
  fi
  mkdir -p "$HOME/Library/LaunchAgents" "$STATE_DIR"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.javis.watchdog</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string>
    <string>$PWD/watchdog.sh</string>
    <string>check</string>
  </array>
  <key>StartInterval</key><integer>60</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$STATE_DIR/watchdog.log</string>
  <key>StandardErrorPath</key><string>$STATE_DIR/watchdog.log</string>
</dict></plist>
EOF
  launchctl bootout "gui/$(id -u)/com.javis.watchdog" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
  ghi "installed: checking /health on port $PORT every 60 seconds, $NGUONG consecutive failures → kickstart $TARGET"
  ghi "log at: $LOG"
}

uninstall() {
  launchctl bootout "gui/$(id -u)/com.javis.watchdog" 2>/dev/null || true
  rm -f "$PLIST"
  echo "watchdog removed (com.javis.watchdog)."
}

status() {
  if launchctl print "gui/$(id -u)/com.javis.watchdog" >/dev/null 2>&1; then
    echo "watchdog is RUNNING: checking /health on port $PORT every 60 seconds, threshold $NGUONG failures → kickstart $TARGET"
  else
    echo "watchdog is NOT installed. Install with: ./watchdog.sh install"
  fi
  echo "current consecutive failure count: $(cat "$DEM_FILE" 2>/dev/null || echo 0)"
  if [ -f "$LOG" ]; then
    echo "--- last log lines ---"
    tail -n 5 "$LOG"
  fi
}

case "${1:-status}" in
  install)   install ;;
  uninstall) uninstall ;;
  check)     check ;;
  status)    status ;;
  *) echo "usage: ./watchdog.sh install | uninstall | check | status"; exit 1 ;;
esac
