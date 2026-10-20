# T4 adaptive team chat measurements (0.170.0) - local machine, FAKE engine, NOT a VPS

Tools: `tools/team_adaptive_bench.py` (the real host `main.app` in-process through the httpx ASGITransport, a fake engine with counters,
a guard that blocks every path that would build a real engine) and `tools/team_adaptive_ui_bench.js` (the pure render functions under node). Raw results:
`exports/reviews/team-adaptive/t4-bench-2026-10-15.json` (the review bundle folder, outside git). Regression:
`tests/python/test_team_t4_perf.py` (checks by counts, with wide time thresholds).

No number here is a VPS number. The read-only VPS measurement script is prepared in `tools/team_adaptive_vps_measure.py`, **not run yet**.
Until the VPS is measured, do not conclude that the lag is gone.

## Machine and conditions

- Windows 11 Pro 10.0.26200, Intel64 Family 6 Model 165 (8 threads), Python 3.12.10, node v24.15.0. The machine was running other
  working sessions (not isolated), so the times are only for comparing order, not a commitment.
- Command: `python tools/team_adaptive_bench.py --out exports/reviews/team-adaptive/t4-bench-2026-10-15.json` (defaults).
- Data: 12 teams x 1,500 messages = 18,000 messages, 8 assistants (4 with Auto on), 4 members per team, 1,500 owner reactions seeded
  straight into the store (the outbox still waiting to be projected), 12 hibernating team contexts and 12 due contexts, 8 private chat sessions.
- Fake engine: 5 ms per turn. The scheduler's background pulse is stopped (`JAVIS_PULSE_TICK_PAUSED=1`), and the bench calls the tick directly. `JAVIS_RESONANCE_CALL_CEILING`
  is not set. SQL statements are counted with the sqlite3 trace callback on every connection.

## Sequential API (30 calls per route, server-side time)

| Route | p50 | p95 | SQL read / write statements (max) |
|---|---|---|---|
| GET /teams/{id} (team page) | 54 ms | 64 ms | 25 / 0 |
| GET /teams/{id}/messages (message page) | 10 ms | 13 ms | 5 / 0 |
| POST team reaction | 72 ms | 96 ms | 26 / 9 |
| POST private chat reaction | 52 ms | 76 ms | 25 / 8 |
| GET /agents/{slug}/pulse (pulse panel) | 37 ms | 45 ms | 17 / 0 |

The SQL statement counts of the message page and the team page are **unchanged** between a team of 60 messages and one of 600 (regression test) and between 100 and 1,500 messages.

## Event loop lag (10 ms timer)

| Phase | Duration | p95 | max |
|---|---|---|---|
| Requests only (8 threads x 30 mixed requests) | 6.2 s | 0 ms | 45 ms |
| Judge batch only (24 messages without an @ at once) | 1.1 s | 1.7 ms | 75 ms |
| Pulse tick only (5 ticks) | 7.1 s | 10.7 ms | 217 ms |
| All at once | 13.5 s | 3.2 ms | 245 ms |

In the concurrent phase, request latency was p50 338 ms, p95 1.29 s (240 requests, at the same time as 24 judge batches and 5 ticks).

One pulse tick: 3.4 s the first time (projecting the remaining outbox), 0.5 to 1.5 s afterwards; 1.9 to 3.0 s when run under load. The
heavy part runs in a worker thread (`asyncio.to_thread`).

## Fake model turns

Concurrent phase: 24 team turns, 24 judge batches (each message without an @ is exactly one batch), 0 scan turns. Zero scan turns is by design 5.5:
a wake-up runs code first, and with no new opportunity it does not call the model. No real engine was built (`real_engine_guard`).

## Feedback outbox

1,500 reactions still `pending` were drained in 8 projections (at most 200 rows each), 48 s, about 32 ms per reaction. In the run
with 6 teams x 300 messages (same machine): 150 reactions in "Waiting for review" after draining, each steady projection costing about 700 ms (about 4.7 ms
per waiting reaction, ceiling 200 rows per tick).

## Browser rendering (limitation)

Playwright for Python is not in `.venv`, so a real browser was not measured (layout, paint, two real tabs). Substitute: the time to
build the HTML string with the dashboard's own render functions under node:

| Task | p50 | p95 |
|---|---|---|
| List of 12 teams | 0.4 ms | 7.7 ms |
| Frame of 200 messages (94 KB HTML) | 2.8 ms | 5.3 ms |
| SIMULATED 20 reaction packets to 2 tabs, each packet redrawing the whole 200 message frame (the bench loop redoes the work of `onTeamEvent`, without calling it) | 92 ms | 101 ms |
| 500 chips + the reaction picker | 25 ms | 36 ms |

## Before and after the T3 performance fix (T3 branch `7e8b96f5`)

Same machine, same default command, same data. "Before" is T4 head `89a0acd1` (T3 only had P and J, no performance fix yet); "after" is
the T4 head after merging T3 `7e8b96f5` (P, J, L; the judge batch and pulse tick leave the event loop through `server/io_offload.py`, the projector
works in batches; T3's measurements are in docs/dev/team-chat-t3-pulse.md section 9). (The T3 branches after `7e8b96f5` up to `054975b3` only fix behavior and UI, and do not change the measured hot path.) Raw results of the second run:
`exports/reviews/team-adaptive/t4-bench-2026-10-15-after-t3-fix.json`. The machine is shared with other sessions, so a difference of a few tens of ms
between the two runs is noise; read only the large changes.

| Measurement | Before | After |
|---|---|---|
| Max event loop, pulse tick only | 217 ms | **39 ms** |
| Max event loop, all at once | 245 ms | **67 ms** |
| Max event loop, judge batch only | 75 ms | 73 ms |
| Max event loop, requests only | 45 ms | 52 ms |
| Request p95 when all at once | 1.29 s | 0.93 s |
| One pulse tick (tick only, runs 2 to 5) | 0.46 to 1.5 s | 0.26 to 0.51 s |
| One steady projector projection | 2.5 to 3.6 ms (0 waiting reactions) | 16 to 21 ms with **1,125** reactions "Waiting for review" (previous version: about 700 ms with 150) |
| Draining the outbox of 1,500 reactions | 48 s | 81 s (more reactions go into "Waiting for review", because part L now serves the reason) |
| GET team page p50 / SQL read statements | 54 ms / 25 | 49 ms / 25 |
| GET message page p50 / SQL read statements | 10 ms / 5 | 14 ms / 5 |
| POST team reaction p50 / reads, writes | 72 ms / 26, 9 | 80 ms / 26, 9 |
| POST private chat reaction p50 | 52 ms | 43 ms |
| GET pulse panel p50 / SQL read statements | 37 ms / 17 | 83 ms / **29** (adds part L's lessons section) |
| Fake model turns, concurrent phase | 24 team, 24 judge batches, 0 scans | 24 team, 24 judge batches, 0 scans (whole bench: 6 fake learning turns of L) |
| Real engines built | 0 | 0 |

Conclusion: the T3 fix removed most of the event loop lag in the pulse phase and the concurrent phase, and the projector's reconciliation cost
no longer grows with the number of waiting reactions. The pulse panel is slower because it has the extra lessons section (29 SQL read statements, still a constant). The judge
batch still sometimes holds the loop for about 70 ms on this machine. VPS not measured.

## Observations (the run before the T3 fix)

1. **The judge batch holds the event loop:** the `--stall-watch` diagnostic (captures the loop thread's stack when held more than 50 ms) pointed at
   `agent_judge.judge_team_message` calling `agent_judge_store` (`get_decision`, `profile`, `get_offset`, `add_decision`),
   `resonance_store.agent_any` (through `_agent_judge_resonance_on`) and `agent_ledger._tx` right on the loop thread. This belongs to part J;
   the fix direction is to move the batch's store work to a worker thread. Note: turning on `--stall-watch` slows the whole process (capturing stacks contends for the
   GIL), so use it only for diagnosis and do not use the numbers from that run.
2. **Pulse tick:** in the tick-only phase, no stack of Jarvis 007 code was caught on the loop thread; the max lag of about 0.2 s
   is most likely from the projector's worker thread (reconciling each reaction's status, every row opening several SQLite connections) contending for the GIL.
   While part L is not merged, reactions in "Waiting for review" are never served, so this reconciliation repeats every 30 second tick
   (at most 200 rows).
3. **Concurrency slows requests:** request p95 1.3 s with 8 request threads plus the judge batch and tick, against under 0.1 s when
   sequential. It must be measured again on the VPS (different disk and CPU) before concluding.
4. **Every reaction packet redraws the whole message frame** of each tab (O(number of visible messages)). Fine at 200 messages.
