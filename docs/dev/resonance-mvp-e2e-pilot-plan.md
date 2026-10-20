# Resonance MVP end-to-end pilot over the real chat path: scenario and limits

**Status (8 Oct 2026): pilot run 5 passed technically and on content within the scope of the scenario; waiting for an integration check on `main` before release.** In runs 1 and 2 the brain did not form a goal; run 3 stopped at S2 (a file-posting conflict, fixed with a handoff); run 4 failed because of an authentication token refresh (the classification was fixed); run 5 went through the whole loop. Details for each run are below.

## Purpose

Sign off the missing MVP condition (plan 00-mvp, "MVP completion conditions", item 1): a request that needs to be pursued goes through the whole loop on a real host, including **forming a goal by itself** from a real chat message, acting with a receipt, verifying, resuming after an interruption and delivering the result to the right session. The M3 and M5 pilots both built the goal from a prepared proposal; this pilot lets the brain itself decide whether to call `javis_goal`.

## Runner

`tests/python/test_resonance_mvp_e2e_pilot.py`, opt-in through `JAVIS_RESONANCE_E2E` (`dry` or `real`); the safety gate is in `tests/python/_e2e_pilot_guard.py` (with its own test, `test_resonance_e2e_guard.py`, which always runs and calls no CLI or model).

- **Real server** of the checkout under review, in its own process, port 7791; a temporary `JAVIS_STATE_DIR` and `BRAINS_DIR` on a short path; the default brain (`Brain Default`, which the dashboard calls simply `"brain"`) has Resonance turned on.
- **Only the engine selection fields are copied** (`auxiliary`, `main`, `engine`, `claude_model`); the sandbox settings are checked to contain no `claude_auth` or `anthropic_api_key`. No channel, no account: nothing is sent outside.
- **Real path:** the message goes over the WebSocket `/ws` in exactly the dashboard's format; cards and feedback go through real HTTP (Origin is checked); background work runs on the real scheduler tick (30 seconds).
- **Real, deterministic interruption:** server A runs with `JAVIS_RESONANCE_TICK_PAUSED=1` (the Resonance tick is paused, but the chat turn can still form a goal), so it is certain that no background work turn has happened before it is killed; the WHOLE process tree is killed, not shut down gracefully. Every pilot variable inherited from the parent shell (paused tick, ceiling, binary, directories) is REMOVED before each server is built and then set back to the exact value; the report records the effective state of each server (`servers`).

### Cost safety gate (checked BEFORE the message is sent, no model call)

0. **The engine that will run is exactly the approved configuration** (e2e review round 2): resolve the main brain and the background work with the runtime's own rules (`aux_engine.main_spec`, `read_spec`, together with `claude_model`) on the sandbox settings, and compare against the configuration the user approved (run 2: `anthropic-cli` / `claude-opus-5-5` for the brain, `anthropic-cli` / `sonnet` for background work). If they differ or cannot be resolved, stop; never change the model by itself. The report records the resolved selection. `dry` mode has its own expectation: background work is a blocked provider.
1. **Environment:** drop every variable of the Claude Code session that runs the runner (`CLAUDE*`, `ANTHROPIC*`), keys (`*_API_KEY`, `*_AUTH_TOKEN`, `*_ACCESS_TOKEN`) and provider selectors (`AWS_*`, `GOOGLE_*`, `AZURE_*`, Vertex, Bedrock, gcloud). KEEP `CLAUDE_CONFIG_DIR` if the user set it (dropping it makes the process fall back to the default directory, which is not a clean profile).
2. **Binary:** find `claude` the way the engine finds it (`claude_cli.tim_binary`) in the filtered environment, then pin it for the server with `JAVIS_CLAUDE_CLI`, so the gate and the engine use the SAME binary.
3. **Authentication:** `claude auth status --json` run with that binary, in the filtered environment, in BOTH cwds: the brain (chat turn) and `STATE/resonance_cwd` (background work turn, whose tool configuration differs from the chat turn). Only accept `loggedIn`, `authMethod` = `claude.ai`, `apiProvider` = `firstParty`, with a `subscriptionType`. The report stores only those four fields and the binary version, not the email, ids or tokens.
4. **User and project settings sources:** the chat engine turns on `setting_sources = user, project, local`, so the gate inspects `settings.json` and `settings.local.json` in the configuration directory that `auth status` itself reports, plus the `.claude/settings*.json` of BOTH cwds. If there is an `apiKeyHelper`, a cloud credential refresh command, or an `env` that selects a key, provider or call path, STOP. An unreadable file counts as a risk. Only the key NAMES are recorded, never the values.
5. **Administrator-set sources** (e2e review round 2): `managed-settings.json`, the `managed-settings.d/*.json` directory at system locations, the registry key `SOFTWARE\Policies\ClaudeCode` (HKLM, HKCU), and managed/remote-style cache files in the configuration directory. The gate does NOT evaluate the content of these sources: if any source exists the environment is **not yet supported**, STOP. The current machine has none.

**Scope of the guarantee:** the gate proves the Claude authentication identity (subscription plan, first-party provider) for exactly the engine that will run. The gate does NOT prove that every child process spends no money: hooks, plugins and MCP may run their own processes or services. Those keys in the settings are recorded BY NAME in the report (`not_assessed`; on the current machine: `enabledPlugins` in the user settings). The label "every source reviewed" is not applied.

If the above cannot be proven, stop and do not send the message. The gate only proves the state at run time; it does not infer anything for earlier runs.

### Call ceiling

- **Unit:** an engine turn at host level. One brain turn can include many internal SDK requests (tool loops); this ceiling is NOT the number of requests sent to the provider, nor tokens or cost, and there is no data to count those requests.
- **Total 3** (`JAVIS_RESONANCE_E2E_MAX_CALLS`). The brain turn is counted before sending (the runner sends exactly one message). For the rest, the server blocks BEFORE a call that would exceed the ceiling with `JAVIS_RESONANCE_CALL_CEILING`: the check happens in the same reservation transaction and counts EVERY path by which Resonance calls the engine (background work turns, trial runs, the goal framer through the `call_ledger` ledger); the used count lives in SQLite so it survives restarts; the runner passes the variable to EVERY server process (a process without the variable has no shared ceiling).

## Scenario (`real` mode), run 2

The user's words, of the **maintain** type (exactly the `javis_goal` group under the current routing rules), simulated data, no tool named. The prompt below is the literal Vietnamese text sent by the pilot (it is test input and the content contract below matches Vietnamese phrases), followed by an English gloss:

> (Dữ liệu mô phỏng để thử nghiệm.) Từ giờ duy trì giúp mình ghi chú Inbox/viec-dang-do.md: lúc nào cũng liệt kê đủ các việc đang dở bên dưới, mỗi việc ghi người phụ trách và hạn chót. Khi mình báo thêm việc thì cập nhật vào, có bản mới thì báo mình xem. Đừng đụng tới Notes/ghi-chu-cu.md.
> Việc đang dở: Lan soạn kế hoạch bài viết tháng 11, hạn 09/10. Minh kiểm lại lịch đăng, hạn 10/10. Hà gửi bảng số liệu cho cả nhóm, hạn 12/10.

Gloss: "(Simulated data for testing.) From now on, please maintain the note Inbox/viec-dang-do.md: always list all the unfinished tasks below, each with the person in charge and the deadline. When I report more tasks, update it, and tell me when there is a new version to look at. Do not touch Notes/ghi-chu-cu.md. Unfinished tasks: Lan drafts the November post plan, due 9 Oct. Minh rechecks the posting schedule, due 10 Oct. Hà sends the data sheet to the whole team, due 12 Oct."

**Independent expectation contract** (e2e review rounds 2 and 3), taken from the user's words, not from the brain's proposal and not added to the prompt: kind `maintain`; file `Inbox/viec-dang-do.md`; the old note intact; and all three triples present:

| Task | Person | Deadline | Accepted characteristic phrases (every phrase in one variant must be present; the phrases are Vietnamese because the output is Vietnamese) |
|---|---|---|---|
| Draft the November post plan (Soạn kế hoạch bài viết tháng 11) | Lan | 09/10 | "kế hoạch" + "bài viết" (plan + posts); "kế hoạch" + "tháng 11" (plan + November); "kế hoạch nội dung" (content plan) |
| Recheck the posting schedule (Kiểm lại lịch đăng) | Minh | 10/10 | "lịch đăng" (posting schedule); "lịch" + "đăng bài" (schedule + publish posts) |
| Send the data sheet to the whole team (Gửi bảng số liệu cho cả nhóm) | Hà | 12/10 | "số liệu" (data figures) |

**Content acceptance is decided by the REVIEWER** (an acceptance process adjustment following e2e review round 4, option 1; the Resonance evaluation rules in the product are unchanged). Phrase matching cannot understand negation ("không gửi", do not send), opposite actions ("hủy lịch đăng", cancel the posting schedule), a wrong month, or merely the right topic ("kiểm tra số liệu", check the figures), so it is not used as the basis for acceptance:

- The runner computes a **supporting indicator** `content_candidate` (`_e2e_pilot_guard.content_contract`) per presentation unit (a table row, a list item together with its continuation lines, a paragraph, each line; headings are NOT merged with the items under them), using only units that talk about exactly one person. The result is `met` (the phrases, person and deadline are in the same unit), `not_met` (there is clear evidence of error: the name is not found, the task belongs to someone else, the right task with a different deadline, a person and deadline without the task), or `unverified` (the relation cannot be extracted: a sentence mentioning several people, a heading, a task with no date, a phrasing that is not supported). The indicator is written into the report for the reviewer's reference.
- The runner **saves the deliverable file INTACT** outside the temporary directory (next to the report, `<report name>-deliverable.md`) before cleanup, checks the copy's hash against the source hash; the report points to the exact file name and hash. Real mode requires `JAVIS_RESONANCE_E2E_OUT`.
- When every technical check passes, the conclusion of the run is `acceptance: pending_content_review` and `content_review: pending`: **the pilot is not yet accepted**. The reviewer compares the three triples of task, person and deadline against exactly that file and hash before deciding; it is never inferred from the indicator. If the technical checks fail it is `technical_failed`; if the run stops midway it is `stopped`.

A goal that misunderstands the kind or the file is still a hard technical error (pilot FAIL); wrong content is caught by the reviewer.

Every condition below is a HARD error (if one fails the pilot FAILS; there is no "note it and call it OK" branch).

| Step | What happens | Check |
|---|---|---|
| 0 | Server A starts (tick paused); safety gate | Right binary, native subscription plan, clean settings; the WebSocket accepts the connection |
| 1 | Send ONE message over `/ws`, wait for `turn_done` | The brain forms EXACTLY ONE goal through `javis_goal`, attached to the right session; **the kind is `maintain`**; **the goal's deliverable file is exactly the file the user named**; the original intent MATCHES the user's words in full; the card is placed in the right session with a receipt; no background work turn yet. If no goal is formed: record the result, STOP |
| 2 | Kill A, build B (tick running) | The scheduler tick does the background work turn by itself; receipt succeeded, right provider, 0 tool calls; **the file the user named** exists and its bytes match the hash the host recorded when posting; the deliverable is **saved intact** outside the temporary directory, hash matches; the content indicator is recorded (not a decision); the notification arrives in the right session with a receipt |
| 3 | Kill B, build C, wait more than two ticks | No repeated notification; no further calls |
| 4 | If the goal has criteria the user approves | A deliverable to approve (`artifact_ref`) is REQUIRED; click "Meets the bar" (the "Đạt yêu cầu" button) through the API as the button on the card does: 200 |
| 5 | Close the loop by the SCENARIO'S KIND (not by the kind the brain chose) | Assessment met, still active, `goal.maintained` has been reported to the session with a receipt, the review schedule falls within **[6 hours, 24 hours] after the assessment time (both ends inclusive)**; then the user **pauses through the API** so no background work remains. No further model calls in steps 4 and 5 |
| End | | The old note is intact (hash); total calls within the ceiling; the conclusion is `pending_content_review` if every technical check passes. **The reviewer decides the content** on the saved file |

Additional evidence saved: the `tool_call` / `tool_result` frames (including `ToolSearch`; the engine only forwards tool results truncated to 500 characters), the final answer, the Kanban task if any, the version hash of the repo's and the brain's `CLAUDE.md` together with the `javis_goal` plugin (the routing rules in use).

## Proposed limits for run 2

| Item | Proposal |
|---|---|
| Main brain turns | **1** (`anthropic-cli` / `claude-opus-5-5`, subscription plan that passed the authentication gate) |
| Background work turns | **1 expected, at most 2** (`anthropic-cli` / `sonnet`); a retry on a failed attempt waits 15 minutes, so within the real pilot window there is only 1 |
| Hard ceiling | **3 host-level engine turns** (1 Opus turn, at most 2 Sonnet turns), blocked before the turn that would exceed it, kept across restarts. Not 3 internal SDK requests. Hooks, plugins and MCP in the user's settings (current machine: `enabledPlugins`) are outside this ceiling and outside the gate's scope; a broader commitment would require isolating them in the sandbox |
| Approval proposal states | The runner's commit, the verbatim task wording, the scoring contract above, the specific engine configuration. The engine and authentication gate still runs right before the message is sent |
| Duration | About 8 to 15 minutes |
| Number of runs | **One.** No retry, no rewording, no raising the ceiling; every other decision is the user's |

## Checked in `dry` mode (no model call)

The runner after the round 2 fix: **14/14 checks green, 0 engine turns**, about 2 minutes: the safety gate runs FOR REAL (the engine resolves as dry expects; binary 2.1.292; `auth status` in both cwds reports `claude.ai` / `firstParty` / plan `max`; no risky key, no managed source; `enabledPlugins` in the user settings is recorded as out of scope), server up, WebSocket, paused tick on A (the report records A paused, B and C running, the ceiling and binary pinned on all three), kill and rebuild, the scheduler tick picks up the schedule by itself (the background engine is blocked before the call, as intended), the notification arrives in the right session with a receipt, no repeated notification, the card API through the Origin check, the old note intact. Separately, the REAL configuration (copying the engine selection fields): resolves to `anthropic-cli` / `claude-opus-5-5` and `anthropic-cli` / `sonnet`, matching the approved configuration.

## This pilot does NOT prove

- Channels other than web chat (Telegram, Zalo, voice).
- Real data or a multi-day goal; the guard jumping on real data.
- The case of a candidate falling in rank on a real model (M5; `no_improvement` is not turned into `regression`).
- The stability of the goal-forming decision: one run is only one sample.
- The real number of requests or cost sent to the provider.

## Command to run once approved

```bash
JAVIS_RESONANCE_E2E=real JAVIS_RESONANCE_PILOT_SETTINGS=D:/Project/Javis-OS/server/settings.json JAVIS_RESONANCE_E2E_MAX_CALLS=3 JAVIS_RESONANCE_E2E_OUT=docs/dev/resonance-mvp-e2e-pilot-2.json D:/Project/Javis-OS/.venv/Scripts/python.exe tests/python/test_resonance_mvp_e2e_pilot.py
```

## Fixes following the e2e review (PR #579, diff `d38d033a..2ba6f74b`)

1. **P1-1, the ceiling missed the goal framer.** `POST /goal-requests` called the framer with its own separate `CallBudget`, which did not write to the store. Now the framer reserves a row in the durable `call_ledger` ledger BEFORE the call, within the shared ceiling (`reserve_ledger_call`, in the same transaction as the ceiling check); it is refunded only when the engine was not called, and a call that errored still counts. The ceiling counts `SUM(goals.calls_used)` plus the ledger. The ceiling's docstring states plainly that the unit is a host-level engine turn. Tests: a ceiling of 0 blocks before the call; within the ceiling it calls exactly once and then blocks the next turn; reopening the store still blocks; a failing framer still counts; a blocked engine refunds the reservation; six simultaneous reservation requests with one slot left let exactly one through. Four mutations (dropping the reservation, the ceiling not counting the ledger, refunding even after a call, not refunding when blocked) all turn the tests red.
2. **P1-2, environment filtering was not enough to prove subscription-only use.** Added the four-layer safety gate above (environment, pinned binary, `auth status`, settings source review), stopping if it cannot prove it; tested with fake fixtures for `apiKeyHelper`, an `env` selecting Bedrock and keys, a broken file, and a different authentication method. Corrected an old claim: run 1 was NOT independently verified for its authentication method (see below).
3. **P2-1, a mandatory condition was only a note.** Removed every `hard=False` branch; a missing deliverable, a missing deliverable to approve when there are approval criteria, a file hash that differs from the hash at posting, or not closing the loop by the goal's kind are all hard errors, and the pilot exits with code 1. A deterministic interruption by pausing the tick on A. The original intent is compared as a FULL match. Save the tool frames, the final answer, the Kanban task and the routing rule version.

### Round 2 (diff `2ba6f74b..2a8db1aa` reviewed)

1. **P2-1, the gate did not check the engine about to run.** Added step 0 of the gate (resolve with the runtime rules, compare with the approved configuration, stop if different); `auth status` and the settings review run in both the chat-turn cwd and the background-turn cwd. Fixture tests: the brain choosing Codex, background work choosing OpenRouter, a different model, a different `claude_model`, unresolvable: all stop; dry has its own expectation.
2. **P2-2, the maintain scenario scored as passing even when misunderstood.** An independent expectation contract (kind, file, three person-and-deadline triples), scored on the real file; the loop-closing branch follows the scenario's kind, with no `achieve` branch left; the review schedule is checked at both ends. Fixture tests: content missing a person or date, a person and date on different lines, 19/10 not accepted as 9/10, a one-year or one-hour schedule: all fail.
3. **Unreviewed configuration sources.** Added managed sources (managed-settings.d, registry, cache): if present, stop as an unsupported environment. Hooks, plugins and MCP are recorded as outside the guarantee.
4. **Inherited pilot variables** are removed before each server is built; the effective state is written into the report.

The expectation script `PR-579-e2e-round3-expected-checks.py` (built from the reviewer's round 2 script: the same misunderstood goal through the real `form_goal` + `advance`, running the runner's own check expressions): 17 PASS, exit 0. On `2a8db1aa` the script stops immediately because the old runner has no expectation contract.

### Round 3 (diff `2a8db1aa..d5cff3d2` reviewed)

**P2, having the names and dates still scored as passing even when a task was missing or misattributed.** The contract now stores three triples of TASK, PERSON, DEADLINE; scoring is per presentation unit, using only units that talk about exactly one person, with three results `met`, `not_met`, `unverified` as described above. The question "is the same line too strict" was answered by additionally reading multi-line list items, paragraphs and items under headings; a layout beyond what can be read is `unverified`, not `not_met`.

Fixture tests (`test_resonance_e2e_guard.py`, 49 checks in total): a correct table, a one-line list, a multi-line list (the reviewer's case), grouping by person under headings, two-line prose, a table with a summary row mentioning all three people: `met`. Only person and deadline (the reviewer's case), a table with only person and deadline columns, a missing task, a wrongly assigned person (the reviewer's case), a wrong deadline, another person's deadline, an empty deliverable: `not_met`. An unsupported phrasing: `unverified`.

The expectation script `PR-579-e2e-round4-expected-checks.py` (built from the reviewer's round 3 script: a real maintain goal passing by the host's criteria, the right file, hash and schedule; running the runner's own content check expression): a missing task and a misassignment FAIL, a correct and a multi-line version pass; exit 0. On `d5cff3d2` the script stops at the first check because the old contract has no tasks.

### Round 4 (diff `d5cff3d2..5c414d6f` reviewed)

**P2, keyword scoring still reported a pass for wrong content.** Following the review's recommendation, chose **option 1**: remove content scoring from the acceptance checks; keep it as a supporting indicator; if the technical checks pass it is `pending_content_review`; save the deliverable intact with its hash so the reviewer can decide. No more keywords were added. The indicator was made more cautious: it does not merge items under headings (the case of borrowing another task's deadline is no longer `met`); a name that appears only in a unit mentioning several people is `unverified`, not "person not found"; if there is the right task but the date is nobody's deadline it is `not_met`.

Tests (`test_resonance_e2e_guard.py`, 56 checks): added the case of borrowing a deadline under a heading, a multi-person sentence, name not found, a strange date, the indicator describing itself as only an indicator, intact saving (hash matches) and a case with no file. The expectation script `PR-579-e2e-round5-expected-checks.py`: the runner no longer has a content check for acceptance and requires intact saving; `acceptance` depends only on the technical side (`rep`, `_fails`, `MODE`); for the reviewer's four wrong-meaning cases the indicator still says `met` but the conclusion is to wait for the reviewer; borrowing a deadline and the multi-person sentence are no longer `met`; a deliverable over 4,000 characters is saved in full. Exit 0; on `5c414d6f` it is red.

Answers to the three questions of review round 1: **keep the current routing rules** and change the scenario to the maintain type, accepted by the goal's kind (maintain: met, `goal.maintained`, review schedule, then pause); the ceiling now covers every path by which Resonance calls the engine on the same store with the same variable in every process, but it is not a ceiling on internal SDK requests; environment filtering is not enough by itself, so there is an authentication gate and a settings review.

## Run 1 (7 Oct 2026): the brain did not form a goal

**The pilot stopped exactly on the approved condition, with no retry and no rewording of the task.** This was a single attempt that stopped at the routing step, not a successful end-to-end loop.

| Item | Value |
|---|---|
| Commit | `c0ab3d66`, `server/` and `system/` trees clean |
| Approver | The user approved one run, at most 3 turns, with the existing engine and subscription plan |
| Main engine | `anthropic-cli` / `claude-opus-5-5`. **The authentication method actually used was NOT independently verified this time** (there was no `auth status` gate or settings review yet). The server environment had filtered the `CLAUDE*`, `ANTHROPIC*` variables and provider keys, but as the review pointed out, that by itself does not prove subscription-only use |
| Ceiling | 3 total; 1 brain turn counted before sending; background work blocked before the call with `JAVIS_RESONANCE_CALL_CEILING=2` |
| Turns used | **1 host-level engine turn** (the brain turn; the number of internal requests cannot be measured), 0 background work turns |
| Duration | Chat turn 29.9 seconds; total 38.1 seconds |
| Evidence | [`resonance-mvp-e2e-pilot.json`](resonance-mvp-e2e-pilot.json): tool names and frame types; no Kanban task content or answer (the runner did not save them back then, it does now). The content described below was read from the sandbox before deletion and was not saved as independently verifiable evidence |

**What the brain did:** called `ToolSearch` and then `javis_task`, creating one Kanban task (status `triage`) to build the note `Inbox/viec-tu-bien-ban.md`, did not touch `Notes/ghi-chu-cu.md`, did not overwrite. The answer was accurate: the task had entered the queue but was not running because the background work orchestration mode was off. No goal, no file went into the brain, no other call.

**Assessment:** that choice matches the current rules (both CLAUDE.md and the `javis_goal` description send an approved one-off background job to Kanban); the run 1 scenario picked the wrong kind of request. The run neither proves nor refutes whether the brain calls `javis_goal` at the right moment. It is not known whether the brain saw `javis_goal` in `ToolSearch` (the tool results were not saved then).

**The first MVP condition is still NOT met.**

## Run 2 (7 Oct 2026): the brain did the work within the turn and formed no goal

**The pilot stopped exactly on the approved condition, with no retry and no rewording of the task.** The conclusion of the run: `acceptance: stopped`.

| Item | Value |
|---|---|
| Commit | `9e4f842a` (passed e2e review round 5), `server/` and `system/` trees clean |
| Approver | The user approved one run per the proposal: 1 Opus turn + at most 2 Sonnet turns, the task wording, contract and engine configuration as above |
| Safety gate | Passed: the engine resolved `anthropic-cli` / `claude-opus-5-5` and `anthropic-cli` / `sonnet`, matching the approved configuration; `auth status` in both cwds is `claude.ai` / `firstParty` / `max`; no managed source; `enabledPlugins` recorded as out of scope |
| Server | One server (A, tick paused, background ceiling 2, binary pinned); stopped before reaching the kill and rebuild step |
| Turns used | **1 host-level engine turn** (the brain turn), 0 background work turns |
| Duration | Total 41.1 seconds |
| Evidence | [`resonance-mvp-e2e-pilot-2.json`](resonance-mvp-e2e-pilot-2.json): the gate, tool frames, final answer, Kanban task (none), server state |

**What the brain did** (tool frames in the report): `Bash` to look at the `Inbox` and `Notes` directories; `Write` to create `Inbox/viec-dang-do.md`; `Bash` to read the memory index; `Write` of a memory `memory/facts/duy-tri-viec-dang-do.md`; `Edit` of `memory/MEMORY.md`. **It did not call `ToolSearch` or `javis_search_tools`**, so at no point did it see `javis_goal`. The final answer had a table with all three tasks, people and deadlines (Lan 09/10, Minh 10/10, Hà 12/10, with the year 2026), said it did not touch `Notes/ghi-chu-cu.md`, and stated plainly that the file is only updated when the user sends a message, "no automatic background tracking" (the original wording was Vietnamese: "không tự theo dõi ở nền").

**Assessment:**
1. The prompt of a brain with Resonance turned on DOES have the routing line (main.py: "maintain, track, wait for an event, work until it is met then call the tool javis_goal op=create ... If you do not see the tool, find it with javis_search_tools"). The brain did not follow that line; `javis_goal` is a tool you must search for to see, and the brain did not search.
2. But on a careful reading, the run 2 task also did not truly need anything done after the turn: "when I report more tasks, update it" is a reaction to a new message, with no state changing in the background between two messages. The brain finished immediately within the turn and stated its own limit accurately. As in run 1, this run neither proves nor refutes whether the brain uses `javis_goal` when a task TRULY needs pursuing after the turn.
3. The two runs show a design difficulty, not just a scenario problem: with a text-only background executor that cannot read data, it is very hard to build a natural request that both needs work after the turn and can be done with the Resonance MVP, yet belongs neither to Kanban (one-off background work) nor to `javis_schedule` (a fixed time).

**The first MVP condition is still NOT met. No further runs.** The next direction needs the user's decision (see the report sent to the user).

## After run 2: fixing the boundary and checking the tool path (no model call)

Done following the assessment `PR-579-pilot-2-assessment.md`: no further run, and the task wording was not changed to force the brain to form a goal. Every check in this part runs with code and a fake brain.

### Routing boundary (the review agrees in principle)

| Kind | When | Path | Example |
|---|---|---|---|
| Do it now | Finish and return the result within the turn | Answer, may write a file | "Summarize this note into three points"; "Build a task table from the message below, save it to Inbox" |
| One-off background work | Runs once in the background, responsibility ends when done | `javis_task` (Kanban) | "Translate all 40 files in this folder, tell me when done" |
| Pursue a result | Keep responsibility across several rounds of work, self-check, revise on feedback; keep the job open until it is met. While waiting for feedback, no model call | `javis_goal` (Resonance) | "Take care of this guide until you find it usable, I will give feedback bit by bit" |
| Fixed-time reminder | A plain reminder notification at a point in time (not every task with a deadline) | `javis_schedule` | "At 8 tomorrow morning remind me to call the supplier" |

Two more cases that create nothing new: **attaching to an open goal** (only feedback that changes the open goal is attached to it with `javis_goal op=update`; "thanks" or an aside question is not) and **plain chat** (questions, advice, planning: just answer).

The distinguishing point is the responsibility to keep pursuing a result, not the number of model calls or the word "maintain". The run 2 task ("when I report more tasks, update it") sits in the overlap: each update is a reaction to a new message, and doing it immediately within that turn is still reasonable. Conversely, writing the first draft right within the turn does NOT negate Resonance: the brain can do the useful part immediately and still store the responsibility in a goal.

### Result of checking the tool path on the Claude Code engine

The script `exports/reviews/PR-579-tool-path-probe.py` (outside the repo), later turned into the test `tests/python/test_resonance_tool_path.py`:

1. **Correct brain registration: passed.** `javis_goal` appears in `plugins_host.plugin_tools` only when the brain has Resonance turned on; with the brain off or the brain unknown it is absent. `javis_task` is always present.
2. **The list reaching the engine: passed.** The Claude engine receives plugins through the in-process MCP `javis-plugins` (32 tools, including `javis_goal`). The chat path sets `javis_vault` in `main._apply_mcp`; without it `javis_goal` is not present.
3. **The search path: wrong on Claude Code.** When the Claude engine manages to build the in-process plugin server, it tells the hub to drop the plugin group (`X-Javis-No-Plugins: 1`) to avoid duplicate tools, so the hub's `javis_search_tools` does not return `javis_goal`. The conclusion applies only to that path; the fallback branch when the in-process server fails (the hub keeps the plugin group) is not checked here. With API engines or Codex, the hub has the plugin group so `javis_search_tools` finds it. The old hint line mentioned only `javis_search_tools`.
4. **Source of the user message: passed.** `luot_dang_chay` (the running turn) returns the right session, message id and user words of the running turn; once the turn ends, they are gone.

**Not checkable without calling a model:** whether the SDK's ToolSearch is always available, and whether Claude Code defers loading `mcp__javis-plugins__*` tools. The only indirect evidence is run 1 (the brain found `mcp__javis-plugins__javis_task` through ToolSearch). The fault in item 3 is real, but **it is not proven to be the cause** of run 2.

### Minimal fix

- `server/main.py` (the hint line, only when the brain has Resonance on): states all four kinds per the table above and points to the search path for each engine: Claude Code uses ToolSearch (`mcp__javis-plugins__javis_goal`), other engines use `javis_search_tools`. The comment records the evidence level accurately (deferred loading is unverified). The test's length ceiling for the hint line was raised from 450 to 650 characters.
- `system/plugins/javis-goal/plugin.py`: added "self-check, revise on feedback, keep the job open until it is met" to the conditions for forming a goal; stated plainly "one-off background work, responsibility ends when done: javis_task". This description reaches the engine only when the brain has it on.
- **The `javis_task` description is unchanged** (tool path review, P2). Version `9c62b9a0` once added a boundary sentence there, and that sentence reached even brains without Resonance on; it was removed. The boundary now lives only in two places that exist only when it is on.

`test_resonance_tool_path.py` (20 checks) reads the tool description that **actually reaches the Claude engine** (the in-process server's metadata) with the brain on and off. The `javis_task` description must be identical and must not mention `javis_goal`; putting the old sentence back turns it red. No keyword aimed at the pilot's task wording was added. There is no evidence that this fix is enough for the brain to form a goal.

**Two real conditions of `op=update`** (found while writing the fake-engine test): the proposal must carry a `relevant_quote` quoting the FEEDBACK words verbatim, and it must change at least one field (a constraint, a criterion, or the interpretation). Without the quote the host rejects it; with no change the host returns "no change was applied", writes no new intent, and the background work does not run again.

### Run 3 (NOT yet run, waiting for review of the runner and then the user's approval)

**Scenario: finish a guide through feedback** (an `achieve` goal, text deliverable). Separate runner: `tests/python/test_resonance_mvp_e2e_achieve.py` (variable `JAVIS_RESONANCE_E2E_ACHIEVE=dry|real`, port 7792). The old maintain runner is kept as the record of runs 1 and 2.

**Frozen input** (verbatim in the runner, the report records the sha256): the task consists of the request, the path `Docs/huong-dan-nhan-hang.md`, three instructions (for someone who has never done it, numbered steps, a "Lỗi hay gặp" section, i.e. "Common mistakes") and six note lines (count the packages before letting the driver leave; check every line of the delivery slip against item code and quantity; set dented, wet or torn boxes aside and record the damaged goods; sign only after counting and checking, write any shortage or damage next to the signature; enter it in the warehouse ledger the same day; if unsure, call Tùng). The wording is Vietnamese in the runner. The feedback message (also Vietnamese in the runner): "Anh xem bản đầu rồi. Bước đối chiếu phiếu giao khó hiểu quá, em thêm một ví dụ cụ thể, và thêm bước chụp ảnh hàng hỏng trước khi ký." Gloss: "I have looked at the first draft. The step of checking the delivery slip is too hard to understand, add a concrete example, and add a step of photographing damaged goods before signing." No tool name, API or schema appears in the user's words.

**Steps and limits split by stage** (at most 4 host-level engine turns):

| Step | Server | Turn | Passes when | Stops when |
|---|---|---|---|---|
| S0 | A: stage 1, tick paused | 0 | The authentication gate passes | The gate fails |
| S1 chat turn 1 | A | chat 1/2 | Exactly one `achieve` goal, file `Docs/huong-dan-nhan-hang.md`, with a user-confirmation criterion; original intent matches the task wording | No goal formed or two goals formed, handed to Kanban: `stopped`. Deviating kind, file or criterion: `contract_failed` |
| S2 first draft | B: stage 1, tick running | background 1/1 | Receipt has the right provider; file matches the posting hash; saved intact; waiting for the user; notification to the session with a receipt | Technical error |
| S3 rebuild | C: stage 1, tick running, then D: tick paused | 0 | Goal and revision unchanged; no repeated notification; 75 seconds with no further call | State lost |
| S4 chat turn 2 | D | chat 2/2 | Same session; same goal, revision +1; the new intent matches the feedback words and chains to the previous intent; keeps the old constraints, file and confirmation criterion; the redo schedule is not yet picked up | A new goal, Kanban, or an unchanged revision: `stopped` |
| S5 revised draft | E: stage 2, tick running | background 2/2 | Exactly one turn for the new revision; hash differs from the first draft and matches the posted version; saved intact; waiting for the user; 75 seconds with no further call | Technical error |
| S6 confirmation | E | 0 | Click "Meets the bar" (the "Đạt yêu cầu" button) for **each** user criterion of the current revision, on exactly the `artifact_ref`; the goal is `succeeded` and has been notified | |

- **Chat turns:** the `TurnLedger` ledger reserves BEFORE each send and writes to disk immediately. A turn that times out or errors still counts, there is no retry path, at most 2.
- **Background work:** a CUMULATIVE ceiling of 1 for every server through the end of S4, 2 for server E. The ledger in SQLite is never reset. The feedback chat turn runs on a tick-paused server, so the redo schedule is only picked up when E comes up. If the tick ran with a ceiling of 1 after the feedback, that schedule would be blocked by the limit and the runner may not edit the store to unblock it.
- No retry, no raising the ceiling, no switching to a paid API. The javis_goal tool forms a goal without calling a model (framer `CallBudget(0)`); the M5 approach trial has no call path in the product.

**The conclusion of the run** separates four kinds: `technical_failed` (host or runner), `contract_failed` (took the goal path but deviated from the scenario), `stopped` (the brain did not take the goal path at S1 or S4), `pending_content_review` (technical checks passed).

**Content acceptance is still the reviewer's** (keeping the round 5 process). A different hash only proves different bytes. The runner saves the first draft and the revised draft intact together with the hash, revision and the sha of the feedback words, with a list of things to check:
- **first draft:** written for someone who has never done it, numbered steps, has a "Lỗi hay gặp" (Common mistakes) section, covers all six points of the notes;
- **revised draft:** the checking step has a concrete example, there is a step of photographing damaged goods placed before the signing step, and it still keeps every requirement of the first draft.

The "Đạt yêu cầu" (Meets the bar) button at S6 is a **simulated** action (`simulated_acceptance: true`), checking only the API path, not a human having approved.

**Additional evidence recorded:**
- every tool frame, with the frames involving ToolSearch or `javis_search_tools` (`search_calls`) and the frames involving `javis_goal` or `javis_task` listed separately;
- the files the brain wrote in each chat turn (snapshots before and after);
- the deliverable files saved after S1 and S4, even when stopping early.

The tool list in Claude Code's `init` message cannot be read from outside without changing product code; the report records `not_observable`.

**Checked without calling a model:**
- the runner's `dry`: 24/24 checks, `dry_ok`.
  - Forming a goal with the tool's own function.
  - Five servers: four with ceiling 1, the last with ceiling 2.
  - Feedback chained through `revise_goal` as `op=update` does, revision 1 to 2, intent chained as a string.
  - The revision 2 revised draft is blocked before the model call (a text-only provider cannot run).
  - The pause command through the API still takes effect. 0 engine turns.
- `test_resonance_achieve_stages.py` (20 checks, fake engine):
  - Ceiling 1: if the first draft is not accepted, the redo is blocked before the call, even after rebuilding the store.
  - While waiting for the user, waking up again does not call a model.
  - Valid feedback and then ceiling 2: exactly one more turn, the prompt has the feedback and the previous draft; the third turn cannot reserve.
  - The chat turn ledger counts a timed-out turn, does not hold the same turn, and can be re-read after a rebuild.
- `test_resonance_e2e_guard.py`: added the brain snapshot and the tool-search frame filter.

**Known risks:**
- The brain may write the first draft right within the turn without forming a goal: `stopped`, which is not an error by default.
- `op=update` missing the quote or changing no field: S4 stops and says so plainly; the runner does not add fields itself to fake a fix.
- The hint line defining kind 3 is fairly close to the task wording, so one pass only proves this path works when the boundary is stated clearly, not that routing is stable.

**Fixes following the review of the achieve runner (diff `9c62b9a0..ff9f97bf`):**
- **P2-1, a failed check still granted the next turn:** the cost gate now sits INSIDE the three operations that can lead to a model call: building a server, sending a chat message, clicking confirm (`tests/python/_e2e_achieve_harness.py`). If any check fails, technical or contract, all three refuse. The runner script goes through the harness for all three.
- **P2-2, an old notification was counted for the revised draft:** the notifications of S2, S5, S6 must match an outbox row of exactly the right goal, the right kind (`goal.waiting_human`, `goal.succeeded`) and the right revision. An `outbox:<id>` message with the host's receipt must be in the task giver's session. The `delivered` flag is no longer enough.
- **Negative cases** (`test_resonance_e2e_achieve_harness.py`, 31 checks):
  - S4 with the wrong feedback source, a lost constraint, a missing schedule: stage 2 is not built.
  - A failed check before S4: no message sent, no reservation.
  - A failed chat turn: counted in the ledger, no retry.
  - S5 failed: no confirm click.
  - Notifications: only an old message, only a reframe card, an empty session, not sent, the wrong session, a missing receipt, a different goal, not yet delivered, S6 with only the delivered flag.
  - Source review: the script no longer has a path that builds a server, sends chat or clicks confirm around the gate.
- **`dry` on the clean commit `64ad9eba`:** 23/23 checks, `dry_ok`, 0 engine turns.

## Run 3 (7 Oct 2026): the brain formed a goal by itself, stopped at S2 because of a file-posting conflict

**Conclusion: `technical_failed` at S2. No retry, no further run.** The user approved exactly one run on `1c76ce6f` (clean tree), at most 2 Opus and 2 Sonnet.

| Item | Value |
|---|---|
| Gate | Passed: engine `anthropic-cli` / `claude-opus-5-5` (chat) and `sonnet` (background work), Max plan in both cwds |
| Turns used | 2 of 4: one Opus chat turn (S1), one Sonnet background turn (S2). When server 2 stopped, the cost gate blocked the third server |
| Duration | 122.6 seconds |
| Evidence | [`resonance-mvp-e2e-pilot-3.json`](resonance-mvp-e2e-pilot-3.json), the version the brain wrote [`resonance-mvp-e2e-pilot-3-s1-chat.md`](resonance-mvp-e2e-pilot-3-s1-chat.md) (`draft1` and `final` are the same file, same hash `c30c9443...`) |

**S1 passed: for the first time the brain routed itself to a goal.**
- Tool order: `Write` (wrote the first draft straight into `Docs/huong-dan-nhan-hang.md`), `ToolSearch` with `select:mcp__javis-plugins__javis_goal`, then two `javis_goal` calls in the SAME chat turn: the first time the host rejected it because the review horizon lacked a readable `at_iso`, the brain fixed the proposal and the second time a goal was formed (the result is in the JSON's `tool_frames`; the earlier note saying the trace had no result was WRONG, as the run 3 pilot review pointed out). The trace has no content for the ToolSearch result.
- The goal matched the contract:
  - `achieve`, the right file;
  - criterion `c1` self-check (has "Lỗi hay gặp" (Common mistakes), "1.", "anh Tùng", at least 800 characters), criterion `c2` user confirmation;
  - four constraints exactly as instructed; an internal review deadline of one week, stating plainly that the user gave no deadline.
- The goal card reached the right session with a receipt. Not handed to Kanban.
- The answer said plainly that the job was recorded to be followed until the user confirms.

**S2 failed: the brain had already written the first draft, and the host had no path to accept that draft.**
- Background work still ran one Sonnet turn: receipt succeeded, output hash `bebd0547...`.
- When posting, the host saw the file already existed and was not written by the goal, so it did not overwrite. The host recorded `goal.publish_conflict` and kept the Sonnet version in the work area (which is lost when the sandbox is cleaned up).
- The assessment afterwards scored `c1` on the brain's file (passed), then waited for user confirmation. The confirmation card therefore points at the version the brain wrote, not the one the host just produced.
- The `goal.waiting_human` message reached the right session with a receipt. There was no posting, so the check "bytes match the hash the host recorded at posting" failed correctly. The cost gate blocked every later step.

**Assessment (pending review):**
1. **Routing works on the Claude Code engine** after the hint line pointed correctly at ToolSearch: the brain called exactly `select:mcp__javis-plugins__javis_goal`. One sample, stability not proven.
2. **A real hole in the product was exposed**, exactly the case the review foresaw ("do the useful part immediately and still store the responsibility in a goal"). When the brain writes the first draft within the turn and then forms a goal:
   - the host still spends a background work turn redoing the first draft;
   - that draft cannot be posted because of the conflict;
   - the notification states the wrong origin ("the file was edited after Jarvis 007's previous write", when Jarvis 007 never wrote it).
   The direction of the fix needs review before it is built, for example: when forming the goal, the host takes the file the brain just wrote in that very turn as the first draft (with a hash, the right session, the file of the criterion) and does not queue a background work turn until there is feedback.
3. **The Sonnet version was lost** because the work area lives in the sandbox. The runner should also save the background work output when it cannot be posted.
4. ~~The trace lacks the result of the tool frame~~ (wrong, see above): `javis_goal` was called twice because the first time lacked `at_iso`.

Two conclusions separated (run 3 pilot review): **routing by itself from chat PASSES for one sample** (S1: it found and called the goal tool by itself, exactly one achieve goal, no Kanban). **The end-to-end loop is NOT yet passed** (stopped at S2), so the complete first MVP condition is still not met.

## Run 4 (8 Oct 2026): the chat turn failed because of a login token refresh, routing could not be measured

**Conclusion: the run is NOT valid for assessment.** The runner recorded `stopped` (the brain formed 0 goals), but that is the WRONG classification: the brain never ran.

| Item | Value |
|---|---|
| Commit | `1aa20e5b` (passed review round 3), clean tree |
| Gate | Passed: the engine matches the approved configuration, `auth status` is `claude.ai` / `firstParty` / `max` in both cwds |
| Turns counted | 1 chat turn (per the ledger, counted before sending), 0 background work turns. The chat turn failed at the token refresh step, most likely no request reached the model |
| Duration | Total 21.5 seconds; chat turn 10.1 seconds |
| Evidence | [`resonance-mvp-e2e-pilot-4.json`](resonance-mvp-e2e-pilot-4.json) |

**What happened:**
- The chat turn's answer was only Claude Code's error message, repeated twice: "Failed to refresh OAuth token: another Claude Code process is refreshing it or exited mid-refresh. This is usually transient; retry in a minute...".
- The trace has no tool. WebSocket frames: `response`, `status`, `stream`, `turn_done`, no `error` frame.
- The brain wrote no deliverable file (only the conversation log).
- The `auth status` gate passed at first, because it only reads the login state. The access token expired and had to be refreshed exactly when the message was sent; at that moment another Claude Code process on the machine (the session driving the pilot is also Claude Code) was holding the refresh turn.

**Holes in the runner:**
- The check "S1 chat turn ended (turn_done)" passed even though the answer was an engine error.
- The S1 stop branch attributed it to a routing result (`stopped`) instead of a technical error.
- To fix before the next run:
  - a chat turn whose answer is an engine or authentication error (no model content, no tool) must come out as `technical_failed` with a clear reason;
  - that turn must not be counted as "the brain formed no goal".

**No retry** under the approval rule. A new run needs the user's separate approval.

### Fixes after run 4 (following `PR-579-pilot4-next-steps.md`, no model call yet)

**A structured engine status, sent along with `turn_done`.** `turn_done` only says the turn has ended. Run 4 had no `error` frame: the error sentence came out like a normal answer. So neither the `error` frame nor text scanning is relied on.
- **SDK mapper** (`claude_sdk_engine.map_message`): `final` carries `is_error`, `subtype`, and the flag `auth_refresh_race`. The flag comes from the narrow recognizer `claude_token_gate.la_loi_tranh_lam_moi`, which now additionally recognizes EXACTLY the opening phrase "Failed to refresh OAuth token: another Claude Code process is refreshing". A sentence with just the word OAuth or refresh is not recognized.
- **`main.py`:** `_engine_outcome_*` records the engine outcome per session.
  - `final` is an error or carries the token race flag: `error`.
  - There is an `error` frame (except a lost stream that was re-primed): `error`.
  - Exception: `error`.
  - No `final` (timed out, cancelled, an engine branch that did not report): `unknown`.
  - `run_turn` sends `turn_done` together with `engine_status` and `engine_error`.
  - The dashboard ignores unknown fields, so the interface does not change.
- **What the user sees change:** the new token race sentence is now replaced with the sentence "the session is not lost, send again and it continues", as with the old sentence, instead of showing the English text as is.

**Runner:**
- `H.chat_turn` counts a turn as having run only when `engine_status == "ok"`.
  - An error, an unknown outcome, or a missing field: record a TECHNICAL error, close the gate, do not send again, do not assess routing.
  - The turn still counts in the ledger with the label `engine_*`.
  - The failed turn's trace still goes into the report.
- Only a successful engine turn that formed no goal comes out as `stopped`.
- Right before each message send, `token_ready` checks the token has at least 600 seconds left. The function only reads `expiresAt` through `claude_token_gate.han_token`. If there is not enough time left or it cannot be read, stop at the gate without reserving. This reduces risk and does not guarantee the conflict is gone.

**Tests:**
- `test_turn_engine_status.py` (18 checks):
  - the narrow recognizer;
  - the real SDK mapper with a login-error `ResultMessage`, with and without `is_error`;
  - engine outcome: an error with text, an `error` frame, a lost stream that was re-primed, an exception, no `final`, a success control;
  - the wiring in `run_turn` and the Claude branch.
- `test_resonance_e2e_achieve_harness.py`:
  - the three failure cases of run 4: an error with text and then `turn_done`, an unknown outcome, a missing field. Each stops at the gate, records a technical error, counts the turn, keeps the trace, and opens no later stage;
  - an `ok` control;
  - source review: the token check sits before `H.chat_turn`.

**Running the pilot afterwards:**
- Stop the Claude Code sessions that share the login so they do not call a model during the pilot window, and run the runner from an independent terminal.
- The run 4 ledger keeps the 1 chat turn already sent. The new run asks for a new ceiling of at most 4 additional turns (2 Opus and 2 Sonnet).
- If the login error repeats even when run on its own: stop to investigate the authentication path, do not continue.

### Fixes following the review of the post-run-4 fix (`e099b81a`, 2 P2)

**P2-1, a successful answer was reported as a login error.** The `auth_refresh_race` flag used to look for a substring in every result. Now the flag is set only in two cases:
- the CLI sets `is_error` AND the sentence is a token race error (`la_loi_tranh_lam_moi`);
- the whole result STARTS with Claude Code's raw error message (`la_loi_tho_tranh_lam_moi`, anchored at the start).

Outcome:
- An ordinary sentence with the words "already used", or a sentence that explains or quotes an OAuth error, comes out as `ok`.
- Run 4's raw error is still blocked when `is_error` is missing.
- The path that replaces the sentence for the user (`dua_token`) shares this narrow flag. Before, a successful answer containing the words "already used", while the machine was still logged in, was replaced with an error message; that case is now left as is.
- Tightening the pattern is not perfect evidence about the origin of the text; the main signal is still `is_error`.

**P2-2, a turn cancelled after `final` was still let through.** `turn_done` now also carries the host turn's `turn_status`: `completed`, `cancelled` or `failed`.
- The `CancelledError` branch of `run_turn` records `cancelled`. An exception records `failed`.
- These two states win over an earlier `final`.
- `engine_status` still tells the truth about the engine: cancelled after `final` means the engine is `ok` but the turn is `cancelled`.
- The runner requires both `engine_status == "ok"` AND `turn_status == "completed"`.

**Tests:**
- `test_turn_engine_status.py`:
  - P2-1 on the real SDK mapper, including when the machine is still logged in (`con_dang_nhap`, a fake, is True): an ordinary sentence with "already used", a sentence explaining and quoting an OAuth error, a sentence opening with a heading, run 4's raw error, the old error with `is_error`, the old sentence where the CLI reports success;
  - P2-2 runs the REAL BODY of `run_turn` (extracted from main.py) with fake services: cancelled after `final`, cancelled before `final`, an exception after `final`, a completed control; each result goes through the real `H.chat_turn`.
- `test_resonance_e2e_achieve_harness.py`: added the case `ok` but `cancelled`, and `ok` but missing `turn_status`.
- Mutations:
  - dropping the cancel recording in `run_turn`: 4 checks red;
  - dropping the `is_error` condition of the "already used" branch: 2 checks red.
- The script `PR-579-pilot4-fix-checks.py` stops at the first REPRO ("ordinary healthy SDK result misclassified as auth failure"), because the bug is gone.

## Run 5 (8 Oct 2026): went through the whole loop, technically passed, waiting for content approval

**Conclusion: `pending_content_review`.** Every technical check passed. This is NOT yet pilot acceptance: the content of the two drafts waits for the reviewer to decide. The click of "Meets the bar" (the "Đạt yêu cầu" button) at S6 is simulated through the API.

| Item | Value |
|---|---|
| Commit | `0b6a4542` (reviewed), clean tree, CI 4/4 green before the run |
| Gate | Passed: engine `claude-opus-5-5` / `sonnet` as approved, Max plan in both cwds; token had 25456 seconds left (S1) and 25286 seconds (S4) |
| Turns used | **2 Opus turns** (S1, S4; both `engine_status=ok`, `turn_status=completed`), **0 Sonnet turns**. Ceiling this time: 2 Opus + 2 additional Sonnet (run 4 keeps the 1 chat turn already counted) |
| Duration | 356.4 seconds |
| Evidence | [`resonance-mvp-e2e-pilot-5.json`](resonance-mvp-e2e-pilot-5.json), [first draft](resonance-mvp-e2e-pilot-5-draft1.md) (`8045014b...`, revision 1), [revised draft](resonance-mvp-e2e-pilot-5-draft2.md) (`b160e8ff...`, revision 2). The two `-s1-chat` and `-s4-chat` files have the same bytes as the two drafts above |

**What happened:**
- **S1:**
  - Tools in order: `Glob`, `ToolSearch` (`select:mcp__javis-plugins__javis_goal`), `Write` of the first draft into `Docs/huong-dan-nhan-hang.md`, then `javis_goal` (formed on the first try).
  - An `achieve` goal with two criteria: `c1` self-check ("Lỗi hay gặp" (Common mistakes), "1.", anh Tùng, phiếu giao (delivery slip), sổ kho (warehouse ledger), at least 1500 characters) and `c2` user confirmation.
  - Four constraints exactly as instructed. An internal review mark of 15 Oct, stating plainly that it is not a deadline.
- **S2:** the host accepted the chat draft with a write receipt (Write succeeded, bytes match). The draft met the objective part so it did NOT call background work; the goal waits for the user; the notification went to the right session.
- **S3:** server rebuilt; the goal, revision and on-disk draft unchanged; no repeated notification, no further call.
- **S4:**
  - Feedback turn: `Write` of the revised draft, then `javis_goal op=update` on the same goal.
  - Revision went to 2. The new intent is exactly the feedback words, chained to the previous intent.
  - Added two constraints: a concrete example for the checking step, photographing damaged goods before signing.
- **S5:** the host accepted the revised draft for revision 2; no background work called; hash differs from the first draft; the notification of the revised draft went to the right session.
- **S6:** clicked "Meets the bar" for `c2` through the API (simulated); the goal is `succeeded`; the success notification reached the right session with a receipt.

**The implementer's preliminary content check (does NOT replace the reviewer):**
- **First draft:**
  - written for someone who has not done it, with key terms explained;
  - 7 numbered steps;
  - the "Lỗi hay gặp" (Common mistakes) section with 8 mistakes;
  - covers all six points of the notes.
- **Revised draft:**
  - the checking step has a 3-row table example (matching, 1 box short, wrong code) and a sentence to write next to the signature;
  - there is a step of photographing damaged goods (step 3), placed before the signing step (step 6);
  - keeps every requirement of the first draft, with "Lỗi hay gặp" and the summary updated.
- In its answer the brain itself named the places where it made its own decisions (moving the damaged-box check ahead of the checking step; adding "do not copy the numbers on the slip") and two things still unknown (where the photos are sent; how to handle a wrong code).
- No em dash characters.

**Limits:**
- One sample: stable routing is not proven.
- This time the brain wrote both drafts itself, so the path where background work revises the draft with a real model was NOT used; that path already has its own evidence in the M3 pilot and in the fake engine tests.
- The final confirmation is simulated.
- The first MVP condition is only closed after the reviewer approves the content of the two drafts.

## Run 5 content acceptance (post-review, 8 Oct 2026)

Review record: `exports/reviews/PR-579-pilot5-content-review.md` (outside git). The original JSON `resonance-mvp-e2e-pilot-5.json` keeps `acceptance: pending_content_review` exactly as at run time; this section is the post-review conclusion and does not overwrite history.

**Conclusion: content accepted.** The reviewer read both drafts, compared them against the task and feedback, and recomputed the hashes:

| Draft | File | SHA-256 | Revision | Result |
|---|---|---|---|---|
| First draft | `resonance-mvp-e2e-pilot-5-draft1.md` | `8045014ba3c29514a387b1deb36f4b4c100aa9dd53a509545f1b1554fedfd23d` | 1 | Passed 4/4 checklist items |
| Revised draft | `resonance-mvp-e2e-pilot-5-draft2.md` | `b160e8ffe7d25a39e1cca1c115cb088ea9f8d662bfe7abd292c0851e2e53d762` | 2 | Passed 3/3 checklist items |

- 29/29 evidence consistency checks passed; the 43 checks recorded in the pilot report are all correct.
- The reviewer did not call a model.
- The arithmetic of the example is correct: 10 + 5 + 8 = 23 on the slip, 22 counted, row 3 has the right quantity but the wrong code. The example states plainly that the figures are illustrative.

**Scope:**
- One real sample that went through the whole loop, not a statistic on routing stability.
- Both drafts were written by Opus in the chat turn and accepted by the host. 0 Sonnet turns means no pointless rewrite in this case, not evidence that the background work path revising the draft ran in run 5.
- The final confirmation is simulated through the API.
- The content passes for simulated data and the approved checklist, not as acceptance of a warehouse process in operation.

**Quality remarks beyond the checklist (non-blocking, evidence not modified):** a few sentences are too absolute ("Đã ký là coi như mình đồng ý đủ hàng" (once signed, it counts as us agreeing the goods are complete), "không ghi coi như không có" (if it is not written down, it counts as not existing), "Ảnh là bằng chứng ... không phải do kho làm hỏng" (the photo is evidence ... that the warehouse did not cause the damage)). When used as an operating document they should be written by their practical effect: signing before checking makes it hard to claim a shortage or damage afterwards; photos help record the condition at delivery. The two hashed files are left as they are.


## A1: the pilot moves to an assistant session (8 Oct 2026, PR #590)

From A1, Resonance (Cộng hưởng) is turned on per assistant only; the old brain switch no longer grants permission. The achieve runner (`tests/python/test_resonance_mvp_e2e_achieve.py`) changes accordingly:
- The temporary brain has one **temporary assistant** `tro-ly-tai-lieu` (a neutral role, no model of its own, so it runs on the approved main brain). The old brain switch is not turned on.
- **A new S0b stage, no model call:**
  - plain chat: `/goal-requests` 403;
  - assistant not yet turned on: 403;
  - the project owner turns it on through `POST /resonance/agents/toggle`: a code is granted, the assistant session is `ready`; re-reading `GET /resonance/agents` matches the store.
  - In real mode, additionally check that the assistant's engine can form a goal and accepts the chat draft.
  - In dry mode, `/goal-requests` on a turned-on assistant session gets through the gate, reaches the goal framer and stops at the blocked engine (400), with no model call. Real mode does NOT call this path, because the goal framer would call a model.
- **Chat turns S1, S4** are sent into exactly the `agent:<slug>` session. S1 additionally checks that the goal is attached to the session's own assistant.

**Differences from pilot 5, to remember when reading the results:**
- The assistant session prompt is `_agent_chat_prompt`: the assistant role, assistant memory, the tool block and the Resonance hint line. It does NOT have CLAUDE.md as plain chat did in pilot 5.
- The brain's routing may differ. The pilot result is not to be inferred back to plain chat.

**Dry (no model call):** `exports/reviews/A1-pilot-dry-report.json`, result `dry_ok`, 0 engine turns.

**Real run:** not yet run. It needs the project owner's separate approval of scope and limits. Do not reuse the limits of the old pilot.

## Run A1-1 (8 Oct 2026): assistant session, technically passed

This section records the state AT RUN TIME (`pending_content_review`). The content conclusion is in the post-review section right after.

- **Approval:** the project owner approved directly, exactly once, following the package `exports/reviews/A1-pilot-approval-request.md` (package review: `PR-590-A1-e01eb3c2-pilot-review.md`).
- **Commit:** `e01eb3c2`, `server_dirty: false`.
- **Engine:** chat with Claude Code 2.1.294 `claude-opus-5-5`; background work with Claude Code `sonnet`; subscription plan.
- **Gate S0:** passed. Source not assessed: `.claude/settings.json:enabledPlugins` (hooks, plugins, MCP are outside the gate's scope and outside the ceiling).
- **Record:** `docs/dev/resonance-a1-pilot-1.json`, two deliverable drafts `resonance-a1-pilot-1-draft1.md` and `-draft2.md`, snapshots after the chat turns `-s1-chat.md` and `-s4-chat.md` (same bytes as the two corresponding drafts).

**Result: `pending_content_review`, 0 failed checks, 379 seconds. Host-level engine turns: 2 Opus chat, 0 background work, total 2 of a ceiling of 4.**

- **S0b:**
  - plain chat `/goal-requests` 403; assistant not turned on 403;
  - turned on through the API: `ready`, version 1;
  - the assistant's engine can form a goal and accepts the chat draft.
- **S1** (session `agent:tro-ly-tai-lieu`, 60 seconds, `engine_status ok`, `turn_status completed`):
  - the brain listed the directory with `Bash` (read only), `Write` of the first draft;
  - then `ToolSearch select:mcp__javis-plugins__javis_goal` and called `javis_goal`.
  - Exactly one goal, attached to the session's own assistant, not handed to Kanban.
- **S2:** the first draft was accepted from chat exactly once, with no background work turn rewriting it. Waiting for the user. The notification reached the right session, with a receipt.
- **S3:** server rebuilt: state kept, no repeated notification, no further call.
- **S4** (48 seconds): `Write` of the revised draft then `javis_goal` (update), this time with no need for `ToolSearch`. Attached to the same goal, revision 1 to 2; the new intent is exactly the feedback words; old constraints kept.
- **S5:** the revised draft was accepted from chat, with no background work turn rewriting it. Posted, differs from the first draft, the notification reached the right session.
- **S6:** clicked "Meets the bar" through the API (simulated). The goal is `succeeded`, the success notification reached the right session.

| Draft | File | SHA-256 | Revision |
|---|---|---|---|
| First draft | `resonance-a1-pilot-1-draft1.md` | `629afff4280d2549b96eb0da046c054f189ed2777ffed30f6f95aefe5570641d` | 1 |
| Revised draft | `resonance-a1-pilot-1-draft2.md` | `38ab1df2e718c62a14945f9682c394992e30379c1e55736643f78a54766d84ee` | 2 |

**Limits:**
- One sample, not a statistic on routing stability.
- The brain wrote both drafts itself, so the path where background work revises the draft with a real model was not used this time. That path has evidence in the M3 pilot and in the fake engine tests.
- The final confirmation is simulated.
- Content not yet accepted: the reviewer reads the two drafts against the checklist (4 items for the first draft, 3 items for the revised draft) and then decides.

## A1-1 content acceptance (post-review, 8 Oct 2026)

- **Review record:** `exports/reviews/PR-590-A1-pilot1-e0a60352-content-review.md` (outside git).
- The original JSON `resonance-a1-pilot-1.json` keeps `acceptance: pending_content_review` exactly as at run time. This section is the post-review conclusion and does not overwrite history. The two deliverable files keep their bytes.

**Conclusion: content accepted.** First draft 4/4, revised draft 3/3 checklist items. No blocking errors.

| Draft | File | SHA-256 | Revision | Result |
|---|---|---|---|---|
| First draft | `resonance-a1-pilot-1-draft1.md` | `629afff4280d2549b96eb0da046c054f189ed2777ffed30f6f95aefe5570641d` | 1 | 4/4 |
| Revised draft | `resonance-a1-pilot-1-draft2.md` | `38ab1df2e718c62a14945f9682c394992e30379c1e55736643f78a54766d84ee` | 2 | 3/3 |

- The reviewer computed the hashes from the bytes and compared them with the git blobs; the hashes of the task and feedback match the JSON. 17/17 record consistency checks passed.
- Runtime `e01eb3c2`, record `e0a60352`; between the two commits there are only documentation and evidence files.

**Scope:**
- One successful routing scenario in a turned-on assistant session. Not a stable rate across every request or engine.
- 2 Opus chat turns, 0 Sonnet background turns. Both drafts were written by the chat turn and accepted by the host. This time the path where background work revises the draft with a real model was not measured.
- The final S6 confirmation is simulated through the API.
- The host does not inject CLAUDE.md into the assistant session prompt. The record does not check whether Claude Code finds and loads that file by itself.

**Two wording remarks, non-blocking, evidence files not patched:**
1. A few sentences state the consequence too absolutely ("không khiếu nại được" (cannot be disputed), "Coi như đã nhận đủ" (counts as having received everything)). They should be written by their practical effect: it is hard to prove the condition at delivery, and disputes arise easily.
2. The follow-on example in the revised draft adds "Hỏng 1 thùng mã A123 (ướt)" (1 box with code A123 damaged, wet), which the step 4 table does not mention. It should say "suppose there is also one wet box A123".

If a draft is needed for real use, create a separate edited copy; do not edit the frozen files.
