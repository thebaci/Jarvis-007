# Thorough update for Jarvis 007 - Design

Date: 2026-07-18
Status: design approved, preparing the plan.

## Goal

Make Jarvis 007's update feature solid and safe: a user clicks one "Update now" button and
reaches the new version in every environment, sees clear step-by-step progress while it runs,
and if the new version is broken there is a way back to the old one.

Scope settled with the project owner:
- Do NOT build background auto-update (considered and rejected).
- Do NOT write an updater sidecar for Docker (saved for self-managed VPS later).
- Priority environment: Docker (Hostinger/VPS).
- Docker rollback follows Option B (guided), not automatic rollback inside the container.

## Current state

Already in place (not redone from scratch):
- `GET /version` (server/main.py ~3688): reads the local `VERSION`, compares with
  `raw.githubusercontent.com/blogminhquy/javis-os/main/VERSION`, semver-style compare,
  returns `{current, latest, update_available, mode, can_self_update, error}`.
- `POST /update` (~3712): by mode. Docker calls Watchtower `http://watchtower:8080/v1/update`
  (only when Watchtower is running); Windows writes `_selfupdate.bat` (git pull + relaunch) run
  detached; Native runs `bash update.sh native`.
- `GET /changelog` (~3859): parses the local CHANGELOG.md + cross-checks GitHub.
- `GET /health` (~1436): returns 200 when the server is alive (with Claude CLI status).
- Frontend `dashboard/console.js`: `ovLoadVersion()` (~1379) + the update button handler
  (~1411) poll `/version` until the version changes and then reload; the changelog page (~336).
- Windows autostart (HKCU Run key) + `start-javis.vbs` (kill the old instance + run in the
  background `.venv\Scripts\python.exe server\main.py`).
- CI `.github/workflows/docker-publish.yml`: push main -> build + push GHCR tags `:latest` and
  `:<git-sha>`.
- Docker: the app does NOT mount the docker socket (security). Hostinger uses
  `docker-compose.hostinger.yml` (NO Watchtower, updates by Redeploy). `docker-compose.yml` has a
  Watchtower service in the `update` profile (off by default). The Dockerfile + compose both
  have a HEALTHCHECK calling `/health`.

## Four gaps to patch

1. The Windows updater LACKS `pip install`. `_selfupdate.bat` only does git pull + relaunch. If
   the new version adds a Python library the app crashes when it comes back up. (The native
   `update.sh` does install.)
2. A dirty git tree makes `git pull --ff-only` abort silently -> the update fails while the UI
   only says vaguely "the server came back but the version did not change".
3. No health check + rollback. If the new version fails to boot, the app is dead and does not go
   back on its own.
4. A poor update experience: no step-by-step progress, no changelog of the new version shown
   before clicking, no clear way back when it breaks.

The technical fact shaping the design: Watchtower does NOT roll back by itself (the project
owner confirmed no such feature will be added). The app inside Docker has no Docker permission
so it cannot swap/revert the image by itself. Therefore a truly automatic rollback is only
feasible for the git-checkout installs (Windows/native); Docker uses a guided rollback.

## Solution architecture

Split into four blocks, communicating through state files on STATE_DIR and HTTP endpoints.

### Block 1 - CI: version tag (the foundation of Option B)

`docker-publish.yml` adds the tag `${IMAGE}:<version>` (read from the VERSION file) next to
`:latest` and `:<sha>`. Result: GHCR always has a fixed, readable version tag to pin when
rolling back.

- Input: the VERSION file at the repo root.
- Output: an added tag line in the "Build & push" step.
- Depends on: nothing.

### Block 2 - Update state (the shared source of truth)

The file `STATE_DIR/update_state.json` is the source of truth, SURVIVING restart/recreate of the
container (it sits on the /data volume in Docker). Schema:

```json
{
  "phase": "idle|preparing|pulling|installing|restarting|health_check|rolling_back|done|error",
  "result": "success|rolled_back|pull_failed|rollback_failed|error|null",
  "old_version": "0.9.78",
  "target_version": "0.9.79",
  "old_sha": "<git sha before the pull, git mode only>",
  "previous_version": "0.9.78",
  "last_good_version": "0.9.79",
  "stashed": false,
  "started_at": "<iso>",
  "finished_at": "<iso|null>",
  "error": "<short error string|null>"
}
```

- `last_good_version` / `previous_version` are maintained by a hook at server STARTUP: read the
  file; if `last_good_version` differs from `current` and `current` is newer, set
  `previous_version` = the old `last_good_version`, then `last_good_version = current`. This
  way every mode (Docker included) knows "where to roll back to".
- `phase`/`result`/`error` are written by the updater (Windows/native) or the `/update` flow
  (Docker) during the update.
- Pure Python helpers: `_read_update_state()`, `_write_update_state(patch)`,
  `_record_boot_version(current)`. This is the easiest part to test.

### Block 3 - Backend: /update, /update/status, /version

`POST /update` is rewritten by mode:

- Windows (git checkout): the server writes `update_state` (preparing, old_version, old_sha from
  `git rev-parse HEAD`, target=latest), then spawns the script `server/updater/win_update.ps1`
  DETACHED (PowerShell, easier for HTTP polling + logic than .bat) with parameters: root, path
  of the .venv python, port, old_sha, target, logfile, statefile. No more generating an inline .bat.
- Native (git checkout): spawn `bash update.sh native` as before but update.sh is upgraded.
- Docker with Watchtower: trigger as before, write update_state (phase=restarting,
  target=latest). The new container boots -> the boot hook seals success.
- Docker without Watchtower (Hostinger): return `ok:false` with RICHER Redeploy instructions:
  state `current`, `latest`, and the old version tag `previous_version` to pin if a rollback is
  needed.
- Duplicate-run guard: if `phase` is in progress and `started_at` is recent, return "already updating".

`GET /update/status` (new): returns the contents of `update_state.json` + the last ~50 lines of
`update.log`. The UI polls this to draw progress and show the result (even after the server has
finished restarting).

`GET /version`: add the field `previous_version` (from update_state) so the UI knows the
rollback target. Keep the old fields.

The updater scripts (Windows ps1 and native update.sh) do the same sequence:

1. preparing: make sure old_sha and target are present.
2. pulling: handle a dirty git tree safely - `git stash push -u? NO` (u drags in junk files);
   use `git stash` (tracked only), set `stashed=true` if something was stashed; `git pull --ff-only`.
   Do NOT `stash pop` automatically (avoids conflicts with the new code) - leave the stash for
   the user to restore, record `stashed=true` so the UI can say so. Pull fails ->
   result=pull_failed, relaunch the OLD version (code unchanged), stop.
3. installing: `pip install -r requirements.txt` into .venv (Windows: this is the missing step).
4. restarting: stop the running version then start the new one (Windows uses stop-javis.bat +
   start-javis.vbs; native uses systemctl restart javis if present).
5. health_check: poll `http://127.0.0.1:<port>/health` for up to ~90s. Success = /health
   returns 200 AND `/version.current == target`. If /health does not come up within 90s -> failure.
6. Conclusion:
   - Healthy + right version: phase=done, result=success.
   - /health does not come up (the new version is broken): phase=rolling_back,
     `git reset --hard <old_sha>`, pip install (old version), restart, poll again. Comes up ->
     result=rolled_back; still broken -> result=rollback_failed (write the log for manual rescue).
   - /health comes up but the version did not change (the pull did not apply even though it
     reported ok): treat as a warning, the server is still alive (old version), no rollback;
     result=error with a note.

The script runs DETACHED so it survives independently when the server is killed. Every step
writes update_state + appends to update.log.

### Block 4 - Frontend: update experience

Overview page: an expanded version panel.

- Normal state: show `current`, `latest`, mode. When a new version exists, additionally show the
  CHANGELOG of the versions between current and latest (using the `/changelog` data, filtered to
  versions not yet installed) so the user sees what they are about to get before clicking.
- The "Update now" button: shown when `update_available && can_self_update`. For Docker without
  Watchtower, replace it with a Redeploy instructions block (richer: with the command + the tag
  to roll back).
- On click: confirm -> POST /update -> go to the progress screen.
- Progress screen: a step bar Preparing -> Downloading code -> Installing libraries ->
  Restarting -> Health check -> Done. Fed from polling `/update/status` (the `phase` field)
  combined with `/version`. It has a built-in reassurance line: "if the new version fails, the
  system will go back to the old one on its own" (git mode) or "you can roll back to the old
  version following the instructions" (Docker).
- Final states:
  - success -> "Updated to vX" -> auto reload.
  - rolled_back -> "The new version vX failed, rolled back to vY on its own. See update.log."
    (no reload).
  - pull_failed / error -> show the error + the log tail + the manual command.
  - Docker where the new version does not come up (the version does not arrive after a long
    time) -> a guided rollback panel: pin the tag `:<previous_version>` + a copy-command button
    (`docker compose ... pull && up -d`, or change the tag then Redeploy on Hostinger).

Keep the existing changelog page as is.

## Error handling (summary)

- Dirty git tree: stash tracked files before the pull, no auto-pop, tell the user it was stashed.
- Missing new dependency: the pip install step is mandatory in every git mode.
- The new version crashes at boot: git mode automatically does `git reset --hard` to old_sha +
  restart. Docker: instructions to pin previous_version.
- Duplicate update run: guard by phase + started_at.
- Network lost when checking for a new version: `/version`/`/changelog` still return the local part.
- The rollback also fails: keep the log intact, report clearly, leave it for manual rescue
  (delete nothing).

## Testing

- Pure functions: `_ver_tuple`, `_ver_newer` (add cases), version compare edge cases.
- update_state: round-trip read/write; deriving `previous_version` when booting into a newer version.
- `/update/status`: returns the right structure with/without a state file.
- Rollback decision: split out a helper (e.g. `_health_ok(port)` + a decision function) and test
  with a fake (mock) health -> red health reports that rollback is needed.
- The duplicate-run guard of `/update`.
- The ps1/sh scripts are hard to unit-test in CI: at least lint + check the JSON they produce;
  manual smoke test on the project owner's Windows machine.

Run tests with .venv (the system Python lacks libs). Only when tests are done and green: bump
VERSION + CHANGELOG + commit + push origin/main (following the project owner's auto-push habit).

## Files expected to be touched

- `.github/workflows/docker-publish.yml` - add the version tag.
- `server/main.py` - rewrite `POST /update`; add `GET /update/status`; add `previous_version` to
  `/version`; the boot hook that records the version; update_state helpers; drop generating the
  inline `_selfupdate.bat`.
- `server/updater/win_update.ps1` - the new Windows updater script (takes parameters).
- `update.sh` - add SHA saving + health poll + git reset rollback.
- `dashboard/console.js` (+ related CSS) - the update panel + progress screen + rollback panel.
- `server/tests/test_update.py` - tests as above.
- `VERSION` + `CHANGELOG.md` - bump when done.

## Out of scope (not this time)

- Background auto-update (poller + on/off switch + channel + quiet hours).
- An updater sidecar with a socket for Docker (automatic rollback inside the container).
- Changing the Hostinger deploy model away from Redeploy.
