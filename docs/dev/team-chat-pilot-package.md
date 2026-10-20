# Adaptive team chat pilot package on a real model (T1-T4)

Status: **run once on 2026-10-16** on 0.170.0, with the owner approving a ceiling of 30 (lower than the 60 proposed in section 3). The original report and
evidence are outside the repo: `exports/reviews/team-adaptive/pilot-2026-10-16/PILOT-REPORT.md`. Nobody reruns this package, retries, raises the ceiling or switches to a paid API without a direct approval order
from the project owner (GOAL section 13). The fake engine proved the technical part (matrix: [team-chat-acceptance-matrix.md](team-chat-acceptance-matrix.md));
the fake engine does NOT prove discussion quality, judging or learning on a real model. This package exists to prove that part.

## 1. Preconditions before asking for approval

- Fixed head: the SHA of the T1-T4 integration branch with green CI on exactly that head; record the SHA in the report. Part L of T3 (lessons, teammate
  feedback, self-review) is merged on the T3 branch (last `054975b3`, verification review passed).
- Clean checkout (`git status` empty), the repo's `.venv`, a NEW state in a temp directory (do not use the owner's real state), and a dedicated pilot
  brain with 4 assistants in different roles: coordinator (Lan), data (Minh), content (Hoa), verifier (Tuan).
- Sandbox server on port 7788 (never 7777), `JAVIS_STATE_DIR` pointing at the temp state. Stop it by port
  (`Get-NetTCPConnection -LocalPort 7788 | Stop-Process`), not by command line.
- Engine and provider are chosen by the owner on the sandbox's Models page (Jarvis 007 does not pick a model itself). Record: the team engine (each
  assistant's own model or the main model), the background-work engine (judging batch, scan turns). No paid API unless the owner says so explicitly.
- `JAVIS_PULSE_TICK_PAUSED=0` only when scenario P4 runs; for the other scenarios keep the background rhythm paused (`=1`) and call tick by hand so that
  turns can be counted.
- **The background rhythm is paused when EITHER flag equals 1:** `JAVIS_PULSE_TICK_PAUSED` or `JAVIS_RESONANCE_TICK_PAUSED` (`_pulse_tick` in
  `server/main.py`). Scenarios that need the rhythm (P4, the proactive turn of P5, the feedback review turn of P6) must set BOTH to 0. In the
  2026-10-16 pilot, part 2 set only the first flag, so 4 ticks ran no turn at all, which is why `reaction_review` sat waiting.

## 2. The owner's approval gate

Send the owner exactly one message containing: the SHA, the scenario list (section 4), the turn ceiling (section 3), engine/provider, the estimated time, and how to stop.
Start only when the owner replies with a clear approval in chat. Record the approval sentence verbatim and its time in the record. Every rerun (even
after a technical failure) is a new approval request.

## 3. Turn ceiling (`JAVIS_RESONANCE_CALL_CEILING`)

The shared ceiling is lifetime on the state (design 9.1): every team turn, judging batch, scan turn, review and self-review. A new state should
start from 0. Proposed **`JAVIS_RESONANCE_CALL_CEILING=60`**:

| Scenario | Expected turns | Includes |
|---|---|---|
| P1 direct call and speaking up unprompted | 10 | 3 messages x (1 reply turn + 1 judging batch) + up to 4 speak-up turns |
| P2 assignment, feedback, revising a version | 14 | plan, 2 work steps, 1 verification, 1 synthesis, one request revision and then redo |
| P3 six reactions and teaching the judge | 6 | 2 reply turns to get messages, 2 judging batches after the labels, 2 spare |
| P4 rhythm and wake-up | 8 | up to 4 scan turns over 4 ticks, 4 spare |
| P5 private chat | 6 | 2 direct questions (outside the ceiling: the owner types them) + 2 proactive turns with judging + 2 spare |
| P6 learning in the team (needs L) | 8 | 2 feedback review turns, 1 self-review, the next turn to see the change |
| P7 contribution credit | 4 | 1 synthesis with 2 inputs, feedback on the final result |
| 20% reserve for obligations | (automatic) | spontaneous turns are used only up to floor(60 x 0.8) = 48 |

Also: the pilot team's `daily_turns` is 40, `judge_daily` 20, and `agent_daily_calls` stays at the default 6. The per-team-turn time limit stays at the default
(`JAVIS_TEAM_TURN_TIMEOUT=600`).

## 4. Scenarios and matrix cases

| Code | What it does | Cases proved | Only fake-engine tests before the pilot |
|---|---|---|---|
| P1 | Owner @Minh asks for numbers; then a general question without @; then a chit-chat message | 2, 19, 10 | yes |
| P2 | Assign the team the job "November restocking plan"; Tuan verifies; the owner revises the request after the result | 3, 12, 11 | yes |
| P3 | Drop six emoji in the group and in private chat, change them, remove them; fix one silent case to "Should have spoken", and one spoken case to "interrupted" | 4, 21, 9 | yes |
| P4 | Turn on Auto for Minh and Hoa; let the rhythm run 4 ticks; one group has work, one is silent | 6, 7, 23, 24 | yes (fake clock) |
| P5 | Private chat with Hoa: a direct question; let Hoa take a proactive turn | 20 | yes |
| P6 | Feedback with a quality reason for Hoa; wait for the review turn; the next turn changes the way of working | 5, 17, 25, 26 | yes (L merged on the T3 branch `054975b3`) |
| P7 | Drop a heart on the P2 synthesis | 8, 28 | yes |

## 5. Stop conditions (stop immediately, no retry)

- The shared ceiling is hit (turn blocked with `server_ceiling`), or one scenario exceeds its expected total by more than 50%.
- Any tool call, file read/write, or send to an outside channel (Zalo, Telegram) inside the team: a safety failure.
- A looping call chain (the same pair of assistants calling each other more than 2 levels deep), or one reason running two turns.
- A login error or provider quota exhaustion: stop, record it as a technical failure, do not switch provider.
- Any sign that the real state's data was touched.

## 6. Evidence to keep (not edited after the run)

- SHA, commands, environment variables (keys masked), the owner's approval sentence, start and end times.
- A copy of the state after the pilot (`team.sqlite3`, `conversations.db`, `resonance.sqlite3`, `agent_judge.sqlite3`, `kanban.sqlite3`)
  made with the SQLite backup API, plus `agent_calls` exported as CSV (purpose, status, obligation, engine milestones).
- Screenshots of the Teams page (desktop, narrow screen, two languages), the rhythm panel and each assistant's judging history.
- The sandbox server log.
- The conclusion split into five kinds: technical pass, content awaiting the owner's approval, business not finished, stopped at the gate, technical failure. The original report
  stays as it is; the post-check is written to a separate file and the original evidence is not edited.

## 7. Returning to normal after the pilot

The pilot state is its own temp directory: delete the sandbox, no restore tool needed. If the pilot ran on an existing state (only when the owner
asks), use the restore sequence in [team-chat-t4-ops.md](team-chat-t4-ops.md) section 4 on a copy taken before the pilot.
