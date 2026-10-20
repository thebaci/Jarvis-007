# Fast Mode Engine Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the composer's Fast mode bolt (`settings.model.fast`, stored since 0.153.0) actually switch each brain to its fast tier, fall back cleanly when a provider refuses, and show the last real state in the bolt tooltip.

**Architecture:** One new module `server/fast_mode.py` holds the support matrix, the per-provider parameters, refusal detection, a `ContextVar` with the current turn's choice, and the last observed state per brain. The two chat entry points (dashboard turn, Telegram turn) set the `ContextVar` next to where they read `reasoning`; engines read it where they already add the thinking level. Background runs (loops, kanban, teams, voice) never set it, so they keep running at the normal tier, exactly like the thinking level today.

**Tech Stack:** FastAPI server (server/main.py, server/engine.py, server/claude_sdk_engine.py, server/codex_models.py), vanilla JS dashboard (dashboard/model-picker.js), node and Python test scripts.

**Spec:** docs/superpowers/specs/2026-10-15-composer-plus-fast-mode-design.md (section "PR 2: wire Fast mode into the brain")

## Global Constraints

- All code, comments and test names in English; user-facing strings through i18n (vi with diacritics, en). Never use the em dash.
- Never send a parameter a model does not declare (spec): Claude only Opus 5.5, Opus 5, Opus 4.8 or the default/`opus` alias; Codex only models whose `serviceTiers` list `priority`.
- Bolt off sends nothing, except Codex, which forces the normal tier (`service_tier="default"`), because some Codex models default to `priority` and the owner's `~/.codex/config.toml` sets `service_tier = "priority"` (owner approved).
- A refusal (400 naming the parameter, or 429/529 for Anthropic speed) retries once without the fast parameter; the turn never fails because of Fast mode.
- Values: Claude Code `ClaudeAgentOptions(settings='{"fastMode": true}')`; Anthropic API header `anthropic-beta: fast-mode-2026-02-01` + body `"speed": "fast"`; Codex `-c service_tier="priority"` / `"default"`; ChatGPT OAuth Responses `service_tier: "priority"`; OpenAI API `service_tier: "fast"`; OpenRouter and Gemini `service_tier: "priority"`; Grok, Antigravity, Groq, DeepSeek, Ollama: nothing.
- Version: next free number above main and open PR titles. Bilingual CHANGELOG.

## Review Focus

- A provider rejects the fast parameter mid-stream (status 400 before any token): the turn must retry without it and answer normally. Tests in Task 3 and Task 4.
- Bolt off with a Codex model whose default tier is `priority`: the turn must carry `service_tier="default"`. Test in Task 2.
- A background run (loop, reminder) while the bolt is on: it must not get fast parameters (no `ContextVar` set). Test in Task 1.
- A Claude model that is not Opus 5.5/5/4.8 (e.g. Sonnet) with the bolt on: no `fastMode` setting. Test in Task 2.
- Claude reports `fast_mode_state = cooldown`: the bolt tooltip says Fast mode is temporarily off. Test in Task 5.

---

### Task 1: `server/fast_mode.py` (pure helpers, ContextVar, state store)

**Files:** Create `server/fast_mode.py`; Test `tests/python/test_fast_mode.py`

**Interfaces (produced):**
- `CURRENT: ContextVar[bool]` (default False); `use(on: bool) -> token`; `current() -> bool`
- `claude_supports(model: str) -> bool`
- `claude_sdk_settings(model: str, on: bool) -> str | None` (JSON string or None)
- `anthropic_params(model: str, on: bool) -> tuple[dict, dict]` (extra headers, extra body)
- `compat_params(provider: str, on: bool) -> dict` for "openai", "openrouter", "gemini"
- `responses_params(on: bool) -> dict` for ChatGPT OAuth
- `codex_override(model: str, on: bool, tiers: list[str]) -> str | None` (`service_tier="priority"` / `service_tier="default"` / None when the model has no priority tier and the bolt is on)
- `refused(status: int, text: str, key: str) -> bool` (400/422 mentioning key; for key "speed" also 429/529)
- `remember(provider: str, state: str, reason: str = "")`, `states() -> dict`

- [ ] Step 1: write `tests/python/test_fast_mode.py` covering every function above (support matrix incl. "opus", "", "claude-opus-5-5", "claude-sonnet-5-5"; off returns empty; ContextVar default False and reset; refused matrix; codex override for on/off/no-tier).
- [ ] Step 2: run, expect ModuleNotFoundError.
- [ ] Step 3: implement.
- [ ] Step 4: run, expect all pass.
- [ ] Step 5: commit.

### Task 2: CLI brains (Claude Code SDK, Codex)

**Files:** `server/main.py` (`_cli_do_sau`, `_codex_do_sau`, the two turn entry points), `server/claude_sdk_engine.py` (`_options`, stream state), `server/codex_models.py` (keep service tiers, `tiers_for(model)`); Test `tests/python/test_fast_mode_cli.py`

- `_cli_do_sau(cli, reasoning, message)`: also `cli.fast_settings = fast_mode.claude_sdk_settings(getattr(cli, "model", ""), fast_mode.current())`.
- `ClaudeSDK._options()`: when `getattr(self, "fast_settings", None)` and `"settings" in fields`, `kw["settings"] = self.fast_settings`.
- Stream: read `fast_mode_state` / `fast_mode_disabled_reason` from the init SystemMessage data and the ResultMessage when present, `fast_mode.remember("anthropic-cli", state, reason)`.
- `codex_models._normalize_items` keeps `service_tiers` (ids) and `default_service_tier`; `tiers_for(model)` reads the cache filled by `list_models`.
- `_codex_do_sau`: before the early return, add `fast_mode.codex_override(...)` to `cli.extra_config` (replace an existing `service_tier=` entry).
- Turn entry points (dashboard after `reasoning = _reasoning_level(mcfg)`, Telegram the same): `fast_mode.use(mcfg.get("fast") is True)`.
- Tests: `_options()` with/without fast and Sonnet; `_codex_do_sau` adds priority/default; existing `test_do_sau_suy_nghi` exact `extra_config` asserts keep passing (they run with the bolt off: update only if the forced `default` entry appears, by asserting the reasoning entry is present).

### Task 3: Anthropic API

**Files:** `server/engine.py` (`anthropic_stream`, `anthropic_chat_with_mcp`); Test `tests/python/test_fast_mode_api.py`

- Merge `fast_mode.anthropic_params(model, fast_mode.current())` into headers and payload; on a refused response (`fast_mode.refused(status, text, "speed")`) drop them once and retry; `remember("anthropic-api", "on" | "fallback", reason)`.
- Tests with a fake `httpx.AsyncClient` (monkeypatch in engine): first call 400 "does not support the `speed` parameter", second call OK; assert the retry has no `speed` and no beta header, and that the bolt off sends neither.

### Task 4: OpenAI-compatible and Responses

**Files:** `server/engine.py` (`_openai_compat_stream`, `openrouter_stream`, `_cc_tool_loop` callers `openai_chat_with_mcp`/`gemini_chat_with_mcp`/`openrouter_chat_with_mcp`, `openai_responses_stream`, `responses_with_mcp`); Test in `tests/python/test_fast_mode_api.py`

- Add `fast_mode.compat_params(provider, current())` / `responses_params(current())` next to the reasoning parameter; on `refused(status, text, "service_tier")` retry once without it.
- Tests: payload contains the right value per provider when on, nothing when off; refusal path retries without it.

### Task 5: Bolt tooltip reads the real state; release

**Files:** `server/main.py` (`GET /model/fast-state` returning `fast_mode.states()`), `dashboard/model-picker.js` (drop the `fast.pending` line, append a state line), i18n vi/en (`fast.state_cooldown`, `fast.state_fallback`, `fast.state_reason`), `tests/js/test_tia_set_fast.js`, route table, docs/10 (vi/en) Fast mode section, VERSION, CHANGELOG.

- Tooltip: `"Fast mode\n" + note + (state line when the provider's last state is cooldown/fallback/off with a reason)`.
- Verification: full JS suite, related Python files, one real Codex turn with `-c service_tier="default"` and one with `"priority"` (`codex exec` with a one-word prompt) to confirm both are accepted, sandbox visual check of the tooltip.
