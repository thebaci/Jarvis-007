# D0: checking release 0.86.0 on localhost (2026-10-08)

**Evidence level: local operation.** This is NOT a VPS check, and it is not a check of the server running on port 7777 of the project's host machine. The VPS was not checked because the Hostinger connection in the working session was cut.

| Item | Value |
|---|---|
| Code run | Clean worktree split from release commit `438f83097db4ee64e96b7b4880deb581521f217a` (VERSION 0.86.0). At check time, `main` had already moved to 0.86.1 (#589), but the check deliberately pinned 0.86.0 |
| How it ran | `python server/main.py` from that worktree, port 7788, temporary `JAVIS_STATE_DIR` and `BRAINS_DIR`, `JAVIS_REQUIRE_LOGIN=0`, with the `CLAUDE*` / `ANTHROPIC*` variables of the Claude Code session removed from the environment (keeping `CLAUDE_CONFIG_DIR`) |
| Claude Code on the machine | 2.1.293 (the same build that went into the 0.86.0 Docker image) |
| Script | `exports/reviews/D0-localhost-0860-smoke.py` (outside git). The server log and the temporary data folder were deleted during cleanup; the results below are copied from the output of the run |

## Results without calling a model: 13/13

1. Clean start, `/health` returned 200 after 7 seconds.
2. Dashboard `/` returned 200; `/app-version` reported `0.86.0`; assets carry `?v=0.86.0`.
3. The Resonance switch is off by default (`{"ok": true, "enabled": false}`).
4. WebSocket `/ws` accepted the connection through the Origin check.
5. With the feature off, opened the dashboard and waited more than one scheduler tick (35 seconds): no `resonance.sqlite3` was created.
6. The server log has no Traceback or `[resonance` error.
7. Turned Resonance on for the temporary brain through the API.
8. Restarted after 7 seconds.
9. After the restart the switch is still on (kept in the brain).
10. The goal list API works and returns empty.
11. Turned on and passed one scheduler tick: the log has no errors.
12. Turned Resonance off again.
13. WebSocket still accepts connections after the restart.

Notes:
- Calling `GET /resonance/goals` directly creates the `resonance.sqlite3` store even when the feature is off. This is intentional in M4 (viewing and stopping old goals does not require the switch). The dashboard does not call this API on its own.
- In the browser, `/tools/optional` returns 401. This endpoint requires a login session, and the test server had login turned off; it is not part of the Resonance change.

## One real chat turn: passed

- The user approved exactly 1 turn. For the engine, only the engine choice was copied from the real settings: `anthropic-cli` / `claude-opus-5-5`, Max plan; the token had about 15,400 seconds left before sending.
- Message: "Chào Jarvis 007, đây là tin thử sau khi nâng cấp. Em trả lời ngắn một câu: em đang chạy phiên bản nào và bằng bộ não gì?" (Vietnamese: "Hello Jarvis 007, this is a test message after the upgrade. Answer in one short sentence: which version are you running and with what brain?")
- Result after 10 seconds: the `turn_done` frame has `engine_status: ok`, `turn_status: completed`, and no engine error. The answer correctly named Claude Code and `claude-opus-5-5`, and said it does not see a version number in its context so it did not report one.
- The conversation was saved to the session list. The server log has no Traceback.

## No evidence yet

- A specific VPS that pulled the 0.86.0 image and ran stably (version, chat, data after restart, error log).
- A trial of Resonance on a real brain or agent with real work.
