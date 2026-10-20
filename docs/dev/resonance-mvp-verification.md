# Jarvis 007 Resonance MVP verification

This report records what was actually run for each milestone of the [MVP plan](../superpowers/plans/2026-10-06-resonance-00-mvp.md). Each section separates the runs with a fake engine from the runs with a real engine. Anything that could not be verified is marked as not verified.

## M1: engine run path and host-observed receipt (2026-10-06)

### Code base and environment

| Item | Value |
|---|---|
| Base commit | `origin/main` = `7d264236b61e10077dc7833c1b063076023ea7bb` (0.83.2), fetched on 2026-10-06 |
| Branch, PR | `claude/resonance-mvp-m1`, PR #566 (draft), placeholder version 0.84.0 |
| Final pilot commit | `ba404185a0ef066b3a6d2922a5ebe5c38235a131` (clean, no uncommitted changes in `server/`) |
| Head when writing this report | `5162dfab`: the commit after the pilot only fixed the fake engine's temp directory in tests, and did not change the pilot run path |
| Machine | Windows 11 Pro 10.0.26200 |
| Python | 3.12.10, the `.venv` of the root checkout `D:\Project\Javis-OS` |
| Claude Code CLI | `~/.local/bin/claude`, signed in with a subscription plan |
| Background engine currently selected | `anthropic-cli`, model `sonnet` |
| Main brain | `anthropic-cli`, model `claude-opus-5-5` |
| OpenRouter key | present in the real settings (not copied into the pilot, see Limits) |

The root checkout `D:\Project\Javis-OS` is on the old branch `codex/restore-chat-colors`, 121 commits behind main. All the investigation below read the code on the M1 branch, which is main 0.83.2.

### Integration points probed on the real code

| Point | What the real code does | Used for M1? |
|---|---|---|
| `aux_engine.swap` | Below full level it builds a `_FallbackChain`: the selected engine, Claude, the main brain, OpenRouter free. Full level has no chain, but Codex runs with full permissions | Used at suggest level, then keeping only the first link |
| `aux_engine.strip_tools` | Strips the hub and MCP from API engines, Codex and Grok; drops Antigravity and unknown kinds, falling back to the original Claude engine. Does **not** remove the native tools of Codex and Grok | Used, together with a strict selector (see below) |
| `main._reply_policy_sandbox_engine` | Claude in an empty directory, `allowed_tools` deliberately matching no tool, empty MCP, extra native tools forbidden | Used, with an added `cwd_name` parameter to get a dedicated empty directory `resonance_cwd` |
| `claude_sdk_engine.map_message` | An error `ResultMessage` that still has text is turned into a normal `final`, losing the error flag | Fixed: `final` now also carries `is_error` and `subtype` (keys only added) |
| `main._workflow_agent_helpers`, `main._run_workflow_step` | The agent runs with `cwd` set to the brain and has tools, meant for workflows | Not used: grants wider permissions than a text-only turn needs |
| `agent_runtime.AgentRunner` | Only accepts when `agent_canary` is on and the slug is in the list | Not a live path: in the real settings `allocation_basis_points = 0` and `allowed_slugs = []`. Not enabled |
| `workflow_runtime.WorkflowCanary` | Same | Not a live path: `allocation_basis_points = 0`. Not enabled |
| `evidence_store.EvidenceStore.put` | Needs a `TurnTrace` from `context_runtime`, encrypts the artifact | Not wired up in M1, belongs to M3 |
| `self_improve`, `mcp_hub` | The loop builds Claude and then swaps; the tool hub | Not modified |

### Chosen path

- `resonance.GoalDeps.run_once(goal, prompt, action_id) -> ActionReceipt`.
- The engine is built by `main._resonance_engine`: a Claude engine in an empty directory, swapped according to the background engine at `suggest` level, then `strip_tools`, then `resonance.pick_text_only_link`.
- The selector only accepts the first link when both conditions hold: it is the provider the user selected, and it has a verified text-only mechanism. M1 has two mechanisms: Claude with the `can_use_tool` gate (`allowed_tools` has a value that matches no tool), and API engines with `no_tools`. Codex and Grok still have native tools, so they are blocked before any call. `text_only` is `true` only when the link is accepted.
- The model only produces text. The host writes the output into the goal's `output_root`, with the file named after `action_id`, then reads back the bytes it just wrote to compute the SHA-256.
- The receipt records: status, the engine that actually ran, output path and hash, usage, number of tool calls, error code. Any usage field the engine does not report is left absent; with no figures at all, `usage` is `None`.
- A `final` carrying `is_error` means the turn failed (`engine_result_error`), usage is kept, and no file is written.
- Output over 200,000 characters fails (`output_too_large`), with no silent truncation.
- Quota: a slot is reserved before the call. If the run stops before the model is called, the slot is returned.
- Re-running the same `action_id` is rejected with `action_exists` and the model is not called.
- Nothing outside tests calls `_resonance_engine` yet. Resonance is still off for users.

### Fixes from the PR #566 review

| Item | Bug | Fix | Test that proves it |
|---|---|---|---|
| P1-1 | A `ResultMessage(is_error=True)` with text went through `map_message` as a normal `final`, and the receipt recorded `succeeded` | `map_message` adds `is_error` and `subtype` to `final`; `run_once` treats that as `engine_result_error` | The SDK's real `ResultMessage` through the real `map_message`: the error turn is `failed`, no file, usage kept, counted as 1 turn; a `success` turn is still `succeeded` |
| P1-2 | The selector accepted Codex and Grok and declared `text_only=true` even though they still have native tools; with `JAVIS_CODEX_SANDBOX=off` Codex even dropped the sandbox | Only accept Claude with `allowed_tools` or an API engine with `no_tools`; block everything else before the call | Codex built with the real `aux_engine.swap` and `_build_codex` (both `auto` and `off`, confirming `sandbox is None` at `off`), Grok with the real `_build_grok`: all blocked, `text_only=false`, `run_once` costs no turn. Claude without `allowed_tools` is also blocked |
| P2-1 | Grok usage (`input_tokens`/`output_tokens`) came out as 0; a `final` with only `cost_usd` got fabricated tokens of 0 | Normalize key names per engine; missing fields stay absent | The real `GrokCLI._usage` gives 9028/54; a `final` with only cost gives exactly `{"cost_usd": 0.02}`; an empty `final` gives `None` |
| P2-2 | Output over 200,000 characters was silently truncated and still `succeeded` | Return `output_too_large`, write no file | 200,000 characters plus `IMPORTANT_TAIL`: `failed`, no file, usage kept |
| Report | The pilot only recorded that the hash "matches", and the pilot test did not recompute the hash itself | The pilot branch computes SHA-256 itself over the bytes read from disk and checks the output structure; it exports evidence with the prompt, output, hash, commit, and with personal paths removed | [`resonance-mvp-m1-pilot.json`](resonance-mvp-m1-pilot.json) |

During the fix, the new Grok test caused a bug of its own: `strip_tools` wrote `.grok/config.toml` into the engine's `cwd`, and the fake engine had `cwd=None`, so the file landed in the repo root and turned `test_ignore_files.py` red. That empty file (never tracked by git) was deleted and the fake engine was given a temp directory (commit `5162dfab`).

### Results with the fake engine

```
python tests/run.py resonance_mvp_integration -v
  [ 1/1] ok   test_resonance_mvp_integration.py
1/1 green
```

73 checks green, no model calls. TDD order: the tests went in first and were red because the module did not exist; the three quota reconciliation tests added later were red before the fix; the 11 tests from the review were red before the fix.

Groups checked:

- **Success:** the host writes the file, the SHA-256 matches the exact bytes on disk, the file uses LF, usage is taken from `final`.
- **Usage:** API engine, Grok, `final` with only cost, empty `final`.
- **Repeated `action_id`:** the model is called only once, no extra turn is spent.
- **Quota exhausted:** the engine is not built, the model is not called.
- **Failures that write no file:**
  - the engine returns an error;
  - Claude ends with an error but still has text (through the real `map_message`);
  - login lost but a `final` is returned;
  - token refresh race;
  - a tool call in a text-only turn;
  - empty output;
  - no `final`;
  - output too long;
  - engine not ready;
  - the factory reports blocked or throws;
  - timeout.
- **Quota reconciliation:** if the run stops before calling the model the slot is returned; if the model was called, one turn is counted.
- **Write area not granted and unknown `action_id`:** blocked before the engine is built.
- **Selector, run on the real `aux_engine.swap` and `strip_tools`:**
  - with an OpenRouter key, keeps exactly Claude and drops the later link;
  - with no chain, keeps Claude as is;
  - Antigravity falling back to Claude is blocked;
  - OpenRouter keeps the API link with tools turned off;
  - Codex (sandbox `auto` and `off`) and Grok, built with the real builders, are blocked;
  - Claude without `allowed_tools` is blocked.

The tests that share the SDK mapping and the background engine also ran green after the fix:

```
python tests/run.py sdk_engine claude_ket_thuc_luot aux_engine aux_fallback tao_file_tu_chat resonance
6/6 green in 21 seconds
```

### Real pilot results

The run command, with the two paths set for this machine:

```
JAVIS_RESONANCE_PILOT=1 JAVIS_RESONANCE_PILOT_SETTINGS=D:/Project/Javis-OS/server/settings.json JAVIS_RESONANCE_PILOT_CALLS=1 python tests/python/test_resonance_mvp_integration.py
```

- **Input:** a simulated task list explicitly marked as not real, asking for a Markdown note with the heading `# Việc đang dở` (Vietnamese for "Unfinished tasks", kept because it is the verbatim pilot prompt) and exactly three bullet points. The verbatim prompt is in the evidence file.
- **State:** `JAVIS_STATE_DIR` is a temp directory. The temp settings contain only the engine selection block (`auxiliary`, `main`, `engine`, `claude_model`), with no keys. Nothing is written to the real state.
- **Quota:** run three times, 3 model calls in total against the cap of 5 allowed. Each run used exactly 1 turn; the re-run with the same id did not call the model.

| | Run 1 | Run 2 | Run 3, code after review |
|---|---|---|---|
| Commit | `24611b4b` plus uncommitted `main.py` | `2404fc70` | `ba404185`, clean |
| Receipt status | `succeeded` | `succeeded` | `succeeded` |
| Engine that actually ran | `anthropic-cli` / `sonnet` / `ClaudeSDK` | same as run 1 | same as run 1, `text_only=true` |
| Tool calls observed | 0 | 0 | 0 |
| SHA-256 recomputed from bytes on disk | matches (checked by hand) | matches (checked by hand) | matches (checked by the test itself) |
| Matches the requested structure | yes (read by hand) | yes (read by hand) | yes (checked by the test itself) |
| Turn time | about 7.9 seconds | 5.96 seconds | 6.26 seconds |
| Tokens in / out (reported by Claude Code) | 17,893 / 421 | 17,888 / 197 | 17,893 / 240 |
| `cost_usd` (reported by Claude Code) | 0.0758 | 0.0203 | 0.0207 |
| Re-run with the same `action_id` | `action_exists`, model not called | same as run 1 | same as run 1 |

The evidence for run 3 is in [`resonance-mvp-m1-pilot.json`](resonance-mvp-m1-pilot.json): commit, prompt, receipt, the re-run, quota, the SHA-256 computed on disk, and the full output text. The file is written as escaped JSON (`\uXXXX`), because the model's output contains an em dash, which this repo does not allow to appear verbatim. Personal paths have been removed, only the output file name is kept. The output SHA-256 of run 3: `c690255823b0f391209f951ff5d4c06a3e097dff9303a09ca3ac2db578142ad3`.

**M1 conclusion:** on this machine there is one path that works. It is the background engine the user selected (Claude Code, sonnet), built through `aux_engine` in a text-only mode with a real tool-blocking mechanism, and it returns a receipt the host can observe. This is the result of one text-only turn on simulated data, and is not yet evidence for a full goal loop.

### Limits and what was not verified

1. **Only the real Claude engine was called.** The API engine has only been checked through the selector with a fake configuration. Codex and Grok are blocked on purpose until there is a text-only mechanism for their native tools.
2. **The pilot had no OpenRouter key.** In the pilot, swap did not build an OpenRouter link, so there was no link to drop. The case "if there is a fallback chain, keep only the first link" was only checked with the real `aux_engine.swap` and fake settings.
3. **The model's output contains an em dash.** In M1 the file only lives in a temp directory. From M3, when the host writes output into the user's brain, a criterion or a check step is needed for the em dash ban. The model's text must not be silently altered.
4. **`cost_usd` is not money charged.** It is the figure Claude Code reports itself, and on a subscription plan it is a converted amount. Most of the roughly 17,900 input tokens are Claude Code's default system prompt.
5. **Usage accumulation is only correct for accepted engines.** Claude emits one `final`, and an API engine with no tools emits one `usage` per round. An engine that emits a repeated running total (like Grok) must be handled separately before it is accepted.
6. **Duplicate-run protection still has a gap.** The current mechanism relies on the output file named by `action_id`. It does not prevent calling the model again when a previous turn failed before writing the file, and does not prevent duplicates across two processes. M3 replaces this with a lock and idempotency in SQLite.
7. **The `uncertain` status is not used yet.** A text-only turn has no outside effect.
8. **The receipt is not in EvidenceStore yet.** `evidence_ids` is currently empty. M3 wires this up.
9. **`requested_provider` is the spec after the budget brake.** If the owner turned on auto-brake and the monthly cap has been exceeded, `aux_engine.read_spec` may already have downgraded the engine before Resonance sees it.
10. **The pilot leaves transcripts behind.** Each pilot run opens a Claude Code session in a temp directory, and the Claude CLI stores that session's transcript in `~/.claude/projects` like any other session.
11. **Run 1 landed exactly in the window where the token was about to expire.** The token refresh queue gate (`claude_token_gate`) triggered, labeled it `di-truoc` ("go first"), and let this turn go ahead. The Claude CLI refreshes the token itself like a normal chat turn. There was no login error.
12. **No JS tests were run.** M1 changes no JS files.

### Full Python test run

Ran `python tests/run.py --py` on a clean main before the fixes, and on the final head of the M1 branch.

| | Clean main (`7d264236`) | M1 branch after review (`5162dfab`) |
|---|---|---|
| Green | 387/403 | 389/404 |
| Red files | 16 | 15 |
| New red vs main | | none |

The red files that already exist on clean main, unrelated to M1:

- `test_agy_prompt_dai.py`
- `test_antigravity_cli.py`
- `test_ba_loi_mac_va_telegram.py`
- `test_cai_windows.py`
- `test_grok_cli.py`
- `test_image_vision.py`
- `test_install_admin.py`
- `test_khoi_dong_nhe.py`
- `test_link_file_uri.py`
- `test_machine_translations.py`
- `test_memory_hoa_thuong.py`
- `test_model_theo_phien.py`
- `test_ollama_local.py`
- `test_terminal.py`
- `test_windows_no_console.py`

`test_project_khung.py` was red on clean main but green on the M1 branch in all three later runs. M1 does not touch the code this test checks, so this is most likely a flaky test rather than something M1 fixed.

One mid-way run (after commit `ba404185`) had `test_ignore_files.py` red. The cause was the `.grok/config.toml` file left in the repo root by M1's new Grok test, fixed in `5162dfab` as noted in the review fixes section. The run on the final head has no new red files.

## M2: routing and goal formation (2026-10-06)

### Base and branch

| Item | Value |
|---|---|
| Branch, PR | `claude/resonance-mvp-m2`, PR #567 (draft), stacked on #566; placeholder version 0.84.1 |
| PR base | `claude/resonance-mvp-m1` at `306e96cb` (the M1 head that passed review, CI green) |
| Base commit of the chain | `origin/main` = `7d264236` (0.83.2), unchanged when M2 started |
| Real model | No turn was called in M2. All verification used a fake engine or called the tool directly the way the engine would |

### Design decisions for the reviewer to check

1. **The brain decides on its own whether to form a goal, inside the chat turn, using the `javis_goal` tool.**
   - Spec section 4.0 asks to "reuse the existing conversation router" and to "not call an extra model for every message". Probing the 0.83.2 code showed there is no four-branch router yet.
   - The closest thing is how the brain already decides on its own to hand off background work with the `javis_task` tool (Kanban) and `javis_schedule` (reminders, loops). So `javis_goal` follows the same pattern: a bundled plugin, no extra model call, no keyword matching.
   - In exchange, the quality of the decision depends on the brain reading the tool description. The real pilot to measure this belongs to M3.
2. **The host checks the proposal against SMART** (`resonance.validate_proposal`):
   - **R:** `relevant_quote` must quote an exact passage from the user's words (matched ignoring case and whitespace). This is the barrier against goals the agent invents on its own.
   - **M:** at least one criterion uses an existing evaluator (`artifact_contract`, `human_confirmation`); unknown evaluators are dropped.
   - **T:** there is a horizon of `deadline`, `review`, `event` or `maintain`. A deadline is kept only when a sentence where the user stated the deadline can be quoted; otherwise it becomes an internal review point, `from_user=false`.
   - **S:** if no concrete result can be stated yet, the goal sits at `discovery` and is not rejected.
   - Targets with no quoted sentence in the user's words become assumptions. If the user already said they do not know, the question is dropped, the assumption is recorded, and the goal starts with discovery.
   - Constraints the user stated are always in the frame. The store rejects any revision that drops them.
3. **Branching after the turn is based on what the turn really did** (`resonance.route_request`, `route_after_turn`):
   - A `created` event for this exact message means `create_goal`; a `reframe` event means `continue_goal`.
   - A new Kanban task for this exact chat frame, created during the turn, means `task_now`. Otherwise it is `answer_now`.
   - Having an open goal is NOT enough to attach a new message to it. This is a bug the earlier review caught in the old appendix.
   - Tool names are not guessed from the event stream (names differ per engine, and lazy mode hides the real name behind `javis_run_tool`); the goal store and the Kanban store are read directly.
4. **The anti-duplicate key is the user message id in the session store.**
   - Before M2, this id was dropped right after `append_message`. Now `main.py` keeps it for both typed messages and voice messages (the `message_id` of the voice receipt), and passes it down to the running-turn ledger (`luot_dang_chay`) together with the user's words.
   - The tool runs through the hub, sometimes in another process, so it reads that ledger to know exactly which message it is. If unsure (two chat frames running on one brain, or a channel that does not pass a message id such as Telegram), the tool refuses and does not guess.
5. **The tool is visible only on brains that enabled it.**
   - `plugins_host.register_tool` takes an extra `visible_fn(vault_root)`; `plugin_tools` hides the tool when the function returns False. The existing `check_fn` only blocks at call time while the tool stays visible, which is not enough.
   - The switch is `<brain>/Javis/resonance.json` containing `{"enabled": true}`. Off by default, and a corrupt file counts as off. The on/off interface belongs to M4.
   - The capability index (the line in the system prompt and `Javis/index.md`) also lists only the tools visible to that brain; before the fix, the index read the manifest and still mentioned `javis_goal` on a brain that had not enabled it.
6. **The system prompt gets exactly one extra line hinting at `javis_goal`, only on enabled brains.** `CLAUDE.md` has exactly 1 character of budget left so it is not touched; a brain that has not enabled it gets no extra text.
7. **M2 only STORES the goal.** The tool result tells the brain that nothing is carried out or reported automatically yet, so it does not make empty promises (matching the `CLAUDE.md` rule against "promising to do it and report back").

### Changes

| File | Content |
|---|---|
| `server/resonance_store.py` (new) | `GoalStore` on `resonance.sqlite3`: tables `intents`, `goals`, `goal_revisions`, `goal_events`, `outbox`. Every operation goes through the `Principal` of the right brain. Create and revise write the event and the outbox in one `BEGIN IMMEDIATE` transaction. `revise` needs `expected_revision`, and keeps pause, budget and turns used. Only the user can change pause |
| `server/resonance.py` | `GoalRecord` gains the SMART frame and status (the six M1 fields are unchanged). `GoalRejected`, `RouteDecision`, `enabled_for`, `validate_proposal`, `route_request`, `route_after_turn`, `message_ref`, `framer_prompt`, `form_goal`. The engine-calling part of `run_once` is split out into `GoalDeps._ask`, shared with the goal framer; M1 behavior is unchanged |
| `system/plugins/javis-goal/` (new) | Tool `javis_goal`: `create`, `update`, `list` |
| `server/plugins_host.py` | `visible_fn` for plugin tools |
| `server/luot_dang_chay.py` | `bat_dau` accepts `msg_id`, `user_text`; adds `doan_luot`. The old call style still works |
| `server/main.py` | Keeps the user message id; passes it into `run_turn`; `_resonance_after_turn` writes the runtime event `resonance.route`; the system prompt hint line; the capability index filters out hidden tools |

### Results with the fake engine

```
python tests/run.py resonance -v
  test_resonance_mvp_core.py         58 checks
  test_resonance_mvp_integration.py  73 checks (M1, still green after splitting out _ask)
  test_resonance_mvp_main.py         15 checks
  test_resonance_mvp_wiring.py       29 checks
```

TDD: all three new files ran red before the code existed (`ModuleNotFoundError: No module named 'resonance_store'`, then `TypeError: bat_dau() got an unexpected keyword argument 'msg_id'`).

The eight tests named by the M2 plan, all present in `test_resonance_mvp_core.py` (the check labels carry the exact names):

| Plan test | What it checks |
|---|---|
| `test_chat_does_not_create_goal` | A turn that does not call the goal tool is `answer_now`, even when a goal is open |
| `test_inline_job_stays_inline` | Finished within the turn, with a file written, still `answer_now` |
| `test_followup_reuses_goal` | Adding detail to an open goal is `continue_goal` on that same goal |
| `test_persistent_request_creates_once` | The same message twice: one goal, one `created` event |
| `test_proposed_plan_does_not_schedule` | A basis sentence that is not in the user's words (an idea the agent proposed on its own) is rejected |
| `test_ambiguous_goal_smart` | Missing S falls back to `discovery`; missing M or T is rejected |
| `test_user_unsure_discovers` | The user is unclear: still forms a discovery goal, does not ask back, records an assumption |
| `test_no_invented_target_or_deadline` | A deadline that cannot be quoted becomes a review point; a target with no basis becomes an assumption |

Additional checks:

- **Store:** de-duplication by message; another brain cannot read, change or list; a stale `expected_revision` conflicts and changes nothing; old revisions stay intact; pause, budget and turns used survive revisions; the user's constraints cannot be dropped; the outbox has `goal.created` and `goal.revised`; creating with a nonexistent intent record leaves no half-made goal; reopening the store still has the data.
- **`form_goal`:** with a proposal from the brain it does not call the model and spends no turn; with no proposal the goal framer makes exactly one text-only call, with the user's words fenced as data; garbage output is rejected and still counts one turn; a blocked engine returns the turn.
- **Plugin through the real `plugins_host`:** a brain that has not enabled it does not see the tool, and enabling on this brain does not make another brain see it; create, repeated create, a proposal that breaks the rules (leaves no goal), update to revision 2 with route `continue_goal`, repeated update conflicts, nonexistent goal, `list`; two chat frames running at once and a turn without a message id are refused; turning it off makes the tool disappear and a call by an old reference is also refused.
- **`main.py`:** a brain that is off does nothing, creates no store file, and the prompt does not mention `javis_goal`; an enabled brain gets the hint line (under 450 characters); the brain calls the tool in a turn and then `main` branches `create_goal`, the goal belongs to the right brain by `_brain_key`, the output area is inside the brain; a Kanban task from the right chat frame during the turn is `task_now`, a task created before the turn does not count; a store error is swallowed and does not break the chat turn.

### Self-inflicted bugs found while working, fixed

- **Voice canary.** `test_voice_ten_javis.py` reads the source of `main.py` and looks for the exact line `store.append_message(conv_sid, "user", user_message)` to be sure a misheard name is fixed before saving. I wrapped that line in `int(... or 0)`, so the canary went red on the first full run. I fixed the code to match the canary (commit `f6fd4841`), not the canary.
- **Capability index.** The `main` test caught `javis_goal` still showing in the system prompt of a brain that had not enabled it, through the "Plugins running" line. It is now filtered by the tools that are actually visible.

### Fixes from the PR #567 review

ChatGPT's review (`exports/reviews/PR-567-M2-review.md`, diff `306e96cb..c79e27c5`) raised 1 P1 bug and 2 P2 bugs, all three reproducible through the real tool. Fixed in commits `709f016a` and `279ef56a`, with behavior tests in `tests/python/test_resonance_mvp_revise.py` (28 checks) and 7 more checks in `test_resonance_mvp_main.py`.

- **P1-1: a follow-up message lost the old deadline and targets.** The tool's `update` branch now calls `resonance.revise_goal`. This function reads the current revision BEFORE checking, then calls `validate_proposal(..., prior=..., source_ref=...)`:
  - fields left empty in the update are inherited;
  - a deadline the user stated in an earlier message is kept as is, both value and source, when the update keeps the same time and quote; the same for an old target when it keeps the same text and quote;
  - a NEW deadline or target must still be quotable from the current message, so when the user moves the deadline the new deadline wins; when the agent moves the deadline itself it still becomes a review point;
  - borrowing an old quote for a target with different text does not count as the old target;
  - each of the user's deadlines and targets now carries a `source` which is the message it is based on.

  The host derives the update's relation itself: `replace` when a deadline or target with a user source is no longer intact, otherwise `amend`. The relation is written to the new intent record (which now links to the previous revision's intent through `prev_intent_id`, replacing the unused `supersedes` column) and to the `reframe` event. (This version still let the brain drop a target by only writing `replace`; review round 2 rejected that, and it was fixed in the section below.)
- **P2-1: the voice lane and re-runs did not carry the message id.** `run_voice_turn` takes `user_mid` and passes it to both `run_turn` calls (keep the original sentence, fall back to the main brain). A retry scheduled after quota exhaustion carries the `user_mid` and `user_text` of the original turn, so re-running the same message does not create a second goal. The reply branch in a workflow session also passes the id. `run_turn` gains `user_text`: exactly the user's words, with the UI context block stripped and without the heard-sentence note or the workflow block the host attaches to the prompt. A follow-up turn that the host opens itself after background work still carries NO id, because the opening text belongs to the host.
- **P2-2: an empty criterion still passed the M gate.** Descriptions are whitespace-normalized; an empty criterion is dropped; when no criterion is left the proposal is rejected with a message saying a description of what to check is needed. Checking the structure of `params` per evaluator is left for M3, as the review suggested.

Fixing P2-1 turned two voice canaries that read the `main.py` source red on the first full run. `test_dien_giai_thuat_ngu.py` forbids `_giu_cau_goc` from mentioning the sentence the voice brain paraphrases, so the user's words are computed once into `_loi_goc` next to `original_message`; I changed the code, not the canary. `test_voice_turn_integrity.py` builds `run_voice_turn` with a fake `run_turn` that accepts no keyword arguments; the fake function was changed to also accept `user_mid`, `user_text`, and all of its checks are kept.

Re-running `PR-567-M2-repro.py` on the branch: the assertion describing the P1 bug is no longer true (the kept deadline is `deadline`), meaning the bug is gone. The other two checks are covered by the behavior tests above.

### Fixes from the PR #567 review, round 2

Round 2 review (`exports/reviews/PR-567-M2-review-round2.md`, diff `c79e27c5..9f2e9a32`) confirmed that the P2 on the missing id and the P2 on the empty criterion are closed, and raised 1 more P1 and 1 more P2.

- **P1: the `replace` label could not replace the basis.** (The fix described in this item was rejected by round 3 and replaced, see the round 3 section.) The round 1 version still let the brain send `targets=[]` or move the deadline by itself in a message that only changed presentation; the host saved it and wrote `replace`. Now the user's stated deadline and targets are standing instructions (invariant 2.1). An update can only change or drop them when the CURRENT message has a quote to base it on:
  - changing the deadline: the new deadline comes with a `quote` taken from this message;
  - dropping the deadline: the new horizon comes with a `horizon.quote` quoting the sentence that drops the deadline; the horizon records the sentence and the message it is based on;
  - dropping a target: an entry in `remove_targets` (a new tool field) with the same text, plus a `quote` taken from this message.

  Without a basis the host KEEPS the old instruction and does not reject the whole update, and the tool adds a line "The host kept the user's old instruction" with the reason so the brain knows. A review point the agent sets itself does not override a deadline that is in effect. `replace` is now only written for a change that was allowed. When the user restates a target, that target keeps a single entry with the new source. The old test that asserted dropping a target was correct has had its expectation changed.
- **P2: a partial update dropped constraints.** `_prior_view` now carries `constraints`; the new frame merges the old constraints, the new message's constraints and the proposed constraints. A partial update on a goal with constraints succeeds and keeps the constraints; the brain sending `constraints=[]` cannot remove them either. The tool says clearly that removing constraints is not supported yet.
- **Orphan intent on update (review point 5):** the intent record is now written in the SAME transaction as the revision (`GoalStore.new_intent` + `revise(intent=...)`), so a revision rejected by the store (conflict, missing constraint) leaves no intent behind. The goal CREATE path still writes the intent first and then calls `create`; if two turns with the same message interleave, the losing turn's intent remains.
- **Behavior check of the id handoff path (point 6):** the new test `test_resonance_mvp_handoff.py` (12 checks) extracts `run_turn`, `run_voice_turn` and `_start_resumed_turn` verbatim from `main.py` and runs them with fake services, following the setup of the independent round 2 check script. It checks that the turn ledger and the tool receive the right id and the right user words (UI context block stripped, no heard-sentence note) on both voice branches and the re-run branch; three turns with the same message create only one goal; a turn without an id makes the tool refuse.
- **Tests:** `test_resonance_mvp_revise.py` goes up to 42 checks (adding the cases of a presentation-only message with a dropped target or a self-moved deadline, a review point set by the agent, `remove_targets` with a quote not in the message, the user dropping a target and the deadline with a basis, restating a target, inherited constraints, no orphan intent, and two cases through the real tool).
- **Change to the `intents` table schema with no migration.** The table replaces the `supersedes` column with `prev_intent_id` and `relation`. M2 is not released yet, so there is no user data to keep. A store created with the old M2 schema does NOT upgrade itself; if there is data to keep, a migration must be written, and the store must not be deleted as a fix.

Re-running `PR-567-M2-round2-checks.py` on the branch: the P1 REPRO assertion (the brain sending `targets=[]` loses the target) is no longer true, meaning the bug is gone; the remaining P1 and P2 cases are covered by the behavior tests above.

### Fixes from the PR #567 review, round 3

Round 3 review (`exports/reviews/PR-567-M2-review-round3.md`, diff `9f2e9a32..2b1b212f`) confirmed that inherited constraints, protection when the brain forgets a field or reuses an old quote, the intent written in the same transaction, and the handoff tests all pass. Two points remain:

- **P1: a quote that IS PRESENT in the message could still drop an instruction.** The brain quoted "add a summary table" as the basis for dropping a target and dropping the deadline, and the host accepted it. A string search only proves the sentence is in the message, not that the user wants a change. This hole is wider than the review stated: the CHANGE-deadline path (new deadline with a quote from the current message) has the same weakness.

  The option chosen is the scope-narrowing one proposed by the review, matching invariant 2.1 of the reference design: the deadline, targets and constraints the user already stated can NOT be changed or dropped through an update in M2, whether or not the quote is present. The host keeps both value and source as they are. The tool returns "The host kept the old instruction, the following part is NOT applied yet" and tells the brain to say clearly to the user that it could not be changed yet, and not to report it as changed. An update with nothing applicable left writes no revision and no intent, and the tool says "NO change was applied". Adding NEW instructions is still allowed, with the same quoting rule as at creation: new targets, new constraints, and a deadline when the goal has no user deadline yet. When the user restates a target it is still one entry, keeping the old source. The agent can still fix its own understanding, criteria, assumptions and questions. The path to change authoritative instructions is determined by the host (the user's action on the goal card, or confirming exactly the part being changed) and is left for M4.
- **P2: sending only `remove_targets` reported success while removing nothing.** It is no longer a feature: the `remove_targets` field was removed from the tool schema; if the brain still sends it, the host reports "remove_targets not supported yet" and writes no revision.
- **Tests:** `test_resonance_mvp_revise.py` goes up to 48 checks, with the change/drop-instruction cases rewritten for the new scope: an old quote, a quote that is present but unrelated (exactly the round 3 reproduction), the user genuinely moving the deadline, the user genuinely dropping a target and the deadline, sending only `remove_targets`, adding a new target, adding a deadline when there is no user deadline, restating a target. Each case checks the final state in the store, not just that the tool returned success.

Re-running `PR-567-M2-round3-checks.py`: the first two PASS assertions still pass. Step 4 of the script stops at a revision conflict, because the script assumes step 3 writes a new revision, whereas now an update that can change nothing writes no revision. Running a copy that only changes step 4's `expected_revision` to the current revision: the P1 REPRO assertion is no longer true (the target and deadline are intact). The P2 case is covered in the PR's tests.

### Fixes from the PR #567 review, round 4

Round 4 review (`exports/reviews/PR-567-M2-review-round4.md`, diff `2b1b212f..439fe922`) closes the P1 within the narrowed M2 scope and keeps the scope decision as is. Two local P2 bugs remain:

- **P2-1: a blocked horizon still dragged `mode` along.** `mode` was computed from the proposal's `kind` variable and not from the final horizon the host accepted, so a blocked `maintain` proposal still changed an `achieve` goal into `maintain` and wrote a revision. Now `mode` is computed from the accepted horizon; when no `mode` is sent the previous mode is kept.
- **P2-2: the tool filtered out `remove_targets` before the validator could report it.** The plugin's `_proposal` now forwards this legacy field (still outside the schema) so the validator can report "not supported yet". The tool's summary now has a line "Targets stated by the user", so the brain can see the targets that are still kept.
- **Tests:** `test_resonance_mvp_revise.py` goes up to 58 checks. `_frozen` also checks mode and stage. Three new cases go through the real `plugins_host`, comparing the whole `GoalRecord` and the row counts of `intents`, `goal_revisions`, `goal_events`, `outbox` before and after: a blocked maintain horizon; sending only `remove_targets`; a valid edit mixed with `remove_targets` (the valid part is applied, the tool reports "Updated" along with the part NOT applied and the targets still kept). Row counting uses `closing` so no SQLite connection is held open.

Re-running `PR-567-M2-round4-checks.py`: two PASS assertions pass; the P2-1 REPRO assertion is no longer true. A copy with the two P2-1 assertions removed, to run through to P2-2: the P2-2 REPRO assertion is also no longer true.

### Limits and what was not verified

1. **No real model called in M2.** It was not measured whether the real brain calls `javis_goal` at the right moment, or whether its proposals pass the SMART rules. The real single-goal pilot is M3's job per the plan.
2. **Web chat frame only.** Telegram and Zalo do not pass a message id yet, so the tool refuses to form a goal there. (The first version also missed the voice lane, the retry after quota exhaustion and the workflow session; these were fixed after the review, see the section above.)
3. **No guard in the data model yet.** The plan says that changing the understanding keeps "permissions, budget, guard, pause". M2 keeps budget, turns used and pause; guard arrives with M3.
4. **The intent record can be orphaned on the create path.** The update path already writes the intent in the same transaction as the revision (review round 2). The create path still writes the intent before `create`: if two turns with the same message interleave, the losing turn's intent remains. The table is append-only, so this does no harm.
5. **`reminders_created` is not wired up yet.** The routing function accepts the number of reminders created in the turn, but `main` only counts Kanban tasks. A turn that only sets a reminder is currently recorded as `answer_now`.
6. **The routed branch is only written to the runtime event so far.** M4 uses it to draw the "What Jarvis 007 is working toward" card.
7. **No JS tests were run.** M2 changes no JS files.
8. **Not every voice path supports Resonance.** Background work handed off by the fast lane (V3, `JAVIS_ASK_MAIN`) is the fast lane's normal handoff path, does not call `run_turn` and does not register a turn with a message id, so the tool refuses. Only the two voice branches that go back to `run_turn` (keep the original sentence, fall back to the main brain) carry the id. If the M3 pilot hands off work by voice, a trusted source of the request must first be passed through the background work path.
9. **The id path was checked with real functions and fake services.** It has not been run end to end with a real model, microphone, HTTP/WebSocket, or a real quota wait.
10. **Instructions the user already stated cannot be changed or dropped yet.** The saved deadline, targets and constraints can only be added to, not changed or dropped by chat in M2; the tool states clearly which part was not applied. The authoritative edit path is left for M4. This limit must not be used to ignore a stop command or a permission revocation once there is an execution runtime.
11. **Checking `params` per evaluator is not done.** Currently it only checks that it is an object and then copies it; this is M3's job.

### Full Python test run

| | Clean main (`7d264236`) | M2 branch (`f6fd4841`) | M2 after review (`279ef56a`) | M2 after review round 2 (`daa5684e`) | M2 after review round 3 (`1f9099c9`) | M2 after review round 4 (`d57cd14e`) |
|---|---|---|---|---|---|---|
| Green | 387/403 | 392/407 | 391/408 | 393/409 | 391/409 | 393/409 |
| Red files | 16 | 15 | 17 | 16 | 18 | 16 |
| New red vs main | | none | none caused by M2 | none | none caused by M2 | none caused by M2 |

Round 2 run: the 16 red files are exactly the red list on clean main (the 15 files in the M1 section plus `test_project_khung.py`).

Round 3 run: those 16 files plus two flaky files. `test_hoi_thoai_nhom.py` is noted above. `test_bao_viec_ve_chat_web.py` was red in the full run, and run alone three times on the same code it was green, and it does not touch Resonance code.

Round 4 run: the 15 files already red in the M1 section plus `test_hoi_thoai_nhom.py` (flaky). `test_project_khung.py` is green in this run.

In the run after the review, the 17 red files are the 15 files already red in the M1 section, `test_project_khung.py` (red on clean main) and `test_write_path_phase9.py`. The last file, run alone twice on the same code, was green once and red once (`test_restart_marks_running_writes_unknown_without_rerunning`), and it touches no Resonance code: a flaky test. `test_hoi_thoai_nhom.py` is also flaky (run alone three times: green once, red twice, and checking the M2 conversation pin order does not touch it); in this full run it is green.

The list of 15 red files is exactly the list already red in the M1 section. `test_project_khung.py` keeps being green on the branch, as in M1.

The first full run of M2 (commit `66328b61`) had `test_voice_ten_javis.py` red because of M2, fixed in `f6fd4841` as noted in the self-inflicted bugs section.

## M3: execution, evidence and a small schedule (2026-10-06)

### Base and branch

- Branch `claude/resonance-mvp-m3` split from the M2 head that passed review (`fa7e264d`), draft PR #570 stacked on #567. Version 0.84.4: `origin/main` has already reached 0.84.2 (`bacb1cfe`) and PR #569 is holding 0.84.3.
- `origin/main` has moved on by exactly one commit relative to the chain's base `7d264236` (`bacb1cfe`, Zalo joining groups). That commit only changes the Zalo part plus `VERSION` and two CHANGELOGs, and does not touch any Resonance file. It is not synced into the chain right now: syncing would add a merge commit to two PRs that already passed review without changing anything in Resonance. VERSION and CHANGELOG will be adjusted once at merge time.

### Design decisions for the reviewer to check

1. **A single `advance(goal_id, event, deps)` loop that resumes after a restart** (spec section 7). Each time: check the brain switch, pause, guard; take a time-limited turn lease (`claim_lease`); reconcile any half-done action; assess the evidence attached to EXACTLY the current revision; only if the goal is not yet achieved and the event is a type that allows work (`start`, `wake`, `user_message`, `resume`) does it do ONE step. `observe` only watches the guard; `reaction` does nothing; `user_schedule` edits the schedule.
2. **Write the intent before the effect.** `GoalStore.begin_action` writes a `running` action and reserves one model call in the SAME transaction (`calls_used < budget_calls`), together with a recovery schedule at lease expiry. If it cannot be written, the engine is not built. When the quota is exhausted the goal is blocked as `budget` and no call is made.
3. **Reconciliation after a restart.** For a `running` action whose lease has expired: if there is an output file with exactly that `action_id`, it is settled as succeeded (`reconciled: true`) and the model is not called again; if not, it becomes `failed: interrupted` (the model may already have been called so it still counts against the quota) and the next turn uses a NEW id. A publish action is reconciled by the hash of the target file.
4. **Evidence through the real EvidenceStore.** `main._ResonanceEvidence` opens a runtime turn on the `resonance` channel for each write, encrypts it, and reads it back through `get_valid` (checking expiry and hash). The store has no pinning mechanism yet, so the retention is set to 90 days. If evidence cannot be written it counts as NO evidence yet and success is not confirmed. Each time a file in the brain is assessed, its content is also snapshotted into the store (skipped if the hash is the same).
5. **Placing the product into the brain, with barriers.** The model's output sits in the work area `Javis/resonance/outputs/<goal>`; the host publishes that copy to the path of the first `artifact_contract` criterion that declares a `path`, if and only if: the path is inside the brain after resolving; the extension is `.md` or `.txt`; it is NOT in a place Jarvis 007 runs or loads by itself (hidden folders, `Javis/`, `agents/`, `skills/`, `workflows/`, `plugins/`, `memory/`, the files `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`/`MEMORY.md`); the file does not exist yet, or it exists but its hash equals what this same goal published last time. If a file was changed by the user or another task, that is a conflict: it is left as is, `publish_conflict` is recorded, and the user is notified. The brain switch is checked again RIGHT BEFORE publishing.
6. **Conclusion.** `evaluate_artifact` returns met / not_met / unknown per criterion: a missing declared file is not_met; evidence that does not exist yet or cannot be read back is unknown; a path outside the brain is unknown (evaluator error); `human_confirmation` is always unknown until M4. An achieve goal becomes `succeeded` only when EVERY criterion is met and `GoalStore.finish` compares exactly the revision that was assessed (CAS). A maintain goal that is met stays active and schedules a review. When only user criteria remain, it moves to `waiting` and no model call is scheduled.
7. **Schedule.** A `wakeups` table (one `work` schedule and one `observe` schedule per goal). `main._resonance_tick` is started by the existing 30-second scheduler through `create_task` (a busy flag prevents overlapping ticks); if `resonance.sqlite3` does not exist yet it exits immediately. `tick` only reads due schedules with code and claims each schedule with CAS. `next_wake`: with no event source, review within 6 to 24 hours; an `event` horizon has no adapter yet so it also only gets a bounded review; if not achieved after one turn, retry after 15 minutes if quota remains; an engine error backs off 1 hour, 4 hours, 24 hours or waits for the plan's quota reopening time (`limit_learner.parse_subscription_limit`); when the user schedules something the schedule is edited directly; a reaction changes nothing. Creating and editing a goal write the `work` schedule inside their own transaction.
8. **Guard.** A new `guards` field in the goal frame (accepted by the tool). Only `artifact_contract` has a reading adapter: the declared file must still exist and meet the condition. Other sources record unknown "source ... not supported yet (no reading adapter)". The guard has its own observation schedule (1 hour), read by code, no model call. When a guard trips, the goal is blocked as `guard`, all schedules are cleared, the user is notified, and it does not reopen by itself when woken.
9. **Notifying the user through the outbox.** `drain_outbox` sends exactly the meaningful messages (`goal.succeeded`, `goal.maintained`, `goal.waiting_human`, `goal.blocked`, `goal.guard`, `goal.publish_conflict`) to `_notify_owner("web:<assigned session>")` (the chat frame plus the inbox) and then marks them sent; internal messages are only marked. A unique `idem` key per goal prevents repeated notices. If sending fails, it is left for the next tick.
10. **What is sent to the model.** The goal, the WHOLE chain of user words (followed through `prev_intent_id`, at most 5 messages), criteria, constraints, assumptions, the part not achieved last time, and the current version of the product; the user's words and the old version sit inside a data fence. The engine is still the text-only path from M1 (`main._resonance_engine`), with no fallback chain.
11. **Schema.** New tables `actions`, `assessments`, `evidence_links`, `wakeups`, `published`; new columns `goals.run_state/block_reason/lease_owner/lease_until`, `outbox.idem` added with `ALTER TABLE` when the store opens, so a store created by the M2 version upgrades in place and no data is deleted.
12. **Checking `params` per evaluator** (handed from the M2 review to M3): the `artifact_contract` of criteria and guards only accepts `path` (relative, no `..`, no drive letter), `min_chars` (an integer within the output cap), `must_contain` (at most 10 non-empty strings); unknown or wrongly typed parameters reject the proposal with a clear message. `human_confirmation` carries no params.
13. **`run_once` changes an em dash to "-" before writing** (the rule banning em dashes in files, including the brain), and the receipt records how many places were changed (`normalized_em_dash`); the hash is of exactly the bytes that were written.

### Results with the fake engine

`tests/python/test_resonance_mvp_run.py` (71 checks in the first version, 92 after the review fixes), a real SQLite store, a fake engine following the aux_engine event contract, and a fake evidence gate with the same contract as `_ResonanceEvidence`. It has all the tests Task M3 named: `done_is_not_success`, `missing_evidence_unknown`, `restart_does_not_repeat_effect`, `old_revision_cannot_finish`, `pause_and_revoke`, `audit_failure_before_effect`, `budget_reserved_before_call`, `limit_keeps_checkpoint`, `no_paid_provider_fallback`, `idle_does_not_call_model`, `guard_wakes_without_worker`, `no_source_uses_bounded_review`. Added: not overwriting a file the user changed, nine paths forbidden for publishing, a maintain goal continuing after a follow-up message (the model prompt has the original words, the new message and the current version), and notifying once per revision.

`tests/python/test_resonance_mvp_main.py` adds 10 checks (32 in total): the evidence gate writes and then reads back the REAL EvidenceStore, `_resonance_deps` builds the right principal and engine, and one goal runs the full loop on the host with a fake engine: the `javis_goal` tool creates it, `main._resonance_tick` works on it in the background, the product goes into the brain, the goal succeeds, and it is reported to the right `web:<session>` with a link; the next tick does not call the engine.

Mutation tests (break each behavior and re-run the tests, which must go red): remove the conflict check when publishing, remove the quota cap, remove the pause check, reconciliation not looking at the output file, treating unknown as done, `finish` not comparing the revision, truncating the intent chain, removing the publish-forbidden list. All eight were caught by the tests.

### Real pilot results

`tests/python/test_resonance_mvp_pilot.py`, which only runs when `JAVIS_RESONANCE_PILOT=1`. Evidence: `docs/dev/resonance-mvp-m3-pilot.json` (no personal paths).

- **Commit:** `9f3dad13`, `server/` tree clean. Afterwards there were more changes to the notification path (`goal.maintained`) and the publish-forbidden list; these two parts were checked with the fake engine and the real pilot was NOT re-run, to preserve the quota.
- **Environment:** a temp `JAVIS_STATE_DIR`, copying only the engine selection fields (`anthropic-cli` / `sonnet`), a temp brain with simulated data, and the notification channel replaced by a recorder.
- **Scenario:** a maintain goal "the note `Inbox/viec-tuan.md` lists the unfinished tasks" (the filename means "weekly tasks" and is kept as the verbatim identifier) with the guard "the old notes are still there", and a quota of 3 turns. Tick 1 goes through `main._resonance_tick`; the user adds "renew the domain name"; a restart is simulated (drop the store object, open a fresh store); tick 2; tick 3.
- **Result:** 2 real model calls (6.0 and 5.0 seconds), both receipts succeeded, the right provider that was selected, 0 tool calls, and the hash matches the file on disk. Both publish actions succeeded (the second could overwrite because the hash matched this goal's own first publish). The host checked both revisions as met. Tick 3 made no further call. Used 2/3 turns. The evidence for revision 2 could be read back from the real EvidenceStore, and the hash matches. The old note is untouched, with no em dash.
- **Usage reported by the engine:** about 18.1 thousand and 18.5 thousand input tokens, about 300 output tokens per turn; `cost_usd` is the figure the SDK computes by itself on a subscription plan, not an invoice.
- **The pilot exposed two things:** (a) the maintain goal was met without telling the user anything, fixed with `goal.maintained`; (b) the model wrote a wrong sentence on its own, "the old notes in Inbox/viec-tuan.md are kept as they are", while the old notes are in `Notes/`. The text-only executor only sees constraints as text, not files, so it may write unverified claims. This is a quality limit, not fixed in M3.

### Self-inflicted or self-found bugs while working, fixed

- **Lost context when continuing.** After a follow-up message, the revision's intent is that follow-up message, so the continuing step only gave the new message to the model, losing the original assignment and the version already made. Found while designing the pilot; fixed in `9f3dad13`.
- **A silent maintain goal.** Found in the pilot; fixed in `a71b124e`.
- **The product could create Jarvis 007 config files.** Reviewing the diff myself, I saw that a path declared by the model could create `Javis/loops/*.md`, `agents/*.md`, `skills/*/SKILL.md`, `memory/...` or `CLAUDE.md`, which means expanding its own permissions. Added a forbidden list in `_publish`.
- **Two bugs in my own tests:** the `maintain` horizon makes the goal a maintain goal so it does not "succeed" (correct by design, test fixed); the shared `tick` also processes other goals that are due (test fixed to count per goal).

### Fixes from the PR #570 review

ChatGPT's review (`exports/reviews/PR-570-M3-review.md`, diff `fa7e264d..e5a42409`) raised 5 P1 bugs and 1 P2 bug, all six reproducible on a real SQLite GoalStore. I agreed with all six. Fixed in one commit, with regression tests at the end of `test_resonance_mvp_run.py` (up to 92 checks).

- **P1-1, a pause in the middle of a turn was ignored at the publish step.** Added `_gate`: the goal is still active, the brain switch is still on, the user has not paused, and every guard is clear. The gate runs before EVERY product publish and every success conclusion, including right after the model returns. If it is blocked, the output stays in the work area, and the receipt and turns used are still recorded. On resume (`set_paused(False)` now schedules work immediately), `_publish_latest` publishes the saved output of the current revision through the gate, WITHOUT calling the model a second time.
- **P1-2, the guard did not protect every path.** (a) After the model runs, the gate observes the guard again. (b) `_reconcile` now only settles the receipt; publishing a reconciled output goes through the gate like every other time, so if the guard has already tripped the receipt is settled but the product is not published. (c) An unknown guard (source not supported or unreadable) is no longer treated as clear: blocked as `guard_unknown`, no publish, no conclusion, the user is notified once per revision, and it is re-checked by code after at least 6 hours. The guard result travels with the assessment.
- **P1-3, an update could drop a guard.** Existing guards are kept through every update: `guards=[]`, changing the path, and changing the evaluator can only ADD new guards, while the old guard keeps its id and condition; anything meant to be dropped or edited reports "not supported yet". Same scope as already settled for the deadline, targets and constraints in M2.
- **P1-4, claiming a schedule by deleting it lost the work.** `tick` claims a schedule with `claim_wake`: CAS on `due_at` and then PUSHES the schedule to the claim expiry time (the maximum duration of a turn plus a margin), without deleting it. If the process dies after claiming but before `advance` writes anything, the schedule comes due again by itself; `advance` overwrites or deletes the schedule once there is a next state. If a goal is busy under another turn's lease, its schedule stays there to run later.
- **P1-5, passing the discovery step closed the original need.** A criterion met at stage `discovery` does not call `finish`: the goal waits at `discovery_done` and tells the user this was only the exploration step. This comes with the fix for a default from M2 that surfaced while fixing this case: when no `stage` is declared it used to always be `discovery`, and now it is `delivery` once there is a concrete understanding (the literal meaning of S); otherwise every goal the brain formed with the stage left blank would never complete.
- **P2-1, with only user criteria the goal waited before doing any work.** "Only waiting for the user" now requires that a product of the current revision already exists when there is no other checkable criterion. A goal with only `human_confirmation` first makes a version to review, and the waiting-for-review message carries a link to that version in the work area.

Re-running `PR-570-M3-checks.py`: the script stops at the first REPRO assertion because that bug is gone. A copy that wraps each case separately gives: the 2 control PASS assertions still pass (the basic path, the archived pilot hash), and all 8 REPRO assertions are no longer true. Six mutation tests on the fix (remove the gate after the model runs, treat an unknown guard as clear, remove guard inheritance, claim schedules by deleting, let discovery close the goal, let human-only wait when there is no version yet) all turned the tests red.

The real pilot was not re-run for this fix: the changes are in the check gate, reconciliation and the schedule, all of which can be checked deterministically with the fake engine.

### Fixes from the PR #570 review, round 2

Round 2 review (`exports/reviews/PR-570-M3-review-round2.md`, diff `e5a42409..9aad1f5d`) confirmed that the six round 1 fix groups pass with the right behavior assertions, and raised one P1 bug still open in P1-2: the guard check gate runs BEFORE publishing, and then that snapshot is attached to the assessment AFTER publishing. When the guard reads the product file itself and the new version makes the guard fail (for example dropping a heading that must be kept), the goal is still closed as successful. The bug happens sequentially, and is not the race window noted in the limits.

- **Check the candidate version before replacing the file.** `_publish` checks the content about to be written against every `artifact_contract` guard that reads exactly the target file. If the new version makes the guard fail, the currently valid version is kept, the new one stays in the work area, and a `publish_blocked_by_guard` event is recorded.
- **Re-check on the final state.** `_after_publish` runs the gate again after publishing and only then assesses; the guard in the assessment is the result of this check. If a candidate version is blocked by a guard, the assessment adds a not_met line naming the guard, so it does not conclude success, does not report `goal.maintained`, and the redo turn gives that feedback to the model.
- **Both paths.** The normal work path and the path that reuses a saved output (after a pause, after an interruption) both go through the two steps above. If a saved output is valid, resume still publishes and succeeds WITHOUT spending an extra model turn; if a saved output makes the guard fail, it is not published, and the host redoes one turn within quota with feedback about the guard.
- **Tests:** added 7 checks following the two scenarios of the review plus a control case (`test_resonance_mvp_run.py` goes up to 99). Removing the candidate check turns 6 checks red. Script `PR-570-M3-round2-checks.py`: the first 10 PASS still pass; in both REPRO cases the real guard stays clear and the goal is not closed. The script's resume case still has an assertion "no extra call" written for the bug state; after the fix, an output that violates the guard leads to exactly one redo turn with feedback, as designed above.

### Limits and what was not verified

1. **No policy yet for reaching the deadline.** No goal is concluded as `failed`; reaching the deadline without being achieved is still just not achieved. Spec 7 requires recording unknown and applying the agreed deadline policy.
2. **The executor has text only.** It cannot read files or brain data; a goal that needs data must have the brain do it inside the chat turn. The model may write unverified claims (for example in the pilot).
3. **One product per goal.** Only the first `artifact_contract` criterion that has a `path` is published; other criteria are only assessed.
4. **A gap between check and write when publishing the product.** If the user edits the file exactly between the host comparing the hash and replacing the file, the user's version may be replaced. There is no file lock yet.
5. **Notifications are at-least-once.** If the process dies between sending and marking, the message may be sent twice. Replaying without duplicates at the message store is M4's job.
6. **Guard.** Only `artifact_contract` can be read; other sources make the goal stop at `guard_unknown` until there is an adapter; reading a guard does not snapshot into the evidence store; a guard that has tripped and old guards have no path to reopen or edit (user commands in M4).
7. **Evidence is not pinned.** Retention is 90 days; after expiry, reassessment gives unknown.
8. **SQLite operations are synchronous in the event loop.** Each one is small, but they are not moved to a separate thread yet. Each tick handles at most 3 schedules.
9. **The real pilot ran at `9f3dad13`**, before the last two changes (reporting `goal.maintained`, the publish-forbidden list); those two changes were only checked with the fake engine.
10. **Still outstanding from M2:** background work handed off on its own by the voice lane does not form a goal; the user's stated instructions cannot be changed or dropped yet.

### Full Python test run

| | Clean main (`7d264236`) | M3 branch (`e07c68cd`) | M3 after review (`6c840c93`) | M3 after review round 2 (`7ceb987e`) |
|---|---|---|---|---|
| Green | 387/403 | 396/411 | 395/411 | 396/411 |
| Red files | 16 | 15 | 16 | 15 |
| New red vs main | | none | none | none |

Run after the review: the 15 files already red in the M1 section plus `test_project_khung.py` (red on clean main, flaky).

The 15 red files are exactly the list already red in the M1 section. An earlier run (on the tree being edited, between two commits) was cut off at file 408/411 and left five Zalo/YouTube files red in a row just before stopping; running the last eight files alone all came out green, so that run is not counted.

## M4: goal card and clearly meaningful feedback (2026-10-07)

### Base and branch

- Branch `claude/resonance-mvp-m4` split from the M3 head that passed review (`1fe86a04`), draft PR #575 stacked on #570. Version 0.84.9: `origin/main` has already reached 0.84.8 (`3e3d7d48`) and PR #571 is holding 0.84.5.
- `origin/main` has moved on by 5 more commits relative to the base `7d264236`; among the files M4 edits, only `server/main.py` changed (2 lines in the Zalo part, not touching the Resonance area). Not synced into the chain yet, for the same reason as in M3; adjusted once at merge time.

### Design decisions for the reviewer to check

1. **Two separate questions** (spec 4.5, 4.7). `goal_fit_confirmed` / `goal_fit_rejected` confirm the understanding of exactly the revision currently shown. `outcome_accepted` / `outcome_rejected` are only accepted for a `human_confirmation` criterion (a criterion the host checks automatically returns 400), tied to exactly `artifact_ref` = the sha256 of the CURRENT bytes of the file the card shows (the product file in the brain, or the latest output of the revision when no file is declared), and only available when the current revision already has a successful work turn; if the file changes, the old confirmation no longer applies (fixed after round 1 review, see below). A confirmation does not override an objective check or a guard. Silence is unknown.
2. **Only the user can write feedback.** The dashboard has a single login account; requests to the API have gone through `_auth_guard` and `_csrf_guard`, so the host builds `Principal("owner")` from the resolved brain. If the agent calls `record_feedback`, it gets `PermissionError`.
3. **Every piece of feedback is tied to a revision (CAS).** An old card sending an old revision gets 409 with the new state so the card can redraw. The same `idempotency_key` is not written a second time; the key identifies ONE click, so re-sending exactly that click is a duplicate while a new click is always recorded.
4. **"Not quite"** stops the next effect of that revision (`waiting / fit_rejected`, checked in `_gate`), and is not a full stop command: a new revision (the user speaks more clearly, the brain updates) reopens normally. "Resume" cannot override it.
5. **The pause, resume and cancel commands always take effect**, and do not require matching a revision (a user intervention, spec 2.3); the revision the user is looking at is still recorded. "Resume" reopens a guard that has tripped only when the guard is now clear. Viewing the card and these commands do not require the switch to be on; only feedback and forming goals do.
6. **The authoritative path to drop the user's instructions** (the thing M2 and M3 promised to M4): the card lists the deadline, targets, constraints and guards with a "Remove" button; the `drop_directive` command is owner-only, requires the exact revision, creates a new revision recording the source as the user and the relation `replace`, also removes the item from the store's list of user constraints, and lifts the block if the dropped guard is exactly the one blocking. The brain still cannot do it through `javis_goal`; the message about the part not applied and the tool description now point the user only to this button. Changing the deadline to another date is still two steps: drop the old deadline on the card, then state the new deadline in chat so the brain adds it.
7. **No repeated report after an incident.** The report message carries a `JAVIS_RESONANCE` block with the key `outbox:<id>`. `drain_outbox` asks the message store whether that key is already there (`main._resonance_reported`): if the process dies between saving the message and marking the outbox, the next tick only marks it and does not send a second time. `push_to_chat`, `_gui_qua_kenh`, `_notify_owner` gain an optional `card` parameter that only accepts exactly that block form; existing callers are unchanged.
8. **The card block carries only an id.** The card reads live state through `GET /goals/{id}`, so F5, reopening an old conversation or reconnecting all draw the correct current state. The block name is `JAVIS_RESONANCE`, different from the `JAVIS_GOAL` of the existing `/goal` command.
9. **One goal, many messages.** A goal can appear in the message at creation, at a progress report, and at completion. Every card of the same goal is drawn from one state; only the newest card is full and has buttons, and old cards are a single status line.
10. **Waiting for user review** now requires a product of EXACTLY the current revision. Before this, a new revision whose declared file still passed thanks to the old revision's version would wait for confirmation while there was no version to attach the button to.
11. **A per-brain switch** on the quick settings page ("Auto (experimental)", off by default), through `GET/POST /resonance/settings`.
12. **`POST /goal-requests`** forms a goal from an existing user message (`msg:<session>:<id>`, the session must belong to the brain, the message must be the user's), one goal-framer turn, and the same message returns the existing goal. No UI button calls it yet.

### Results with the fake engine and the real API

- `tests/python/test_resonance_mvp_feedback.py`: TestClient on `main.app` (http://127.0.0.1:8080), SQLite store, real session store, fake engine. It has all the tests Task M4 named: `goal_fit_not_outcome`, `feedback_old_revision`, `feedback_cross_brain`, `silence_is_unknown`, `reload_keeps_goal_action_links`, `report_replay_same_mid`. Added: a confirmation does not override a guard or an objective check; "Needs changes" redoes with feedback and the old confirmation does not apply to the new version; "Not quite" blocks until a new revision; the pause, resume and cancel commands; dropping each kind of instruction; `goal-requests`; the per-brain switch.
- `tests/js/test_resonance_mvp_ui.js`: block extraction (including broken JSON), card HTML safe against code injection, the "Meets the bar" button only for user-reviewed criteria and only when a product exists, the request takes revision / criterion / artifact_ref from the loaded state, an old card sends exactly the old revision, a compact card, the "Remove" instruction button, the vi/en dictionary keys, and the hook-up points in app.js / index.html / style.css.
- Mutation tests: remove duplicate-report reconciliation, remove the "Not quite" block, let a confirmation apply to an old version, let a manual confirmation apply to an automatic criterion. All four turned the tests red.
- Two old canaries (`test_the_viec_nen.js`, `test_voice_v3_mot_luong.js`) pin verbatim two read-aloud lines in `app.js`; exactly those two lines are kept, and the card block is stripped on the line before.
- The first full run turned two more files red because of M4, fixed in `4ae62efa`: `test_viec_nen_khong_moc_lung_tung.py` pins the verbatim `push_to_chat` call for the background-work card in `_gui_qua_kenh` (the goal card branch is split out separately, keeping the old line as is); `test_route_table.py` is a snapshot of the route table, deliberately re-captured for the 7 new routes, with no old route dropped or sharing a prefix.

### Real UI check

A sandbox server of the worktree (port 7788, temp `JAVIS_STATE_DIR` and `BRAINS_DIR`, the background engine set to a pre-blocked text-only selector provider so NO model call was made), the in-app browser, a narrow phone-sized frame:

- The card shows the understanding, status, criteria (Met / Unknown), product, assumptions, quota and buttons in full; it does not overflow horizontally.
- Mouse click "That's right": recorded, and the card shows "You confirmed this understanding". Keyboard: focus "Meets the bar" and then Enter: recorded; the schedule tick afterwards reassesses and concludes "Achieved" without calling the model; there is a completion notice.
- F5 and reopening the conversation: every card reads back the correct live state.
- The card is showing revision 1, the goal is edited to revision 2 behind it, click "That's right": 409, the card redraws revision 2 with a notice, and no confirmation is recorded for revision 2.
- Pause with the mouse, resume: the right state; resume leads to a work turn, the engine is deliberately blocked so the card shows "The background engine cannot run yet".
- The per-brain switch on the settings page: reads correctly, and turning it off and on again writes correctly.

Three things this check exposed, fixed in `a2cf6cc7`: the card still said "Unknown" right after clicking "Meets the bar" (it now reads the live confirmation under the assessment rule and reports that it was recorded); several cards of the same goal showed contradictory states (they are now drawn together, and old cards collapse); "Next step" still showed while paused (now hidden). One mouse click by coordinates computed while the page was still scrolling missed the button; clicking again based on a screenshot worked, noted to tell it apart from a bug.

Very long paths on Windows: in the first sandbox folder (a very deep temp path), writing the output to `Javis/resonance/outputs/<goal>/<action>.md` went over the 260 character limit and the work turn ended with `write_failed` (the host reported the error correctly, and did not fake success). A brain at a normal path does not hit this; a brain placed very deep might.

No real model pilot was run for M4: the new parts are the API, the store and the UI, which can be checked deterministically; the model-calling path has not changed since M3.

### Fixes from the PR #575 review, round 1

The review did not pass, with 3 P1 bugs and 2 P2 bugs. I agreed with all five; each bug has a regression test in `test_resonance_mvp_feedback.py` (section "Review M4 round 1") or `test_resonance_mvp_ui.js`, turning the reviewer's REPRO cases into expected behavior.

1. **P1-1, product identity.** `artifact_ref` used to be the `output_sha256` in the receipt, meaning evidence that the worker produced the content, not the file the user is looking at. It is now the sha256 of the current bytes of that file (`_artifact_file`, `_artifact_ref_of` in `resonance.py`), shared by the card, the `outcome_*` check and `_human_verdict` at assessment time. If the file changes after approval the old confirmation becomes unknown and the goal does not succeed; an old card clicking "Meets the bar" gets 409 with the new `artifact_ref`. Tightened further: a new revision with no successful work turn has no version to review, because the file on disk is then from the old understanding.
2. **P1-2, the anti-double-click key swallowed a new click.** The old key was fixed per goal, revision, button, criterion and product version, so a second "Not quite" after "That's right" was treated by the server as a duplicate. Now `requestFor` takes the click's `nonce` (`send()` generates a new one each time; if none is passed it generates its own). The server keeps the rule: the same key is a duplicate, so re-sending exactly one request still writes once. Both orders are tested (Not quite, That's right, Not quite and the reverse).
3. **P1-3, duplicate guard id.** The id used to be issued as `len(guards) + 1`, so dropping `gd1` and then adding a new guard produced a second `gd2`, and the Remove button deleted both. Now the frame stores an increasing counter `guard_seq` (a new field of `GoalRecord`, read in `_record`, carried through `_prior_view`), and the next id is greater than every id ever issued; a frame with a duplicate id is not saved. When `drop_directive` meets old data with two guards sharing an id it refuses (400), and neither guesses nor deletes both.
4. **P2-1, turning Resonance off blocked the stop commands.** Now viewing the card, the list, and the pause, cancel, resume and drop-instruction commands only require that the brain exists (`_manage` in `resonance_api.py`); feedback and `POST /goal-requests` still require the switch to be on. Continuing to run is still blocked by the switch in `_gate`, so "Resume" while off only removes the pause and does not call the model.
5. **P2-2, report reconciliation only looked at the last 300 messages.** The round 1 version searched for the key string across the whole session in SQL (`instr`); this version was rejected by the round 2 review (see below) and replaced with a receipt.

The reviewer's script (`PR-575-M4-checks.py`) run case by case independently on the fix: 6/6 REPRO no longer reproduce, 2/2 PASS still pass. Mutation tests: reverting each fix (the receipt hash, dropping the requirement of the revision's work turn, id by length, deleting every duplicate id, the switch blocking commands, not finding the report) all turned the tests red.

### Fixes from the PR #575 review, round 2

Round 2 review confirmed the five round 1 bugs are fixed, and found one new P2 bug caused by the P2-2 fix itself: the string `"report": "outbox:<id>"` appearing in any assistant message (an explanation quoting JSON, a log) was treated as a report already sent, so `drain_outbox` marked the outbox row as delivered without sending anything.

**Fix:** the evidence of "sent" is a receipt written by the host, not the content of the message. When `push_to_chat` meets a card carrying a report key, it writes one row `report_receipts(session_id, report_key, goal_id, message_id)` in the SAME SQLite transaction as the report message (`SessionStore.append_message(..., report=...)`), so there is no state with a saved message but a missing receipt. `main._resonance_reported` only accepts a receipt of exactly the right session, the right key and the right goal (`SessionStore.report_receipt`), and then cross-checks the card block in the message. A lookup by primary key means there is still no depth limit. `find_message_containing` was removed.

Why not just parse the `JAVIS_RESONANCE` block in the candidate messages as the review's minimal suggestion said: assistant messages generated by the model are stored raw in several places (`main.py` in the normal chat turn, background work results), so a valid block that the model writes itself (for example copying an old message when the user asks) would also swallow the real report. Only the host can write a receipt.

**Consequence for the reviewer's round 2 script:** the two PASS cases "recent persisted report is recognized" and "not replayed after 300 later messages" build the "already sent" message with a raw `SessionStore.append_message`, which is exactly the shape of a block the model wrote itself; after the fix, such a message is deliberately NO longer counted as sent, so the round 2 script run verbatim stops at line 255. A broken old assertion is not used as evidence. Instead I built `exports/reviews/PR-575-M4-round3-expected-checks.py` from the round 2 script with exactly three changes: the "already sent" message goes through the real `push_to_chat`; the REPRO becomes an expectation (not counted as sent, notify called once, the real report saved once, the outbox marked); and I added negative cases (a valid block written by the model, a broken block, a different key, a real report of another goal with the same key) and a case with a duplicate string before the real message plus 320 later messages. Result: 15/15 PASS on the fix; on the old head `ae1afff3` it is red exactly at the case where the chat text quotes JSON.

**Regression tests** (`test_resonance_mvp_feedback.py`, section "Review M4 round 2"), covering all four acceptance points: quoted JSON is not counted as sent and the drain sends the real report; a broken block, a different key, a block of another goal, and a block the model wrote itself are none of them counted; a duplicate string before the real message still recognizes the real message and does not replay it; keeps the case of more than 300 messages (now stored through `push_to_chat`) and the case of a crash between saving the message and marking the outbox.

**Mutations:** going back to string search, removing the receipt write, and removing the `goal_id` filter when looking up the receipt: all three turned the tests red. Removing the step that cross-checks the card block after having a receipt does not turn the tests red: it is a redundant layer of defense, because a receipt can only be written together with a message carrying exactly that block.

**Canary:** the first full JS run after `e34390c2` turned `test_mic_khong_tu_gui.js` red (176/177): the test pins the verbatim call `append_message(sid, "assistant", clean)` within the first 1400 characters of `push_to_chat`, but the receipt branch changed that call and pushed it too far. Fixed in `114f19a6`: the card-reading part moved out into `_resonance_card`, keeping the verbatim ordinary call; the canary's intent (push_to_chat only writes the assistant role) is unchanged.

**Limits:** receipts exist only for messages saved from this version on; M4 is not released, so there is no old data to migrate. If the user deletes a report message its receipt is deleted with it (foreign key `ON DELETE CASCADE`); this only affects an outbox row still hanging in the crash window, in which case the report is sent once more.

### Limits and what was not verified

1. **No UI button for `POST /goal-requests` yet.** The API exists and so do its tests; the user cannot yet click "pursue this message".
2. **Instructions cannot be edited in place.** They can only be dropped; to change a deadline or a target, drop the old one and state the new one in chat. Requests in words are not yet accepted to apply an instruction change automatically.
3. **"Needs changes" has no text field yet.** The user says the specific change in the chat frame; the API already accepts a `comment` if there is one.
4. **General undo is not part of the MVP**, as planned; the card only lets the user see the product and the history, and has no undo button.
5. **The Work page does not show goals yet** (spec 13 says the Work page shows goals being pursued); M4 only has the card in the chat frame and `GET /resonance/goals`.
6. **The card only appears in the web chat frame.** Telegram and Zalo receive text, and the card block is stripped like every control block.
7. **The Windows path limit** noted above.
8. **Still outstanding from M2 and M3:** the deadline policy, the text-only executor, one product per goal, the gap between the hash check and replacing the file, at-least-once notices on channels outside the report key, evidence kept for 90 days, and voice-lane background work.

### Full test run

| | Clean main (`7d264236`) | M4 branch (`4ae62efa`) | After review round 1 (`39fda1be`) | After review round 2 (`114f19a6`) |
|---|---|---|---|---|
| Python green | 387/403 | 397/412 | 396/412 | 397/412 |
| Python red files | 16 | 15 | 16 | 15 |
| New red vs main | | none | none | none |
| JS (`tests/run.py --js`) | | 177/177 (at `7c9776c6`) | 177/177 | 177/177 |

The 15 red files are exactly the list already red in the M1 section. The run after the review also had `test_write_path_phase9.py` red (the case `test_restart_marks_running_writes_unknown_without_rerunning`, the write path of the write invocation, not touching Resonance): run alone 3 times on the branch it was green once and red twice; run 3 times on clean main `7d264236` it was also green once and red twice. It is an existing flaky test.

## M5: a small improvement experiment (2026-10-07)

### Base and branch

- Branch `claude/resonance-mvp-m5` split from the M4 head that passed review round 3 (`79cfdfb4`), draft PR #579 stacked on #575. Version 0.85.2: `origin/main` has already reached 0.85.0 and PR #578 is holding 0.85.1.
- `origin/main` has moved on by many more commits relative to the base `7d264236`; not synced into the chain, for the same reason as in M3 and M4, adjusted once at merge time.
- The CI of #575 at `79cfdfb4` was already green 4/4 before M5 started.

### Design decisions for the reviewer to check

1. **The method is declarative configuration** (`METHODS` in `resonance.py`): each entry is just a fixed piece of text appended to the work prompt (`work.v1` the default, `work.checklist.v1` checking for completeness, `work.brief.v1` writing concisely). The model cannot add or edit any entry; no entry touches the criteria, the evaluator or the case set.
2. **`compare_methods(goal_id, baseline_ref, candidate_ref, cases, deps)`** (async, like `advance`). Before running, the host pins the yardstick: the automatically checked criteria of EXACTLY the current revision (dropping `path`, because the experiment does not publish a file) together with the answer key the host holds for each case, as `rubric_hash`. The baseline must be the method the goal is currently using; the candidate must differ from the baseline (exactly one change). The case set is 1 to 6 cases, and must include both a tuning set and a separate holdout set.
3. **The method does not see the answer.** The prompt for each turn is built with the real work turn's own `_work_prompt` function, with the user's words as the input of exactly one case; there is no earlier assessment, no old version, no answer key. The two sides of a case have identical prompts except for the method's text.
4. **The same resources, reserved up front.** `begin_experiment` reserves ALL the turns the experiment needs (2 x the number of runnable cases) in the same transaction, both within the goal's overall quota and within the exploration share (`EXPLORE_SHARE` = half the quota, accumulated across experiments, spec 11.2). If there is not enough, no experiment is created and the model is not called (`created: false`, `reason: explore_budget`). If the engine is blocked before the call, exactly that turn is returned; turns that have not started (stopped midway) are returned at settlement.
5. **No repeated outside effect.** Experiment output is only written in the work area (`outputs/<goal>/trials/<experiment>/`), and is not published into the brain. The evidence is tagged `trial_output`, so it is never counted as the goal's product (the goal's evaluator only reads `action_output`).
6. **The host grades with code** (`_grade`): every pinned artifact_contract criterion plus the case's answer key; an "achieved" self-declaration in the output has no value. A case only the user can grade (`expect.evaluator = human_confirmation`) is not run and is recorded as unknown.
7. **A narrow conclusion that favors the current method** (`_trial_verdict`): if the candidate drops in any comparable case, `rejected / regression`; if any case is unknown, `inconclusive / unknown` (unknown is never a win); better in at least one tuning-set case and not worse anywhere is `eligible`; everything else is `rejected / no_improvement`. Cost is NOT yet a winning criterion (see Limits).
8. **User intervention and a change of understanding take effect midway.** The experiment holds the goal lock for the whole run (it does not run concurrently with `advance`). The gate `_trial_gate` uses the SAME conditions for allowing execution as `advance` (the old guard latch, then `_gate`: active, switch, pause, "Not quite", guard tripped or undetermined, then revision) and is checked before reserving quota, before each turn, and after the last turn before concluding. If the revision changed it is `inconclusive / goal_reframed`; every other block is `inconclusive / stopped`. Old results keep their scope.
9. **Applying within existing authority, in the same settlement transaction.** Only `eligible` applies, and the method change happens INSIDE the `finish_experiment` transaction, after the store re-checks the CURRENT STATE: still active, the right revision, not paused, no guard latch, the latest understanding feedback of the revision is not "Not quite", and the current method is still the baseline. The flags `feature_off`, `fit_rejected`, `guard_unknown` are only results observed last time so they do not block here; their real conditions (the switch, the guard) are checked by the gate right before the transaction, and the gate clears those flags once the conditions have recovered. If blocked, the experiment settles as `inconclusive / stopped` and does not leave an eligible experiment unapplied. `GoalStore.apply_method` uses the same checks. The agent has no other path to change the method. The user goes back with `revert_method` (owner only, through `POST /goals/{id}/commands`).
10. **Application scope per revision** (`effective_method`): a learned method only runs on EXACTLY the revision it was checked on; an unchecked revision uses the DEFAULT method, and does not fall back to an earlier ref (an earlier ref may also only have won on an old revision). The revert ref (`method_prev_ref`) is the target of the revert command, not permission to run; it carries exactly its own checked revision (`method_prev_revision`), and reverting does not assign the current revision to the old ref.
11. **Every result is stored**, including losses: the `experiments` table keeps the revision, the method pair, the conclusion, the reason, each case for both sides, usage per side, the evidence and the scope; events `experiment_started`, `experiment_finished`, `method_changed`, `method_reverted`. The goal card (`goal_view`) has `method` and the three most recent experiments.
12. **No experiment just because it is time.** No path in the scheduler calls `compare_methods`. An interruption midway through an experiment is settled by `_reconcile`: the half-done turn becomes failed (not graded, not re-run), the experiment becomes `inconclusive / interrupted`, and the turns that had not started are returned.

### Results with the fake engine

`tests/python/test_resonance_mvp_trial.py`, 44 checks when first handed to review (58 after the fix round), with all five tests Task M5 named: `test_same_goal_and_rubric`, `test_holdout_not_visible`, `test_unknown_not_win`, `test_failed_candidate_not_applied`, `test_one_change_within_budget`. Added: an unknown method, a candidate identical to the baseline, a missing holdout set, Resonance off; output that declares itself achieved; a change of understanding midway; a human-graded-only case; a tie; the exploration share accumulating; the scheduler not creating experiments; the goal lock; a blocked engine; applying, scope per revision, revert for owner only; interruption and reconciliation. The case set is in `tests/fixtures/resonance/mvp_cases.json` (meeting minutes into a task list, a neutral domain).

Mutation tests (12): remove the regression rule, let unknown win, leak the answer into the prompt, not stopping when the revision changes, remove the exploration cap, apply without an experiment, a method not limited per revision, not settling an interrupted experiment, not holding the goal lock, not returning the turn when the engine is blocked, running even the human-graded-only case, accepting the self-declaration: all turned the tests red. The first time, the mutation "not stopping when the revision changes" slipped through because the final check at the end of the experiment also caught it; a separate check was added for the effect of the midway check (stopping after the running turn, returning the unrun turns).

### Fixes from the PR #579 review, round 1

The review did not pass, with 3 P1 bugs, reproducible with the fake engine and real SQLite. I agreed with all three.

1. **P1-1, the experiment ignored "Not quite" and a guard that had already tripped.** The top of the function only checked active, pause, the switch and the revision. Now it uses `_trial_gate` (item 8 above) before reserving quota and before each turn; if blocked, the engine is not called again and the turns that had not started are returned. The old guard latch is kept: a guard that has tripped blocks the experiment even if the protected file is back.
2. **P1-2, stopping during the last turn still applied.** The last check was before the last turn; after the last turn it only checked the revision and then applied, and the store layer did not check pause. Now the gate runs again after the last turn, and the method change happens inside the settlement transaction with the SQLite check (item 9). The brain switch is a file so it is checked by the gate right before the transaction; the gap between those two steps remains (see Limits).
3. **P1-3, the method chain went beyond the revision scope.** After two changes at revision 1, revision 2 fell back to the earlier ref (which also only won at revision 1). Now an unchecked revision uses the default method; the revert ref keeps its own checked revision (item 10).

**Regression tests** (`test_resonance_mvp_trial.py`, section "Review M5 round 1", 14 new checks, 58 in total): Not quite before the experiment; a latched guard; Not quite during the first turn (stops after 1 turn, returns 3); a guard tripping midway through the experiment; pause, switch off and Not quite right INSIDE the last turn (all 4 turns ran but it is not applied, and the experiment is saved as inconclusive); the store layer: settlement with applying while paused, `apply_method` when the understanding was rejected, and when the blocking flag is cleared by another path the "Not quite" event still blocks; a chain of two method changes and then moving to revision 2 (uses the default, the real prompt has no method's text); reverting at revision 2 and at revision 1.

**The reviewer's script:**
- Run verbatim: the first 3 PASS cases pass, and it stops at the first REPRO case (the experiment is now rejected). A broken REPRO assertion is not used as evidence.
- `exports/reviews/PR-579-M5-round2-expected-checks.py`: that script with the PASS cases kept verbatim and each REPRO changed into the correct expectation, checking the final state (number of calls, quota, method, the saved experiment). Result: 10/10 PASS. Running this same version on `abc4f3fe` is red at the first REPRO case.
- The new test file run on the code at `abc4f3fe` is also red at every P1-1 and P1-2 case (the P1-3 part does not get to run because the old store function lacks a parameter).

**Mutations** (8, on the fix): fall back to the earlier ref on an unchecked revision, reverting assigns the current revision to the old ref, drop the old guard latch in the gate, not re-checking before applying, the store not checking pause, the store not checking "Not quite", not checking the gate before each turn, not checking the gate at the start: all 8 turned the tests red. The first time, the mutation "the store not checking Not quite" slipped through because M4 sets the `fit_rejected` flag in the same transaction so the flag-based check caught it first; a case that clears the flag with `clear_block` was added to keep the event-based check layer.

The model pilot was not re-run (as required): the fix is in the gate, the transaction and the method scope, which can be checked deterministically. Pilot `6d54e859` did not apply any method so its conclusion does not change under the new rule.

### Fixes from the PR #579 review, round 2

Round 2 review confirmed the three P1 bugs are fixed, and found one P2 bug caused by the P1-2 fix itself: the apply transaction treats every `block_reason` among `feature_off`, `fit_rejected`, `guard_unknown`, `guard` as a latch still in effect. But `_gate` only WRITES those flags when it observes them, and does not clear them when the condition recovers (turning the switch back on, changing to "That's right"). The first gate lets it run, the experiment spends all 4 turns and wins, and then the final transaction rejects it because of an old flag.

**Fix (`ca8e1674`):**
- In the transaction, only a guard latch (which the user must reopen) is a hard block. "Not quite" is read from the LATEST feedback, not from the flag; pause, cancel, revision and baseline are still checked in the transaction as before.
- When `_trial_gate` lets it pass, `GoalStore.clear_transient_block` resynchronizes: it clears exactly the old observation flags by CAS on exactly the flag currently written; it does not touch a guard latch, pause, the waiting-for-user-review state or an exhausted quota.

**Regression tests** (section "Review M5 round 2", 8 new checks, 66 in total): the reviewer's two recovery cases (turn off and back on after `advance` writes `feature_off`; "Not quite" then "That's right") can apply and the old flags are cleared; the negative case "Not quite, That's right, then Not quite again" is rejected before spending a turn; the store layer: three old observation flags do not reject applying, a guard latch inserted before the transaction still blocks, the flag-clearing function does not touch a guard latch or waiting for review. The round 1 blocking cases (a guard latched after the file is back, stopping in the last turn, an intervention slipping in before the transaction) are kept as they are and still green.

**The reviewer's script:**
- `PR-579-M5-round2-checks.py` run verbatim on the fix: the 16 PASS cases still pass, then it stops at the REPRO case.
- `exports/reviews/PR-579-M5-round3-expected-checks.py`: that script with the 16 PASS cases verbatim, the REPRO case changed into the correct expectation (can apply, all 4 turns, the experiment saved as eligible, the flag cleared) and a negative case added that the final feedback is still a rejection. Result 19/19 PASS; run on `6c1e3bdd` it is red at the recovery case.
- The new test file run on the code at `6c1e3bdd` is also red at both recovery cases and the three old flag cases.

**Mutations** (4): turning the transient flag back into a latch, the gate not synchronizing the flag, the flag-clearing function touching even a guard latch and waiting for review, removing the guard latch in the transaction: all 4 turned the tests red.

### Real pilot

`tests/python/test_resonance_mvp_trial_pilot.py`, which only runs when `JAVIS_RESONANCE_PILOT=1`. Evidence: [`resonance-mvp-m5-pilot.json`](resonance-mvp-m5-pilot.json) (escaped JSON, no personal paths).

- **Commit:** `6d54e859`, `server/` tree clean. **Environment:** a temp `JAVIS_STATE_DIR`, copying only the engine selection fields, a temp brain, simulated data; the background engine currently selected is `anthropic-cli` / `sonnet` through `main._resonance_engine` (text-only, no fallback chain), and evidence through `main._RESONANCE_EVIDENCE`.
- **Scenario:** the goal "meeting minutes into a task list", quota 8 (exploration share 4). The experiment compares `work.v1` against `work.brief.v1` on t1 (tuning set), h1 and h2 (holdout; h2 can only be graded by a person).
- **Host results:** 4 real model calls, 24.4 seconds in total; all 4 receipts succeeded, the right provider that was selected, 0 tool calls, hashes match the files on disk; the evidence can be read back from the real EvidenceStore; nothing was published into the brain; it used exactly 4/8 turns, 4/4 of the exploration share.
- **Grading results:**
  - **Cases that passed:** t1 and h1 passed on BOTH sides.
  - **Unknown cases:** h2, not run, unknown on both sides.
  - **A losing candidate: NOT observed.** The initial prediction was that the concise version would lose by being too short; in practice the model wrote three concise lines that still covered the people and the deadlines. The conclusion is `inconclusive / unknown` (because of h2), not applied. Applying the grading rule to the real results of t1 and h1 (dropping h2, with no further model call) gives `rejected / no_improvement`: the candidate did not win so it is not applied, but that is not a regression case. The candidate-regression case (`regression`) is currently ONLY checked with the fake engine.
- **Usage reported by the engine:** the baseline about 36.3 thousand input tokens, 876 output tokens for 2 turns; the candidate about 36.4 thousand in, 203 out. Most of the input tokens are Claude CLI's background part, not the experiment's prompt.
- **The pilot exposed one thing:** the concise candidate was equal in quality but much cheaper in output tokens, yet the current conclusion rule does not treat a cost reduction as a win, so that candidate is never applied. Spec 11.1 allows acceptance on "meets minimum quality and reduces cost"; the MVP does not do this yet (see Limits).
- No further turn was run to try to reproduce a losing case: 4 of the maximum 5 allowed turns were already used, and the one remaining turn is not enough for a comparison pair.

### Limits and what was not verified

1. **The candidate-regression case does not exist on a real model yet**, only with the fake engine.
2. **Cost is not yet a winning criterion.** The conclusion is based only on quality by the pinned yardstick; equal quality but cheaper is still `no_improvement`.
3. **Nobody proposes experiments on their own yet.** There is no automatic path or UI button calling `compare_methods`; the case set and the method pair are supplied by the caller (tests, pilot). This is the plan's scope (one narrow comparison, no ExperimentService); the agent choosing which experiments are worth doing (spec 11.2) comes later.
4. **Three fixed methods.** There is no variant store and no new variants are created; adding a method means editing code with review.
5. **The goal card does not show the method and experiments yet**: the data is in `GET /goals/{id}` (`method`, `experiments`), but the UI does not draw it; the `revert_method` command exists in the API but has no button.
6. **One experiment per goal at a time** (the goal lock); a large experiment holds the lock for a long time and that goal's work turns wait.
7. **The brain switch is a file, outside the SQLite transaction.** The gate checks the switch right before the method-change transaction; if the user turns it off exactly in the gap between those two steps, the method still changes. This gap is short (no model call in between) and is like the gap between the hash check and replacing the file noted in M3.
8. **A learned method does not carry over to a new revision.** Each time the user adds clarification (a new revision), the goal goes back to the default method until it is compared again; nothing re-compares by itself.
9. **No code self-editing, groups, supervisor, time-series metrics or general undo**: outside the MVP, as planned.
10. The limits from M2 to M4 still remain.

### Checking against the MVP completion conditions

| Condition (end of plan 00-mvp) | Status | Basis |
|---|---|---|
| One request that needs pursuing goes through the whole loop on the real host: forming the goal itself, an action with a receipt, verification, continuing after an interruption, returning the result to the right session | **Met within the scenario** (technically and in content) | End-to-end pilot run 5 (2026-10-08, commit `0b6a4542`, [`resonance-mvp-e2e-pilot-5.json`](resonance-mvp-e2e-pilot-5.json)): through the real chat path, the Opus brain found `javis_goal` ITSELF through ToolSearch and formed exactly one achieve goal from a natural assignment; the first version and the revised version the brain wrote within the turn were accepted by the host with a written receipt; the goal stayed intact across a restart; feedback was attached to the same goal (revision 2); the notice came back to the right session with a receipt; confirmation through the API (simulated) made the goal achieved. 2 Opus turns, 0 Sonnet turns. One sample, which does not prove stable routing. The background path that revises the version on a real model was not used this time (the M3 pilot measured it separately). The content of the two versions was approved by the reviewer (after the fact, checked against the exact hash, see the [pilot file](resonance-mvp-e2e-pilot-plan.md), section "Content acceptance of run 5"). |
| Ordinary chat does not create background work; it does not force filling in SMART or confirming every goal | Met with the fake engine | M2: branching after the turn, no extra model call; not measured on a real brain. |
| Goal-fit and outcome are separate; it can say there is not enough evidence; human confirmation is neither wasted nor used out of scope | Met | M3, M4 and the three M4 review rounds. |
| One method change is tried on the same yardstick, applied only with enough basis within authority; usage and quota are recorded, and it can be stopped | Met, with limits | M5: the fake engine covers all branches; the real pilot covers the not-applied branch. There has not been any application (eligible) on a real model yet. |
| The report only claims the scope that was run | Ongoing | Each item above states whether it was the fake engine or a real model. |

**Current summary (2026-10-08):** end-to-end pilot run 5 met the technical and content bar within the scenario; it awaits an integration check on `main` before release. Scope: one real sample that went through the whole loop, the final confirmation is simulated through the API, and Sonnet was not run this time (the background path that revises the version on a real model has its own evidence in the M3 pilot). It is not a statistic of routing stability.

**History (kept as is, no longer the current status):** The M5 code review passed at round 3 (`d38d033a`); the MVP is NOT complete. The end-to-end pilot script through the real chat path for the first condition and the proposed quota are in [`resonance-mvp-e2e-pilot-plan.md`](resonance-mvp-e2e-pilot-plan.md); the runner `tests/python/test_resonance_mvp_e2e_pilot.py` has passed `dry` mode (14/14, 0 model calls). `real` mode has been run ONCE (run 1) within the quota the user approved: the brain chose `javis_task` (the correct current routing rule for one-off background work that needs approval) and did not form a goal, and the pilot stopped at 1/3 host-granted engine turns; the authentication method of that run was not independently verified. After the e2e review: the cap counts the goal framer too (the `call_ledger` book), an authentication gate and a settings check before sending the message, every acceptance condition is a hard error, and the scenario changed to the maintain kind; run 2 is waiting for the user's approval. The first condition is still not met.

### Full test run

| | Clean main (`7d264236`) | M5 branch (`1cc0395c`) | After review round 1 (`3c214c65`) | After review round 2 (`ca8e1674`) |
|---|---|---|---|---|
| Python green | 387/403 | 399/414 | 399/414 | 399/414 |
| Python red files | 16 | 15 | 15 | 15 |
| New red vs main | | none | none | none |
| JS (`tests/run.py --js`) | | 177/177 | 177/177 | 177/177 |

The 15 red files are exactly the list already red in the M1 section. The two new M5 files (`test_resonance_mvp_trial.py`, and `test_resonance_mvp_trial_pilot.py` which is skipped when `JAVIS_RESONANCE_PILOT=1` is not set) are both green.
