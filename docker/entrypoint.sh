#!/bin/sh
# Container entrypoint: MOVES the HOME directories that external CLIs write into over to the /data
# volume, then runs the main command (uvicorn).
#
# Why it exists (report of 16/08): the Antigravity CLI (`agy`) is installed by the user into
# ~/.local/bin and keeps its login in ~/.antigravity / ~/.config / ~/.gemini - all of which live in
# the container's HOME, and HOME is NOT on any volume (only /data, /brains, ~/.claude and
# ~/.codex are persisted). Every image update is a new container with a brand new HOME: the
# binary and the login both vanish, and the user has to install and sign in from scratch, forever.
#
# The fix: on every boot, link ~/.local, ~/.antigravity, ~/.config, ~/.gemini, ~/.grok into /data/home/
# (the /data volume already exists, so the user does NOT need to edit docker-compose - only the new
# image is needed). The first time after this version, whatever is currently in HOME is moved to
# the volume before linking, so anyone who already installed agy in the current container loses nothing.
#
# Safe: every step tolerates errors (|| true / continue) - if /data has broken permissions the
# linking is skipped and the server STILL starts; only the survive-an-update feature is lost, the app does not die.
set -u

PERSIST_ROOT="${JAVIS_HOME_PERSIST:-/data/home}"

# ~/.gemini: `agy` keeps its MCP config (~/.gemini/config/mcp_config.json - where Jarvis 007 plugs
# the hub in) and the MCP OAuth tokens there. Without it, every update loses all the MCP
# connections the user added by hand, even though the Google login survives.
#
# ~/.grok: the xAI login of Grok Build (`~/.grok/auth.json`) plus personal config. It was missed
# from 0.50.0 to 0.50.3, and it broke the same way `agy` did on 16/08 - just one step harder to
# spot: the `grok` binary sits in ~/.local/bin so it WAS kept, the Models card still said "CLI installed",
# and only the login session vanished. A user reported on 29/08: "every time I upgrade to a new version grok
# gets logged out again". Adding one word to this list is the whole fix, no docker-compose edit needed.
#
# ~/.google_workspace_mcp: the Google Workspace login session of the MCP of the same name. Without it, every
# container rebuild forces a new Google sign-in (report of 13/10/2026).
for d in .local .antigravity .config .gemini .grok .google_workspace_mcp; do
    src="$HOME/$d"
    dst="$PERSIST_ROOT/$d"
    # Already a symlink (second boot onward) -> done long ago.
    [ -L "$src" ] && continue
    mkdir -p "$dst" 2>/dev/null || continue
    # The current container already has content (agy installed before this version) -> move it to the volume,
    # do NOT overwrite files already on the volume (the volume copy is the one that survives updates).
    if [ -d "$src" ]; then
        cp -an "$src/." "$dst/" 2>/dev/null || true
        rm -rf "$src" 2>/dev/null || continue
    fi
    ln -sfn "$dst" "$src" 2>/dev/null || true
done

# ~/.claude.json: Claude Code's global config (user-level MCP, onboarding state, choices already
# made). It is a FILE sitting next to the ~/.claude volume, not inside it, so before this version
# it vanished on every container rebuild (report of 13/10/2026). Link the file into /data/home.
# Claude Code writes through the symlink; if it ever replaces the link with a real file, the next
# boot moves that file to the volume and links again, so at most the changes made between two boots are lost.
f="$HOME/.claude.json"
pf="$PERSIST_ROOT/.claude.json"
if [ ! -L "$f" ] && mkdir -p "$PERSIST_ROOT" 2>/dev/null; then
    if [ -f "$f" ]; then
        # The volume copy is the one that survives updates, so it WINS; only when the file in HOME is newer
        # (Claude Code just wrote over the link inside this very container) is it copied over to the volume.
        if [ ! -f "$pf" ] || [ "$f" -nt "$pf" ]; then
            cp -p "$f" "$pf" 2>/dev/null || true
        fi
        [ -f "$pf" ] && rm -f "$f" 2>/dev/null
    fi
    # Brand new machine: pre-create a valid empty config on the volume so it can be linked from the first boot.
    [ -e "$f" ] || [ -f "$pf" ] || printf '{}\n' > "$pf" 2>/dev/null || true
    if [ ! -e "$f" ] && [ -f "$pf" ]; then
        ln -sfn "$pf" "$f" 2>/dev/null || cp -p "$pf" "$f" 2>/dev/null || true
    fi
fi

# Auto-install the Antigravity CLI (`agy`) and Grok Build (`grok`) if the machine does not have them (0.85.1).
#
# Why they are not baked into the image like claude/codex: these two CLIs are not released through npm but through
# the download scripts of Google and xAI themselves, and embedding their binaries in a public GHCR image is
# redistributing someone else's software. So the image leaves them out and the container downloads them at runtime,
# exactly as `install.sh` and `install.ps1` have done for installs on a machine since 0.59.13.
#
# Before this version, Docker users saw a "CLI not installed" card on the Models page with a command they had to type,
# and customers who installed through Hostinger had almost nowhere to type it. Now the container does it for them.
#
# - RUNS IN THE BACKGROUND: the server starts immediately, without waiting for the two downloads. The Models card reads
#   the state files below to say "installing automatically" instead of handing over a command to type.
# - INSTALLS ONCE: agy goes to ~/.local/bin, grok to ~/.grok/bin, and both were already linked into /data in the
#   loop above, so they SURVIVE every image update. On later boots, seeing them present, it does nothing.
# - IF IT FAILS, IT FAILS: network blocked, vendor changed the URL... it only records the outcome so the Models card
#   tells the truth, and the next start tries again. It never stops the server from starting.
# - Turn it off entirely: set JAVIS_AUTO_INSTALL_CLIS=0 (machine with no Internet, or you do not want these two CLIs).
CLI_STATE="$PERSIST_ROOT/.cli-auto-install"
co_cli() {   # <binary name> <default install path>
    command -v "$1" >/dev/null 2>&1 || [ -x "$2" ] || [ -x "$HOME/.local/bin/$1" ]
}
tu_cai_cli() {   # <binary name> <default install path> <install script URL>
    co_cli "$1" "$2" && { echo "ok $(date +%s)" > "$CLI_STATE/$1" 2>/dev/null; return 0; }
    echo "installing $(date +%s)" > "$CLI_STATE/$1" 2>/dev/null
    echo "[$(date -u +%FT%TZ)] installing $1 from $3" >> "$CLI_STATE/install.log" 2>/dev/null
    if curl -fsSL --max-time 300 "$3" | bash >> "$CLI_STATE/install.log" 2>&1 && co_cli "$1" "$2"; then
        echo "ok $(date +%s)" > "$CLI_STATE/$1" 2>/dev/null
    else
        echo "failed $(date +%s)" > "$CLI_STATE/$1" 2>/dev/null
    fi
}
# Two layers: the outer one exits at once so the inner one is orphaned and adopted by tini (PID 1), which reaps it
# when done. With only one layer, after `exec` it would be a child of uvicorn, Python does not reap strangers, and a zombie is left.
if [ "${JAVIS_AUTO_INSTALL_CLIS:-1}" != "0" ] && mkdir -p "$CLI_STATE" 2>/dev/null; then
    ( (
        tu_cai_cli agy "$HOME/.local/bin/agy" https://antigravity.google/cli/install.sh
        tu_cai_cli grok "$HOME/.grok/bin/grok" https://x.ai/cli/install.sh
    ) </dev/null >/dev/null 2>&1 & )
fi

exec "$@"
