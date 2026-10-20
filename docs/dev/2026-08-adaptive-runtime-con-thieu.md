# What is still missing to reach the original goal

> **Status: all 7 items in section 4 are DONE** (2026-08-02). Section 3 is kept as the original
> analysis so it can be checked against, with three corrections at the end of the document for
> places where the first version blamed the wrong cause. See section 6 for what really changed.

Goes with `2026-08-adaptive-context-runtime-spec.md` (what to build) and
`2026-08-adaptive-runtime-trien-khai.md` (how to roll it out).

This document re-examines the 12 phases from the angle of the **original goal**, not from the
spec's angle. The original goal is not abstract performance, it is very concrete: the free Groq
on_demand plan with `llama-3.3-70b-versatile` allows 12,000 tokens per minute, while a single
Jarvis 007 turn sends 21,446 tokens, so it gets blocked before it can answer.

## 1. Breakdown of the 21,446 tokens, re-measured today

| Block | At diagnosis time | Today | Has any phase touched it yet |
|---|---|---|---|
| `CLAUDE.md` as the system prompt | 21,479 characters | 21,479, unchanged | Yes, Phase 8 |
| `Memory/MEMORY.md` | 18,723 characters | capped at 20,000 | Yes, `memory_canary` |
| 30 skills + dynamic context | ~5,400 characters | capped by `SKILL_LIST_MAX` | Yes, `lazy_skill_canary` |
| **26 MCP/tool schemas** | **17,161 characters** | still intact | **Not yet. See section 3.1** |

## 2. The architecture that is really done

This is the good news, and it needs saying clearly so nobody redoes it:

- **Replace the system prompt with a compiled capsule.** `build_adaptive_source_prompt`
  deliberately does **not** wrap `CLAUDE.md`. When `context_sources` is on, the core prompt is the
  Context Compiler's `CORE_CONTRACT`. Measured for real: **724 characters (~207 tokens) in place of
  26,505 characters (~7,573 tokens), a 97% reduction** for this block alone.
- **TPM is real, not a blank.** `context_runtime.py:1031` has a 60-second sliding-window
  admission, atomic, fail-closed when the limit is unknown. All 5 canary paths pass
  `rolling_tpm` down to the Context Compiler, and the compiler feeds it into the budget formula
  together with `context_window` and `output_reserve`.
- **Evidence Store** so tool result JSON is not resent on every round.
- **Per-step Model Router**, with hard filtering by capability, context window, deadline and cost.

In other words: **the architecture solves the Groq problem. It is just switched off.**

## 3. What is genuinely still missing

### 3.1 Tool schemas never entered the lazy layer (the biggest hole)

This is what the owner pointed out directly in the original chat, and **the 12 phases did not
touch it**.

`mcp_hub._apply_lazy` only hides tools that come from an MCP connector:

```python
pool = [t for t in tools_spec if (route.get(t["fn"]) or {}).get("conn")]
# Builtins + plugin (entry has 'call', not 'conn') are ALWAYS shown directly
```

Add the default `lazy_threshold: 40`, while this machine has 26 tools, and **lazy has never
once activated**. All 17,161 characters of schema go straight into every request, for every
model.

This is the second biggest block after `CLAUDE.md`, and more important than that: **fixing it
takes effect immediately on the legacy path that is running today, with no canary needed.**
Everything else in the 12 phases has to wait for a rollout before it does anything. This one
does not.

### 3.2 Nobody has declared the Groq limits, so every safeguard fails closed into uselessness

`quota_profiles` defaults to `[]`. Fail-closed means a missing profile falls back to legacy.

The ironic result: the machine built to rescue Groq, when it meets exactly the Groq situation,
**does nothing** because it does not know how limited Groq is. `config.py:136` already has the
template (`"rolling_tpm":12000, "context_window":131072`), nobody has just filled it in.

### 3.3 Fail-closed runs in the opposite direction from the TPM problem

When the compiler sees `estimate.input_tokens + reserved > rolling_tpm_remaining`, it adds the
reason `rolling_tpm` and returns **legacy**. But legacy is exactly the path that sends 21,446
tokens.

That is: detect that "this request is too big for the limit" and react by **sending an even
bigger request**. For the read path, failing closed to legacy is right. For the TPM constraint
it points the wrong way.

The original requirement says what to do: *"If it still exceeds, switch to another engine or
report that the model needs to change. Do not send a request that is certain to exceed TPM and
only then let Groq return the error."* The "switch engine or report" part has not been built.

### 3.4 Nothing guards the size of the core prompt

**A correction to a false claim in the first version of this document:** the first version said
`CLAUDE.md` had grown 23%, from 21,479 to 26,505. Wrong. That compared **bytes** with
**characters**: `wc -c` returns 26,505 bytes, while `len()` returns 21,479 characters, and the
original diagnosis counted characters. Vietnamese with diacritics takes more than one byte per
character. `CLAUDE.md` **did not grow at all, it is unchanged**.

But the conclusion stands, only the reason changes: nothing guards it. No test, no warning. That
it has not drifted so far is luck, not a guardrail.

As long as Phase 8 is not on, every line added to `CLAUDE.md` is a tax on every chat turn of
every model, and nobody sees that tax grow.

### 3.5 No `capability_index.py` yet, only keyword

The registry uses FTS5, which is **keyword only**. The original plan asked for hybrid: keyword
plus semantic plus graph, with dynamic widening when confidence is low.

With a few dozen capabilities, keyword is enough. But the repo owner's stated goal is "plug in
many more MCPs, models and workflows later". By then a keyword resolver will start missing
silently, and `miss_class` on the Diagnostics page is where you will see it before it becomes a
problem.

This is a quality risk when scaling, not a bug today.

### 3.6 Modules per the original plan: present, merged, and missing

- Separate and present: `capability_registry`, `capability_resolver`, `context_compiler`,
  `evidence_store`, `model_router`.
- Merged into other places, acceptable: the quality gate sits inside `context_compiler`; task
  state and orchestrator sit inside `context_runtime` plus `readonly_orchestrator`; the policy
  engine is spread across the resolver and executor.
- **Truly missing:** `capability_index` (section 3.5) and `quota_scheduler` as a shared service.
  TPM is currently computed in `context_runtime`, enough for each canary path, but nobody
  coordinates the quota **across** chat, loops, background tasks and reminders. Those four
  sources eat the same Groq quota without knowing about each other.

## 4. Supplementary plan

Ordered by the principle: whatever takes effect earliest and is cheapest goes first.

### Item 1: Bring builtins and plugins into the lazy layer, lower the threshold

**Why first:** this is the only thing that takes effect **right now on the legacy path**, with no
canary to turn on and no baseline to wait for. Aim to cut about 17,000 characters down to a few
thousand.

- Widen `pool` in `_apply_lazy` to accept builtins and plugins too, keeping a small group of core
  tools always visible: find tool, run tool, read file, and the mandatory session tools.
- Lower `lazy_threshold` to a level that makes it actually activate on the current config.
- The core group must be **declared as an explicit list**, not inferred from whether `conn` is
  present. Implicit inference is exactly what caused this hole.
- Guardrail: a two-way cross-check test, every core tool must really exist in the route, so that
  renaming a tool and forgetting to fix the list turns CI red instead of breaking silently.

Acceptance: measure total schema characters before and after on the same config. Plus a test
guarding the ceiling: the total schema sent must not exceed the declared threshold.

### Item 2: Guard the core prompt size

A test that reads `CLAUDE.md` and fails when it exceeds the declared budget. Plus one line in the
docs saying this is a tax on every chat turn. Cheap, and it blocks exactly the kind of drift that
went on through eight phases.

### Item 3: A safe endpoint to set the canary, and recursive merge

Already described in section 3 of the rollout document. It must come before Item 4, because
otherwise declaring the Groq limits by hand would hit the one-level merge trap and
`quota_profiles` would silently disappear.

Changing `read_settings()` to merge recursively is the most important part here.

### Item 4: Declare the real quota for Groq and the models in use

No code, only data, but it must come after Item 3. Fill in `rolling_tpm`, `context_window` and
prices. This is what unlocks the whole machine that was built.

Acceptance via the Diagnostics page: `quota_rules` is non-zero.

### Item 5: Fix the fail-closed direction for the TPM constraint

When the reason for rejection is `rolling_tpm`, it must not fall back to legacy. Three rungs, as
the original requirement says:

1. Compress harder: drop low-value context items and compile again.
2. If it still exceeds, switch provider via the Model Router, based on each model's real quota.
3. If that still fails, **tell the user**, with the estimated figure and the limit, and suggest
   changing model.

Never silently send a request that is certain to exceed.

Acceptance: build a fake model with a very small `rolling_tpm`, assert the system does **not**
call that provider, and assert it does not fall back to legacy.

### Item 6: A shared `quota_scheduler` for every source

Chat, loops, background tasks and reminders currently eat the same quota without knowing each
other. Gather TPM and RPM accounting into one place, and every model call path asks permission
through it.

Not urgent with a single user, but it becomes urgent the moment a loop runs in the background at
the same time as a chat.

### Item 7: Hybrid `capability_index`

Add semantic and graph next to keyword, with dynamic widening when confidence is low. Do it when
`miss_classes` on the Diagnostics page shows the resolver starting to miss, not before.

This protects **quality** as the number of capabilities grows, and it is the condition for the
promise "plug in as many MCPs as you like" to hold.

## 5. Order and reasons

Items 1 and 2 are independent of the whole canary topic, can be done now, and take effect today.

Items 3, 4, 5 are a chain that must go in order, and they are what actually makes Groq work.

Items 6 and 7 are about scaling, done when the Diagnostics page gives a signal, not on a hunch.

The point to remember: after 12 phases, what blocks Groq today is **not a missing architecture**,
but one block of tool schemas nobody put into the lazy layer, plus one line of quota
configuration nobody filled in.

## 6. What was done, and three places this analysis was wrong

### 6.1 Measured results

| Block | Before | After |
|---|---|---|
| Tool schemas sent per turn (26 tools, 30 skills) | 11,994 characters | **2,001** (down 83%) |
| System prompt on the compiled path | 21,479 characters | **724** (down 97%) |
| Fixed cost of the compiled path | - | **~772 tokens**, about 11,200 left under the Groq limit |

The tool schema reduction takes effect **right on the legacy path**, with no canary to turn on.

### 6.2 The seven items

1. **The lazy layer accepts builtins and plugins too.** The pool is no longer implicitly derived
   from `conn` but declared explicitly through `CORE_TOOL_FNS`. Added a SIZE threshold next to the
   count threshold, because counting tools says nothing about cost.
2. **Prompt budget guard** via `test_prompt_budget.py`: three ceilings plus one total check that
   must fit the free Groq limit.
3. **Recursive config merge** (kills the silent `quota_profiles` loss trap) plus
   `POST /runtime/canary` and a Set button on the Diagnostics page.
4. **`model_limits.py`** - suggested limits with their source noted, `POST /runtime/quota`, a
   Declare button.
5. **Fail-closed direction** for the budget constraint: refuse and say so, with the numbers and a
   way out.
6. **`quota_scheduler.py`** - a shared TPM ledger, hooked into `usage_store.record` so it covers
   every source.
7. **`capability_index.py`** - RRF fusion, dynamic widening, source affinity.

### 6.3 Three corrections

Recorded because they show where an analysis that reads code without running it goes wrong.

- **`CLAUDE.md` did not grow 23%.** The first version compared `wc -c` (26,505 **bytes**) with
  the original diagnosis figure (21,479 **characters**). Vietnamese with diacritics takes more
  than one byte per character. The file is unchanged. The guardrail is still needed, but because
  there never was one, not because it drifted.
- **The fast path and readonly path are NOT wrong-direction fail-closed.** They have refused and
  said so from the start. The wrong-direction path is Phase 8, and it is the most important path
  for the Groq problem.
- **TPM is not "a blank".** The 60-second sliding-window admission is real and fails closed
  correctly. The hole is that only 4 canary paths go through it, while 10 other places that call
  a model do not.

### 6.4 Still not there

- Production baseline, gold benchmark. No code can replace them, you have to run shadow and then
  read the Diagnostics page.
- Real embeddings for `capability_index`: the fusion framework is ready but no adapter is
  configured yet, so the semantic part is always empty and fusion falls back to exactly the
  lexical order.
- The limits in `model_limits` only cover Groq so far. Other providers return empty, and that is
  deliberate.
