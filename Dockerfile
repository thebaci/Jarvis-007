# syntax=docker/dockerfile:1
# ============================================================================
# Jarvis 007 - container image
# "Brain" = Claude Code CLI (npm global). FastAPI app served by uvicorn.
# Code tree is immutable; ALL mutable state lives on the /data volume and the
# Claude auth volume (~/.claude). Node comes from the official image (Debian's
# nodejs lags LTS), and tini runs as PID 1 so signals reach uvicorn cleanly.
# ============================================================================

# ---------- Stage 1: Node 22 LTS source ----------
# Copy node/npm/npx from the official image instead of apt (Debian's nodejs lags LTS).
FROM node:22-bookworm-slim AS node_source

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim

# OCI image labels: Docker Manager (Hostinger) + registries read these to show the "Guide" column
# (Documentation / Quick start / Source). Point to the docs on GitHub.
LABEL org.opencontainers.image.title="Jarvis 007" \
      org.opencontainers.image.description="AI operating layer: chat + voice + second brain + automation, built on the CLIs of AI providers (Claude Code, ChatGPT/Codex)." \
      org.opencontainers.image.url="https://github.com/blogminhquy/javis-os" \
      org.opencontainers.image.source="https://github.com/blogminhquy/javis-os" \
      org.opencontainers.image.documentation="https://github.com/blogminhquy/javis-os/blob/main/docs/README.md" \
      org.opencontainers.image.licenses="MIT" \
      com.hostinger.documentation="https://github.com/blogminhquy/javis-os/blob/main/docs/README.md" \
      com.hostinger.quickstart="https://github.com/blogminhquy/javis-os/blob/main/QUICKSTART.md"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: ca-certs (TLS), git (Claude tools), ripgrep (fast search used by
# Claude's Grep), ffmpeg (edge-tts mp3), curl, tini (PID-1 reaper for the node
# subprocesses Claude spawns).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git ripgrep ffmpeg tini \
    && rm -rf /var/lib/apt/lists/*

# Node 22 LTS from stage 1 (npm/npx are symlinks → recreate on PATH).
COPY --from=node_source /usr/local/bin/node /usr/local/bin/node
COPY --from=node_source /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# System libraries for Chromium (UI testing with Playwright).
#
# Why they must be INSIDE the image and not installed at runtime: the container runs as the non-root
# user `javis` and the source code is read-only, so a button in the app CANNOT run `apt-get`. This is
# the only part that has to be there up front.
#
# The browser ITSELF is NOT in the image: it is heavy and most users do not need it.
# Whoever needs it presses the button on the Plugins page, and Jarvis 007 downloads it to `<state>/browsers` - a folder on
# the mounted volume, so it survives every update and does not have to be downloaded again.
#
# Kept as its OWN layer so its cost can be measured (`docker history`), and so it can be switched off with
# `--build-arg WITH_BROWSER_DEPS=0` when someone wants the smallest possible image.
ARG WITH_BROWSER_DEPS=1
RUN if [ "$WITH_BROWSER_DEPS" = "1" ]; then \
        npx -y playwright@latest install-deps chromium \
        && rm -rf /var/lib/apt/lists/* /root/.npm; \
    fi

# The brain: Claude Code CLI, installed globally. Overridable build-arg.
ARG CLAUDE_CLI_VERSION=latest
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CLI_VERSION}" \
    && npm cache clean --force \
    && claude --version

# Codex CLI - for the ChatGPT subscription provider (OpenAI OAuth). Sign in once on the Models page
# (the token is stored in the .codex volume).
#
# No longer best-effort since 0.35.7: the old `|| echo` approach swallowed install errors, and that really
# happened - an image was released WITHOUT codex, and a new user's ChatGPT sign-in showed green (OAuth is handled by
# Jarvis 007 itself, no binary needed), then chat broke with not a single error line pointing the way (report of 16/08).
# If codex is missing the build must go RED so CI stops it; never ship a crippled image.
# CI resolves latest to a concrete version before building: a new CLI version
# changes this layer's cache key even when the Dockerfile itself is unchanged.
ARG CODEX_CLI_VERSION=0.153.4
RUN npm install -g @openai/codex@${CODEX_CLI_VERSION} && npm cache clean --force && codex --version

# Gemini CLI is NO LONGER pre-installed (dropped in 0.29.1).
#
# 0.28.8 installed it, but at that time nobody knew Google had stopped serving Gemini CLI for ALL
# personal accounts from 18/06/2026 (free, AI Pro, Ultra - code UNSUPPORTED_CLIENT). For nearly every
# Jarvis 007 user, that package now downloads a CLI that cannot be used: a bloated image, a slower build, and worse,
# a dead card that looks ready.
#
# That engine was REMOVED from the repo entirely in 0.50.0. The Google route for personal accounts today is the
# Antigravity CLI (`agy`); the xAI route using a SuperGrok / X Premium+ plan is Grok Build (`grok`).
# Both are download-and-run scripts, not installed through npm, so they are not in the image: embedding
# Google/xAI binaries in a public image is redistributing their software. Instead,
# docker/entrypoint.sh installs them when the container starts (0.85.1), into folders already linked to the
# /data volume, so they are installed only once. Turn off with JAVIS_AUTO_INSTALL_CLIS=0.

WORKDIR /app

# Layer-cached Python deps (copy requirements first so app changes don't re-pip).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App source.
COPY . .

# Non-root runtime user. Code stays root-owned + read-only; state on volumes.
RUN useradd -u 10001 -m -d /home/javis javis \
    && mkdir -p /data/state /data/vault /brains /home/javis/.claude /home/javis/.codex \
    && chown -R javis:javis /data /brains /home/javis

# Writable state under /data; ALL second brains under /brains (separate mount -> can be git-backed-up).
ENV JAVIS_HOST=0.0.0.0 \
    JAVIS_PORT=7777 \
    JAVIS_STATE_DIR=/data/state \
    BRAIN_PATH=/data/brain \
    BRAINS_DIR=/brains \
    OBSIDIAN_VAULT_PATH=/data/vault \
    CLAUDE_CWD=/app \
    HOME=/home/javis \
    PATH=/usr/local/bin:$PATH

# Codex (ChatGPT) wraps every file read/write command of its own in bubblewrap. Bubblewrap needs to create a user
# namespace + change the propagation of `/`, but this container runs as a normal user without CAP_SYS_ADMIN,
# and Ubuntu 24.04 also blocks unprivileged user namespaces with AppArmor. So HERE that guard is not
# "stricter" but "completely dead": every background job running on ChatGPT returns
# `bwrap: Failed to make / slave: Permission denied` for EVERY single command, and the loop cannot read
# a single file (the repo owner reported it on 2026-08-07 with a screenshot). Turn off Codex's own guard and let
# the CONTAINER ITSELF be the guard.
#
# The trade-off must be stated plainly: Codex has no per-call allowlist like Claude, so with this flag a `suggest`-level
# loop running on Codex has nothing left stopping it from writing files inside the container. The guards on
# money/orders/posting/sending messages are NOT affected - they live in the MCP Hub, not in the sandbox.
# To turn the guard back on: set JAVIS_CODEX_SANDBOX=auto and grant the container permissions (e.g.
# `security_opt: [apparmor:unconfined]`) so bubblewrap can start.
ENV JAVIS_CODEX_SANDBOX=off

USER javis

# Persist state (/data) + brains (/brains) + Claude auth + Codex auth (login ChatGPT).
VOLUME ["/data", "/brains", "/home/javis/.claude", "/home/javis/.codex"]

EXPOSE 7777

# Healthcheck hits the public /health endpoint with stdlib only (no curl).
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.getenv('JAVIS_PORT','7777')+'/health',timeout=4).status==200 else 1)" || exit 1

# tini reaps node subprocesses; entrypoint.sh links ~/.local, ~/.antigravity, ~/.config
# into /data/home first so a CLI the user installed themselves (agy) + its login SURVIVE UPDATES
# (previously HOME was on no volume -> every image change meant installing and signing in again).
# uvicorn launched with --app-dir server because main.py uses the "main:app" import
# string and `from claude_cli import ...`.
ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker/entrypoint.sh"]
CMD ["sh", "-c", "python -m uvicorn main:app --app-dir server --host ${JAVIS_HOST} --port ${JAVIS_PORT}"]
