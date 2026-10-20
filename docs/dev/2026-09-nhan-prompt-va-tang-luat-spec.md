# Plan: Multiplying the prompt with a frozen ceiling and a rule layer per carrier

> Dev plan, written 2026-09-22 on top of the v0.63.0 code. Goal: end the cycle where
> `CLAUDE.md` swells to the ceiling and then the ceiling gets raised, by changing **where rules
> are written** rather than how rules are compressed.

## Read this if you only have 2 minutes

1. `CLAUDE.md` has **23 characters** left before it hits the CI ceiling. That ceiling has already
   been raised once.
2. The cause is not "too many rules". The cause is that **writing prose into `CLAUDE.md` is the
   cheapest way to force the model to behave**, so every rule flows there. Clearing space without
   fixing that just means the space fills up again.
3. The evidence is already in the repo: scheduling **has its own tool**, so it costs only ~600
   characters of prose; creating an agent **has no tool**, so it costs 2,875 characters for a
   simpler job.
4. So the direction is: **turn rules into tools and code**, not compress rules more cleverly.
5. Three constants keep it from drifting back: the core holds only what belongs to Jarvis 007's
   **personality**, the core ceiling is **frozen and cannot be borrowed against**, and every rule
   must declare **who is enforcing it**.

---

# Part 1: What is happening

## The numbers

```
CLAUDE.md          33,577 characters
CI ceiling         33,600 characters   (tests/python/test_prompt_budget.py)
Remaining              23 characters
```

Running `python tests/run.py prompt_budget -v` at the time of writing:

```
ok  CLAUDE.md under the 33,600 character ceiling   [now 33,577 characters, 23 left]
ok  CORE_CONTRACT under 2,000                      [now 740 characters]
ok  the compiled path is at least 10x smaller than legacy
    [CORE_CONTRACT is 2.2% of CLAUDE.md, saving 98%]
```

The comment right above that ceiling was already written for this moment:

> "The NEXT time the ceiling is hit, cut for real or move one section into a skill, do not
> raise this number again."

The ceiling has already been raised once (`33,600 (0.50.0): raised the ceiling instead of cutting`).
So the real question is not "raise it by how much" but **why it is always full**.

## Where this file goes

`server/main.py:351-352` reads `CLAUDE.md` at the repo root as `SYSTEM_PROMPT`, and
`build_system_prompt()` (`main.py:755`) makes it the base for **every chat turn on every engine**.

For subscription-plan engines, `_subscription_system_prompt` (`main.py:12110`) deliberately keeps
`CLAUDE.md` as it is. The reason is recorded at `main.py:12117`:

> "dropping CLAUDE.md to save tokens is a bargain when TPM is tight and every token costs money.
> On a subscription plan, tokens are not billed"

That argument is right about **money** and wrong about **time**. A subscription plan does not bill
per token, but 33,577 characters still cost exactly the same processing time on every turn.

The third line in the test output above deserves attention: the compiled path has **already
proven** that a 740-character core prompt works. It only applies to API engines. This plan does
not follow the CORE_CONTRACT direction (dropping `CLAUDE.md` altogether would drop Jarvis 007's
personality with it), but that number is evidence that most of those 33,577 characters are **not
things that must be present on every turn**.

---

# Part 2: Why the file keeps swelling

## It is a scar tissue store

Almost every rule in `CLAUDE.md` carries an incident date: "owner reported 2026-08-13", "incident
of 13/09/2026", "incidents on 2026-07-19 and 2026-08-16", "customer reported 2026-08-30".

The file grows steadily by one rule per incident, and never shrinks. That is a good learning loop,
but it is a **learning loop with no mechanism for forgetting**.

## But the deeper cause is price

The right question: why does every rule flow into exactly one file?

| Where the rule is written | Time | Who can do it |
|---|---|---|
| Add a paragraph to `CLAUDE.md` | ~5 minutes | Anyone, even through chat |
| Write validation in code | ~2 hours | Needs a programmer |
| Write a new tool | ~1 day | Needs a programmer |

`CLAUDE.md` is not a design choice. It is the **path of least resistance**. Under time pressure,
every rule rolls down to the low spot.

The consequence has to be stated plainly, because it rules out two options that sound obvious:

> **Any plan that clears space but leaves the slope in place will see the space fill up again.**

Raising the ceiling buys a few more months. Compressing with a retrieval layer buys a year or two,
in exchange for a new system that has to be maintained. Neither touches the slope.

## And why retrieval is not the answer

Recorded here so the next version does not walk this road again.

The argument "per-turn cost is O(top-k), so the total number of rules can grow as much as we like"
fails because **k is not a constant**.

The number of rules relevant to ONE action grows with system complexity. Today, creating an agent
requires knowing 6 rules. When Jarvis 007 has 20 engines, 50 connectors and 5 channels, it needs
those 6 rules **plus** the interaction rules: this engine writes files differently from that one,
this channel does not render markdown, that connector needs different permissions. The number of
interacting pairs grows with the square of the surface.

Retrieval gives a **better constant factor**, not **unboundedness**. To get unboundedness you need
a mechanism that makes rules **disappear**, not one that makes them cheaper to carry.

---

# Part 3: Evidence inside the repo

The repo has already run this experiment; nobody has read the result yet.

Two capabilities, same complexity, differing in exactly one thing:

| Capability | Has its own tool | Prose in `CLAUDE.md` |
|---|---|---:|
| Scheduling, reminders, loops | **Yes** (`javis_schedule`) | **~600 characters** |
| Creating agents, workflows | No | **2,875** |
| Creating plugins | No | **2,114** |
| Writing long-term memory | No | **2,297** |

Scheduling is **more complex** than creating an agent: it has cron, three permission levels, two
storage locations, and preconditions. But it costs only ~600 characters of prose, because its
rules live in the tool contract (`system/plugins/javis-schedule/plugin.py:583`, a description of
~1,900 characters).

And more importantly: that tool **sits in the lazy pool**. `mcp_hub.py:837` defines the pool as
every tool except `CORE_TOOL_FNS` (`mcp_hub.py:598`, which holds only `javis_read_file`,
`javis_list_dir`, `javis_write_file`). So those 1,900 characters enter the context only when the
model actually needs to schedule something. A revenue question pays 0 characters for it.

> **The mechanism "rules travel with the capability, loaded lazily on demand" already exists, already
> runs in production, and has already been measured (tool schema 11,994 characters down to 2,001,
> an 83% reduction). `CLAUDE.md` is the only thing standing outside it.**

That is why this plan **does not build a new retrieval layer**. It brings `CLAUDE.md` into the
mechanism that is already running.

## The process gap

`javis_schedule` has existed for a long time, yet the Orchestration section in `CLAUDE.md` still
holds 8,888 characters describing those same rules again.

**Adding a tool does not automatically remove prose.** No field, no test, no process says "this
rule is now enforced by code, delete it from the prompt". That is the slope, and it is the thing
to fix first.

---

# Part 4: Six real defects found in the survey

All self-verified against the code. The first three are the premise of the plan.

## 4.1. Two constants contradict each other, and Antigravity pays for it

This defect only shows up when you put two numbers from two files side by side.

- `compaction.AGY_BOOTSTRAP_MAX_CHARS = 100_000`: the history re-sent every turn
- `antigravity_cli._tran_argv()`: the command-line ceiling, **120,000 bytes** on Linux

**Real measurements (2026-09-22), not estimates:**

```
bytes-per-character ratio for Vietnamese (measured on docs/dev)   1.202
build_system_prompt (sample brain)                                37,767 characters
+ channel block                                                    8,412
= REAL SYSPROMPT                                                  46,179 characters
```

> **Correction to the first draft:** the first draft estimated the sysprompt at "~36,000". The
> real figure is **46,179**, 28% higher. The channel block alone is 8,412 characters, far more
> than a block assembled into every turn should be - worth its own look, but not part of this
> batch.

Applied to the budget `120,000 x 0.97 / 1.21 = 96,198 characters`:

| Scenario | Sysprompt | History | Total | Result |
|---|---:|---:|---:|---|
| Before the fix | 46,179 | 100,000 | 146,179 | **Badly over** |
| Only lower history to 80,000 | 46,179 | 80,000 | 126,179 | **STILL over** |
| **After the fix (this batch)** | 46,179 | **45,000** | 91,179 | **fits** |

### What happens over the ceiling, stated at the right strength

> **Second correction, more important.** The first draft wrote "going over the ceiling means the
> prompt must go through a context file, adding an inference round". Reading `_chon_duong`
> carefully during implementation, that is NOT what happens:
>
> ```python
> if do_dai <= _tran_argv():
>     return "argv"
> return duong_prompt_dai(self.cli_path)   # -> "stdin:<recipe>" OR "file"
> ```
>
> Over the ceiling, it tries **stdin first**, and stdin has no ceiling. Only a machine where no
> stdin recipe works falls through to the file path. So the 30-60 second cost belongs to ONE GROUP
> OF MACHINES, not to every turn as the first draft said.

The benefit of lowering this constant therefore has two parts, and the second part is the certain
one:

1. **Machines on the file path:** saves one tool round per turn.
2. **All machines on the file path:** a shorter file means the file-reading tool truncates it less
   often. This is a bug that **has been reported** (2026-09-18/19): the model read the first half
   of the file and answered an old question. The previous reduction (300,000 down to 100,000) was
   for the same reason, and 100,000 is still long enough to trigger it.

### Trade-off

`agy` **does not resume a thread**, so this history bundle is its entire conversational memory.
Lowering to 45,000 characters is roughly 20-30 ordinary chat turns. `bootstrap_prompt` keeps the
**most recent** part and does not cut `summary`, so what falls off is the oldest turns, not
random ones.

In return, it no longer answers the wrong old question. For a bug someone has already reported,
that trade goes in the right direction.

### On Windows it is hopeless

The ceiling is **30,000 UTF-16 units**, so the 46,179-character sysprompt alone does not fit no
matter how far history is lowered. The argv path is dead there; the right path is stdin, and
`duong_prompt_dai` already prefers it. Recorded so nobody optimizes in the wrong direction.

## 4.2. The `pre_tool_call` hook blocks nothing

`plugins_host.py:755` wraps every tool call:

```python
async def _wrapped(args):
    await _fire("pre_tool_call", vault_root, {...})   # return value ignored
    result = await base_call(args)                     # called regardless of what the hook says
```

And `_fire` (`:746`) swallows exceptions too. So the hook is currently **observe-only**: it cannot
veto and cannot rewrite parameters. The docstring at `:369` promises it fires "around EVERY tool
call", so it is easy to assume it is a gate; it is not.

Part 8 will show this is not a small bug: **it decides whether the whole plan pays off at all.**

## 4.3. The 21st skill onward is invisible to the router

`skill_router.py:49` sets `SKILL_LIST_MAX = 20`. `_skill_router_block` cuts there and writes
`…(+N more skills - see Javis/index.md)`. The model does not read that file unless told to, so
the 21st skill onward is **never routed**. A brain that has been used for a while will certainly
exceed 20.

## 4.4. `_fit_memory_index`: OVERSTATED, now corrected

> **Correction 2026-09-22, after reading the code carefully during implementation.** The first
> draft of this document called this "the last step is losing memory", based on the function's own
> docstring ("Losing the line entirely is losing memory"). The real code is milder: the last step
> does cut lines from the PROMPT, but it **counts the lines cut and says so**, with a way
> forward:
>
> ```
> (The index is too long, so {N} memories are not listed here.
>  Read memory/MEMORY.md for the full list, and memory/facts/ for details.)
> ```
>
> No memory is lost from DISK, and the model knows something is missing. This is not a silent
> failure, so it does NOT belong in the "real defects" group and is not to be fixed in this batch.

What remains true: `MEMORY_INDEX_MAX = 20000` (`main.py:523`) is that large because the index
carries detailed descriptions too. Splitting the index from the details (Contract 7) is still
worth doing, but for **compactness and cost**, not because "memory is being lost". Re-prioritize
accordingly.

## 4.5. `build_system_prompt` re-running every turn: WRONG NUMBER, re-measured

> **Correction 2026-09-22.** The first draft wrote "~40 ms blocking the event loop". That number is
> the **acceptance threshold** in `bench_hotpath.py`, not a measurement. Running
> `python bench_hotpath.py` for real:
>
> ```
> build_system_prompt   baseline 150.8 ms -> now 3.9 ms   (target < 60)
> ```
>
> **3.9 ms.** This optimization has already been done, from 150.8 down to 3.9. What remains is not
> worth trading for the risk of the cache returning a stale copy, and above all not worth ignoring
> the two side effects on DISK that this function carries (`system_sync.ensure_synced` and
> `mirror_skills` - Claude Code relies on that mirror to see skills).

**Conclusion: drop "pre-built core keyed by signature" from the roadmap.** The CPU reason is gone.
The remaining reason (a byte-identical prefix for the prompt cache) is not enough by itself to
build another signature-keyed cache layer, especially since the CLI path does not use Jarvis 007's
prompt cache.

The more general lesson, worth recording more than the patch: **an acceptance threshold in a bench
file is not a measurement.** Confusing the two means building an entire work item on a number
nobody ever measured.

## 4.6. The 1-hour cache: WRONG RECOMMENDATION, checked against the docs and withdrawn

`engine.py:320` has a `cache_ttl` parameter that takes `"5m"` or `"1h"`, and its only call site
(`engine.py:716`) passes nothing, so it is always 5 minutes. The first draft of this document
proposed "pass `cache_ttl='1h'`, a one-line fix".

> **Correction 2026-09-22, after checking the Claude API documentation instead of writing from
> memory.** The syntax is right and needs no beta header. But the ECONOMICS are the other way
> round:
>
> - A cache write costs **1.25x with the 5-minute TTL**, and **2x with the 1-hour TTL**.
> - Break-even: the 5-minute TTL needs 2 requests, the 1-hour TTL needs at least 3.
> - The docs say it outright: for two requests less than 5 minutes apart, *"the 1-hour TTL buys
>   nothing there except the doubled write price"*.
>
> Chat is bursty traffic, exactly the case where 1 hour only costs more. Turning it on across the
> board **makes things more expensive for most users** to serve a minority.

**Conclusion: drop "turn on the 1-hour cache" from the roadmap as a one-line fix.** The 1-hour TTL
is only right when the gap between two turns is 5 to 60 minutes. Doing it properly means CHOOSING
by the real gap of each session (Jarvis 007 can know this: the session store has the time of the
previous turn), and that is a feature with its own design, not a default parameter.

Lesson: the current default of `5m` **is right** for the most common case. A code branch that has
been written but that nobody calls does not automatically mean someone forgot to call it.

---

# Part 5: Slope and cliff

This is the frame for reading every number in this document. Without it, it is very easy to
optimize the wrong place.

A **slope** is a constant where being a little off costs a little. Example: a core of 8,000
instead of 6,000 adds ~393 tokens, about **130 milliseconds**. On a turn that takes 30 to 90
seconds, that is below the threshold of perception.

A **cliff** is a threshold where crossing it makes behavior **jump a step**. Example: crossing the
argv ceiling adds a whole inference round, that is **30 to 60 seconds**.

The gap between the two kinds is **more than 200 times**. So:

> Jarvis 007's performance lies in standing on the right side of a few cliffs, not in shaving
> every thousand characters off the slope.

The four cliffs in the system:

| Cliff | Threshold | What crossing it means |
|---|---|---|
| Antigravity command-line ceiling | 120,000 bytes (Linux), 30,000 UTF-16 (Windows) | One extra inference round, 30-60 seconds |
| Lazy tool threshold | 40 tools **or** 6,000 characters of schema | ~10,000 characters of schema, traded for the possibility of one extra `javis_search_tools` round |
| Cache lifetime | 5 minutes (or 1 hour if enabled) | The whole cached prefix is lost |
| Minimum size to cache | 512 to 4,096 tokens, depending on model | **Below the threshold, caching silently does not run** |

The fourth cliff is the new find from reading the API docs, and it is **this plan's own trap**:
cutting the prompt too hard can drop the prefix below the minimum, and then caching **stops working
without any notice**. Part 9 has a way to check.

The lazy threshold also deserves attention: the three new tools in Part 9 **make the pool bigger**,
so they could push a brain currently at 38 tools past the 40 mark. That is a behavior change to
know in advance, not a surprise.

---

# Part 6: Three architectural constants

This is the part that has to stand still for years. All three are **process and structure**,
independent of any library, model or algorithm, so they can live a long time.

## Constant 1: The line that splits personality from surface

> **The core prompt holds only what scales with Jarvis 007's PERSONALITY. Everything that scales
> with Jarvis 007's SURFACE lives on its own carrier.**

| | Personality | Surface |
|---|---|---|
| Content | Who Jarvis 007 is, forms of address, how it presents, the decision ladder, when to ask back | Engines, connectors, file formats, operating procedures, incidents |
| Growth rate | Nearly stationary | Superlinear |
| Evidence | The decision ladder has not changed since the start of the repo | Gemini CLI removed, Antigravity added, Grok added |
| Home | `kernel.md` (frozen ceiling) | Tool contract, skill body, code, connector metadata |

Split along this line, the core **does not grow**, because what makes it grow has been routed
elsewhere at the moment it is born. That is the durability this plan is aiming for.

## Constant 2: The core ceiling is frozen and cannot be borrowed against

```
system/prompt/kernel.md     ceiling 8,000 characters, PERMANENT
```

Adding to the core must come with deleting something else.

Why this is the most important constant: **a ceiling that can be raised is not a ceiling, it is a
suggestion.** The current ceiling has been raised. A ceiling with teeth is the only thing that
creates pressure to route rules elsewhere.

8,000 characters is also the amount a person can **read through in one sitting**. Nobody can audit
33,577, so nobody knows which rules in there have gone stale.

To avoid any misunderstanding: the number 8,000 is **not a performance optimization**. The
difference between 8,000 and 6,000 is only ~130 ms. It exists for discipline.

## Constant 3: Every rule declares its enforcer

```yaml
id: agent-writes-to-correct-folder
enforced_by: javis_create_agent     # code enforces → DELETE from prose
# enforced_by: ""                   # empty → candidate to turn into code
added: 2026-07-19
because: "Agent wrote into Javis/agents/ so it vanished from the app"
review: 2026-12-19
```

The `enforced_by` field turns removing prose from **a whim** into **something automatic**: once
code enforces a rule, the prose is deleted, and nobody has to remember. This is exactly the hole
that let the Orchestration section survive intact even though `javis_schedule` has existed for a
long time.

---

# Part 7: Four carriers and how to choose

## The real price list

| Carrier | Cost per turn | Reliability | Can drop out of context mid-session? |
|---|---|---|---|
| **Code / validation / hook** | **0 forever** | **100%** | Cannot |
| **Tool contract** (schema + description) | 0 when out of scope (lazy already exists) | ~95% | No, the tool's scope is stable for the whole session |
| **Skill body / policy** | 0 until loaded | ~90% | **Yes** |
| **Prose in the core** | **Always paid** | ~80% | No |

The two best carriers are both code, and both are **immune to losing context mid-turn**.

This also settles an obvious worry: "if I pull rules out, what if the model forgets them next
turn?". If most of the heavy rules sit on carriers 1 and 2, then that problem mostly does not
exist, and **no session-pinning mechanism needs to be built at all**. One fewer system to maintain.

## Selection principle: four questions in order

When an incident gives birth to a rule:

```
1. Can the degree of freedom be removed?   → tool or hook.   The rule DISAPPEARS.
2. Can code detect it?                     → validation.     One line of prose remains.
3. Judgment about a capability?            → tool description / skill body.
4. Judgment about PERSONALITY?             → the core (rare, and something else must be deleted).
```

## Why question 1 is the strongest lever

Almost every rule has the form *"when doing X, do it this way, not that way"*. Each such rule is a
**tax levied on a surplus degree of freedom** that the model should not have had in the first
place.

Try it on the most expensive section in this group, the one on creating agents and workflows
(2,875 characters):

| Current rule | Why it exists | Remove the degree of freedom with |
|---|---|---|
| Write to flat `agents/`, NOT `Javis/agents/` | The model chooses the path | The tool writes to the right place itself |
| ASCII slug without diacritics | The model makes up the slug | The tool slugifies itself (`main.py:_ascii_slug`, which has `replace("đ","d")`) |
| `description` at most 150 characters, count after writing | The model counts by itself | Validation returns an error with the number of excess characters |
| `group` must not be empty, read the groups in use then pick the closest | The model has to survey on its own | An enum parameter built from the existing groups |
| A workflow that references a missing agent means create the agent first | The model has to check on its own | The tool checks references |
| A loop created from chat defaults to `enabled: false`, `mode: full` | The model has to remember | The tool's default values |

Six rules, 2,875 characters, **gone entirely**. No compression, no retrieval. And accuracy rises
from ~80% (the model remembers the rule) to 100% (code enforces it).

## A paved road, not a cage

Narrowing the interface reduces flexibility, and flexibility is Jarvis 007's selling point. So the
design has two layers:

- **The paved road:** `javis_create_agent(...)` does everything right and is the easiest path, so
  the model picks it by itself
- **The guardrail:** a `pre_tool_call` hook blocks or rewrites a write into `Javis/agents/`, with
  an explanation

The raw file tool stays for free-form work (writing articles, analysis, data). The boundary:

> **Anything with required frontmatter gets a tool. Anything free-form keeps the primitive.**

**A limit that has to be stated plainly:** the hook only wraps tools that go through the hub
(`mcp_hub.py:951`). The native `Write` tool in Claude Code and Codex **does not go through
there**, so the guardrail cannot reach it. Two layers make up for that:

1. `mcp_store.disallowed_tools()` already has a path for blocking native tools (`main.py:3331`),
   but banning `Write` for the owner's chat is overkill, so we do not.
2. **A post-turn check:** `channel_context.collect_turn_files` already scans for new files after
   each turn. Add a cross-check step: a `.md` file with frontmatter `type: agent|workflow` that sits
   in the wrong folder is moved to the right place, and one line is added to the answer. This is
   firefighting, not fire prevention, but it turns a silent error into a spoken one.

---

# Part 8: The economics of cutting

This part decides **where to stop cutting**, and it corrects a number that intuition tends to get
wrong.

## The right question

Not "how much to cut to be faster", but **"how far can we cut before it starts getting slower"**.

Because if a cut rule makes the model do the wrong thing, the work has to be redone, and one redo
costs far more than the characters saved.

## Break-even table

Using the real measurement: `CLAUDE.md` at 33,369 English characters = 6,555 tokens, that is
**5.09 characters/token**. Prompt ingestion speed is taken generously at 3,000 tokens/second (this
number favors cutting).

**Cutting a 2,000-character section from the core:**

| Scenario | Saved | One failure costs | Pays off only if | Rate the model must get right |
|---|---:|---:|---|---:|
| **With a guardrail** (hook catches it, adds 1 tool round ~10s) | 131 ms/turn | 10 s | fewer than 1 failure per 76 turns | **≥ 98.7%** |
| **Without a guardrail** (user notices, 1 fix turn ~60s) | 131 ms/turn | 60 s | fewer than 1 failure per 458 turns | **≥ 99.8%** |

**Cutting the whole Orchestration section, 8,888 characters:**

| Scenario | Saved | Pays off only if | Rate required |
|---|---:|---|---:|
| With a guardrail | 582 ms/turn | fewer than 1 failure per 17 turns | ≥ 94.2% |
| Without a guardrail | 582 ms/turn | fewer than 1 failure per 103 turns | ≥ 99.0% |

## Two conclusions

**One: the stop threshold is 98%, not 90%.**

An earlier draft of this plan set "if the rate at which the model uses the tool path is below 90%,
do not cut". 90% means 1 failure per 10 turns, while break-even is 1 per 76. So that threshold is
**nearly 8 times looser than necessary**, and following it means cutting and then getting slower
with nobody able to trace why.

**Two: the guardrail is a prerequisite, not a side job.**

The table shows that a veto hook lowers the requirement from **99.8% (unattainable)** to **98.7%
(attainable)**. Without a guardrail, **the entire effort of pulling out prose does not pay off**, no
matter how well it is done.

So in the roadmap, the veto hook **hard-blocks** all prose removal that comes after it.

---

# Part 9: Seven contracts

## Contract 1: `system/prompt/kernel.md`

### Splitting two audiences

`server/main.py:351` points at `CLAUDE.md` at the repo root. That same file is serving two very
different audiences:

1. **Claude Code working on the `javis-os` repo** reads it as the project file (automatically,
   by cwd)
2. **Every end user of Jarvis 007** receives it as the system prompt, on every chat turn

This is the **structural** cause of the swelling: every time a dev convention is added, every
paying customer pays for it on every turn. The "Dev conventions" section (1,005 characters) is just
the visible part; the pressure persists because both audiences write into the same file.

After the split:

```
CLAUDE.md                    the repo's dev conventions. Claude Code reads it by cwd.
                             NOT in the product's system prompt.
system/prompt/kernel.md      the product's core prompt. main.py:351 points here.
system/prompt/blocks/*.md    conditional blocks (Contract 4)
system/prompt/policies/*.md  rules by skill carrier (Contract 2)
```

### Fixed table of contents for the core

```
1. Who Jarvis 007 is                 ~1,200   personality, swappable brain
2. Output contract                   ~1,500   language, forms of address, format, no em dash
3. Decision ladder                     ~700   5 lines, not 8,888 characters
4. When to ask back                  ~1,200   real judgment, keep
5. When no suitable MCP exists         ~150
6. RULE GROUP INDEX                    ~250   always present
                                     ------
                                     ~5,000   ceiling 8,000, leaving room for new personality rules
```

Item 6 is the safeguard against the biggest risk of moving rules out. Today the model sees all
33,577 characters, so it knows every rule exists; after the move, it may not know whether the thing
it needs exists. A **group**-level index keeps the model always holding a **map**, just not always
holding the **content**:

```
Existing rule groups: task orchestration · creating capabilities · memory · files and images ·
data and MCP · channels and chatbots · safety.
If you need a group that is not in the prompt yet, call javis_use_skill to fetch it.
```

## Contract 2: rule files

One rule = one file at `system/prompt/policies/<id>.md`, reusing the existing skill format so
`skill_router` and `javis_use_skill` can read it right away, **with no new runtime needed**.

```yaml
---
id: ba-muc-quyen-loop
group: dieu-phoi                  # matches the group index in the core
description: "The three permission levels of a loop and when to pick each."   # <= 150, enforced by skill_router
requires: [thang-quyet-dinh]      # loading this pulls that in too
enforced_by: javis_schedule       # empty = no code enforces it yet
added: 2026-08-16
because: "A loop in full mode ran outside actions without asking"
review: 2027-02-16
---
<rule body, no length limit, only enters context when loaded>
```

### Chunk by DECISION, not by section

Loading the 8,888-character Orchestration section as one lump saves almost nothing. Split around
**one decision**, each unit 800 to 1,500 characters:

```
policies/thang-quyet-dinh.md              ~900   (the 5-line digest goes into the core)
policies/bao-ket-qua-ve-nguoi-hoi.md    ~1,200   enforced_by: server attaches chat_id itself
policies/ba-muc-quyen-loop.md           ~1,100   enforced_by: javis_schedule
policies/dieu-kien-truoc-khi-len-lich.md  ~900   enforced_by: javis_schedule (can_force)
policies/zalo-gui-tin.md                ~1,000   → moves to the zalo_send_message description
policies/khong-hua-suong.md               ~200   enforced_by: background_status
```

## Contract 3: three new tools

Written as bundled plugins, following the mold of `system/plugins/javis-schedule/`. Use
`ctx.register_tool` (`plugins_host.py:340`), `min_mode="safe"`. All three sit in the lazy pool and
are **not** added to `CORE_TOOL_FNS`.

### `javis_create_agent` / `javis_update_agent`

```
op            create | update
slug          optional. If missing, the tool slugifies from name using _ascii_slug.
name          required on create.
description   required. The tool COUNTS and returns an error if > 150, with the excess count.
group         enum built AT RUNTIME from the groups in use across agents/ + skills/ + workflows/.
              If none match, a new value is accepted but a warning is returned.
skills        list of slugs. The tool checks they exist, errors if one points to a missing skill.
body          the agent's prompt content.
```

The tool handles by itself: writing to `<brain>/agents/<slug>.md` **flat**, building correct
frontmatter, preventing duplicate slugs, rejecting slugs with diacritics or containing `/` and
`..`.

Retires: **2,875 characters** (the "Creating/editing Agents and Workflows" section) and **1,726**
(the "Building capabilities" section, which already duplicates the `javis-builder` skill).

### `javis_create_workflow`

Same mold. Adds **reference checking**: a workflow that points to an agent that does not exist makes
the tool return an error naming the missing agent, instead of relying on the model to remember the
rule "create the agent first".

### `javis_remember`

```
type          user | preference | business | decision
content       the memory content
slug          optional, slugified from the first line if missing
```

The tool handles by itself: writing `<brain>/memory/facts/<slug>.md` in **lowercase** (the rule
"Linux reads a capital M as a different folder" disappears), building the `type/created/updated`
frontmatter, adding exactly one line to `memory/MEMORY.md`, and **detecting duplicates by itself**
then updating the old file instead of spawning a copy.

Retires: **2,297 characters**.

### `javis_create_plugin`

Forces `enabled: false`, requires an explicit `min_mode`, and **returns the reminder about
`JAVIS_ENABLE_USER_PLUGINS`** in the tool result instead of relying on the model to remember to say
it.

Retires: **2,114 characters**.

## Contract 4: conditional blocks

The server does not guess, it **knows**. These five blocks are assembled according to facts it
already has: no retrieval, no risk, no tool round.

| Fact | Block | Characters | Where the server knows it |
|---|---|---:|---|
| There are attached files | `blocks/files-attached.md` | 2,272 | `has_attachments`, `main.py:12175` |
| There is a `[FILE ĐANG MỞ]` block | `blocks/open-file.md` | 676 | the server inserts that block itself |
| CRM pack installed | `blocks/customer-inbox.md` | 329 | `packs_store` |
| There is a data MCP | `blocks/data-cache.md` | 824 | `javis_connections` |
| Dev session on the repo | (goes to `CLAUDE.md`) | 1,005 | no longer relevant |

A turn that matches none of the conditions pays **0 characters** for all five.

## Contract 5: order blocks by stability

The assembly order is part of the contract. The API docs say it plainly:

> "Caching is a prefix match. Any byte change anywhere in the prefix invalidates everything
> after it. Render order is `tools` → `system` → `messages`. Keep stable content first, put
> volatile content after the last `cache_control` breakpoint."

So:

```
┌─ CORE                      unchanged between turns, unchanged between brains
├─ MEMORY (short index)      changes when a new memory is added
├─ CONDITIONAL BLOCKS        change when conditions change, not per turn
│  === CACHE BOUNDARY: cache_control goes HERE ===
├─ CLOCK, LANGUAGE, CHANNEL  change every turn
└─ THE QUESTION
```

Today the clock block (`context_compiler.dong_ho`) already sits at the end of
`build_system_prompt`, which is the right direction. What needs doing is placing `cache_control`
at the right boundary instead of wrapping the whole system block.

### Three things that must be stated plainly about the cache

**One: a better way for the block that changes every turn.** The API docs describe a first-class
mechanism:

> "Mid-conversation operator instructions (Claude Opus 5, Opus 4.8, Fable 5/5.1; **not Sonnet
> 5**; no beta header): append `{"role": "system", ...}` to `messages[]` instead of editing
> top-level `system`. Preserves the cached history prefix and is the prompt-injection-safe
> operator channel."

That is, the clock, the channel block and the conditional blocks should go into `messages[]` as
mid-conversation system messages, instead of being appended to `system` at the top. That way the
cached prefix is **not touched at all**. Constraints: it must come after a `user` message, and must
be the last entry or be followed by an `assistant` turn; it cannot be `messages[0]`. It is
model-gated, so a fallback is needed for models that do not support it.

**Two: cutting too hard can kill the cache.** The docs say: *"Minimum cacheable prefix is
model-dependent (512-4096 tokens) - shorter prefixes silently won't cache."*

A 6,000-character core is about 1,180 tokens. Add memory and the conditional blocks and the prefix
is about 2,500 tokens, so it **may still be above the threshold, but that is not certain for every
model**. This is the fourth cliff in Part 5, and it is this plan's own trap.

**How to check, mandatory at roadmap item 5:** read `usage.cache_read_input_tokens` over a few
consecutive turns. Zero means the cache is not running.

**Three: scope.** The whole cache argument applies only to API engines. For Claude Code, Codex and
`agy`, Jarvis 007 does not control the cache; the CLI and the provider handle it. For exactly the
brains most often complained about as slow, what decides is Cliff 1 (the argv ceiling), not the
cache.

## Contract 6: a pre-built core keyed by signature

`build_system_prompt` caches by signature, following the mold of `plugins_host._signature`, which
already works well:

```python
sig = (mtime kernel.md, mtime blocks/, mtime policies/, mtime MEMORY.md,
       skill tree signature (system_sync._mirror_signature, stat-only),
       brain, lang, project_id, session_id, active condition set)
```

Two benefits, and the second matters more:

1. Removes ~40 ms of event loop blocking per turn
2. The prefix sent out is **identical to the byte** between turns, so the prompt cache hits
   reliably rather than by luck

## Contract 7: `MEMORY.md`

Same split line, different medicine, because memory is not allowed to be absent.

| | Today | After |
|---|---|---|
| User personality (form of address, role, industry, goals) | Mixed into the 20,000 | **~800 characters, always present** |
| Fact index (surface) | Same place, cut when full | Ceiling 3,000, each fact 1 line of ~60 characters → ~50 facts, **no line cut** |
| Fact details | Stuffed into the index | Loaded when relevant |

It sounds backwards but it is true: **the new 3,000 ceiling holds more facts than the old 20,000
one**, because the old ceiling also carried the details. And the "losing memory" step in
`_fit_memory_index` disappears.

---

# Part 10: Roadmap

The order has real constraints; it is not arranged by feel. Three ordering rules:

- **Stop the source of swelling before cleaning up the consequences** (items 1 and 2 before
  everything)
- **Guardrail before removing any rule** (item 3 hard-blocks items 6 through 9, see Part 8)
- **The two Antigravity constants must be fixed together** (item 4, see Part 4.1)

| # | Task | Acceptance | Effort |
|---|---|---|---|
| 1 | Split `CLAUDE.md` (repo dev) from `system/prompt/kernel.md` (product) | End-user chat no longer carries "Dev conventions". Claude Code on the repo can still read the conventions | 0.5 days |
| 2 | Freeze the core ceiling at 8,000 + a character allocation table on the Diagnostics page | One test guards `kernel.md`, a second test guards the **assembled total**. The Diagnostics page shows the characters of each block | 1 day |
| 3 | **DONE: `pre_tool_call` can veto** (`plugins_host.py`) | If the hook returns `{"deny": "reason"}` the tool does not run and the model receives exactly that sentence. If the hook errors, the tool STILL runs (fail-open) | 0.5 days |
| 4 | ~~`AGY_BOOTSTRAP_MAX_CHARS` 100,000 → 80,000~~ **DONE: → 45,000** (the real number after measuring the 46,179 sysprompt) | `test_ba_loi_tran_prompt.py` | ✅ |
| 5 | Four conditional blocks + move `cache_control` + **check `cache_read_input_tokens`** | A turn without attachments drops exactly 2,272 characters. Cache read is non-zero over 3 consecutive turns | 1.5 days |
| 6 | Remove rules that code already enforces + add `enforced_by` to every rule file | The three "empty promise" passages (2,403) shrink to 1 line. Test: a non-empty `enforced_by` must point to a real symbol | 0.5 days |
| 7 | `javis_remember` | Retires 2,297. Write 60 test memories, `MEMORY.md` loses no line | 1 day |
| 8 | `javis_create_agent`, `javis_create_workflow` + hook guardrail | Retires 2,875 + 1,726. A direct write into `Javis/agents/` is blocked with an explanation | 2 days |
| 9 | `javis_create_plugin` | Retires 2,114 | 1 day |
| 10 | Split Orchestration into policies | Retires ~8,000. Core under 6,500 | 2-3 days |
| ~~11~~ | ~~Pre-built core keyed by signature~~ **WITHDRAWN** | Measured 3.9 ms, not 40 ms (see 4.5). The CPU reason is gone | - |
| ~~12~~ | ~~`cache_ttl="1h"`~~ **WITHDRAWN** | The 1-hour TTL costs 2x to write and is only right for 5-60 minute gaps (see 4.6). The 5m default is right | - |
| 13 | Split `MEMORY.md` into index and details | The line-cutting step no longer triggers with 50 facts | 2 days |
| 14 | **HALF DONE:** order by usage frequency + cut by character budget. Top-k by `capability_index` later | `test_ba_loi_tran_prompt.py` | ✅ |
| 15 | `/luat-moi` classifies at the source | The command runs the 4 questions and builds a file skeleton on the right carrier | 1 day |

**Item 15 is not a final reward, it is what keeps the 14 items above from drifting back.** If
writing a rule on the right carrier is still more expensive than writing it into the core, the
slope remains.

## Expected results, stated as a distribution

No single number, because a single number is a way to make the reader decide wrongly.

| | Today | After |
|---|---:|---:|
| Ordinary question (p50) | 33,577 | **~6,000** |
| With an attached file (p80) | 33,577 | ~8,300 |
| Creating an agent, tool in scope (p95) | 33,577 | ~7,000 |
| Worst case (p99) | 33,577 | ~11,000 |
| Extra inference rounds per turn | 0 | **0** |
| Antigravity on Linux forced onto the file path | **Always** | Only when the conversation is very long |
| Ceiling on number of rules | ~33,600 characters | **None** |

The p95 row is where this differs sharply from the "compress by retrieval" option: when the model
is **doing** something that needs a rule, the cost is still lower than today, because a tool
contract is tighter than prose explaining how to use a primitive.

---

# Part 11: Tests and fences

| Test | What it guards |
|---|---|
| `test_prompt_budget` (changed) | `kernel.md` <= 8,000. **This number must not be raised**; raising it must come with a deletion |
| `test_prompt_assembled` (new) | Assembled total <= 14,000 for every combination of conditions |
| `test_rule_provenance` (new) | Every rule file has `id`, `group`, `description` <= 150, `added`, `because`. A non-empty `enforced_by` must point to a real symbol |
| `test_kernel_no_surface` (new) | The core contains no engine names, connector names, or specific file paths |
| `test_hook_veto` (new) | If the hook returns `deny` the tool does not run; if the hook errors the tool STILL runs |
| `test_agy_argv_fit` (new) | `AGY_BOOTSTRAP_MAX_CHARS` + the core ceiling, converted to Vietnamese bytes, must be under the Linux `_tran_argv()` with a 3% margin |
| `test_tool_retire` (new) | For each tool in the retire table, `kernel.md` no longer contains the key phrases of the removed section |

The two most valuable tests:

- **`test_kernel_no_surface`** turns Constant 1 from a promise into something CI can check. It goes
  red the first time someone writes "Antigravity" or "agents/" into the core.
- **`test_agy_argv_fit`** is what stops the exact defect in Part 4.1 from recurring: two constants
  in two different files that nobody places side by side, with silent consequences.

---

# Part 12: Risks and fallbacks

| Risk | Level | Fallback |
|---|---|---|
| The model does not call the new tools and still writes raw files | High at first | Hook guardrail + `collect_turn_files` post-check. Measure the tool-call rate for 1 week before removing prose |
| After a rule is pulled out, the model gets that task wrong | Medium | **Run in parallel**: keep the prose while creating the tool, measure for 1 week, **if the tool usage rate is under 98% do not cut** (basis in Part 8) |
| Cutting too hard drops the prefix below the minimum, so the cache silently stops | Medium | Check `usage.cache_read_input_tokens` at item 5. Zero over 3 turns is the sign |
| The three new tools push a brain past the lazy threshold of 40 | Low | Measure `pool_chars` before and after. The threshold is at `config.py:228`, adjustable |
| New tools reduce flexibility | Medium | Primitives remain. The tool is a paved road, not a cage |
| The pre-built core returns a stale copy after a skill is edited | Low | The signature includes the skill tree mtime, following the mold of `plugins_host._signature` |
| The veto hook blocks by mistake | Low | Fail-open when the hook errors. Explicit path allowlist, no implicit inference |
| Item 14 (dropping `SKILL_LIST_MAX`) makes routing miss | Medium | Do it last, and only when `miss_class` on the Diagnostics page has data |

**Stop condition:** for any of items 7 to 10, if after 1 week of running in parallel the rate at
which the model uses the tool path is **under 98%**, do not cut the prose; go back and fix the tool
description first.

---

# Part 13: Things deliberately NOT done

Recorded because each of these was considered and then rejected for a reason.

- **Do not build a new policy retrieval layer.** The mechanism already exists (lazy tool pool,
  `skill_router`, `javis_use_skill`) and has been measured. Adding a seventh layer on top of a stack
  of six that has no production baseline repeats exactly the mistake that led here.
- **Do not configure embeddings for `capability_index`.** The RRF scaffolding is ready. Turn it on
  when `miss_class` says it is needed. Most rules are triggered by **structure** (a time expression is
  present, a creation intent is present) rather than by vocabulary, so embeddings solve a problem
  they do not have.
- **Do not build a per-session policy pinning mechanism.** It is only needed when a rule lives in a
  policy body. Putting the rule into the tool contract means the tool's scope is already stable for
  the whole session.
- **Do not let the model calling `javis_use_skill` be the MAIN path.** It is a full inference
  round, that is 30 to 60 seconds on a CLI engine. It is a safety net for the retrieval-miss case.
- **Do not ban native `Write` for the owner's chat.** Overkill. Use the post-check instead of a ban.
- **Do not raise the core ceiling.** Hitting 8,000 is a signal that a surface rule has leaked into
  the core, not a signal that the ceiling is too small.

---

# Appendix A: routing of the current `CLAUDE.md`

| Section | Characters | Destination | Notes |
|---|---:|---|---|
| Orchestration | 8,888 | Tool + core | The 5-line decision ladder goes into the core (~700). Reporting results → the server attaches `chat_id` itself. Three permission levels → tool parameters. Zalo rules → the `zalo_send_message` description. Empty promises → already enforced by `background_status` |
| What Jarvis 007 is | 4,071 | Core + data | Personality keeps ~1,200. The 10-engine table is **data**, generated from `PROVIDERS`, not hand-written |
| Response principles | 3,812 | Core + channel | Personality keeps ~1,500. The per-channel part already has `channel_context` |
| Creating Agents/Workflows | 2,875 | Tool | `javis_create_agent`, `javis_create_workflow`. 0 remaining |
| Long-term memory | 2,297 | Tool | `javis_remember`. 0 remaining |
| Files attached | 2,272 | Conditional block | `has_attachments` |
| Creating Plugins | 2,114 | Tool | `javis_create_plugin`. 0 remaining |
| Clarify before answering | 2,055 | Core | Real judgment, kept as is |
| Building capabilities | 1,726 | Skill | Already duplicates `javis-builder`. 0 remaining |
| Dev conventions | 1,005 | Split out to a file | Goes to the repo's `CLAUDE.md` |
| Data Cache | 824 | Conditional block | Only when there is a data MCP |
| Open file | 676 | Conditional block | The server inserts that block itself |
| Customer inbox | 329 | Conditional block | Only when the CRM pack is installed |
| Role, formula, when no MCP | ~610 | Core | Keep |

**Total going into the core: ~5,000 to 6,500 characters.**

---

# Appendix B: every constant and its kind

| Constant | Where | Kind | Effect |
|---|---|---|---|
| `_tran_argv` 120,000 / 30,000 | `antigravity_cli.py` | **Cliff** | Crossing it adds 1 inference round, 30-60 seconds |
| `AGY_BOOTSTRAP_MAX_CHARS` 100,000 → **45,000** | `compaction.py` | **Cliff** (via the argv ceiling) | Fixed. The 45,000 comes from the MEASURED sysprompt of 46,179, not the 36,000 estimate |
| `lazy_threshold` 40 / `lazy_char_budget` 6000 | `config.py:228` | Two-way **cliff** | ~10,000 characters, traded for the possibility of 1 extra tool round |
| Minimum to cache 512-4096 tokens | API | **Cliff** | Below the threshold the cache silently does not run |
| `cache_ttl` stays at 5 minutes | `engine.py:320` | Time-based **cliff** | NOT changed: 1 hour costs 2x to write, only right for 5-60 minute gaps |
| `SUBSCRIPTION_THREAD_MAX_TOKENS` 1M | `compaction.py:73` | Cliff | Rotates the thread, re-primes the transcript |
| Core ceiling 8,000 | (new) | Slope | ~130 ms compared with 6,000. Exists for **discipline**, not for speed |
| `MEMORY_INDEX_MAX` 20,000 → 3,000 | `main.py:523` | Slope | The reason is **compactness and cost**, NOT "memory is being lost" (see correction 4.4) |
| Assembled total ceiling 14,000 | (new) | Slope | A yardstick, not a performance switch |
| `SKILL_LIST_MAX` 20 → **40** + `SKILL_LIST_CHAR_BUDGET` 4,000 | `skill_router.py` | **Hidden ceiling** | Fixed: ordered by usage frequency before cutting, so what gets cut is no longer whatever sorts last alphabetically |
| Stop threshold when removing prose, 98% | (new) | **Decision** | Setting it at 90% is a net loss, see Part 8 |

---

# One-paragraph summary

The problem is not that there are too many rules, but that **the model has too many surplus
degrees of freedom, and writing prose is the cheapest way to tax them**. This plan changes the
price: it makes placing a rule on the right carrier as cheap as stuffing it into the core, it
freezes the core ceiling to force a choice, and it makes every rule declare its enforcer so that
any rule code already enforces is automatically deleted from the prompt.

On performance, the most important thing to remember: **what decides is not a few thousand
characters on the slope, but standing on the right side of a few cliffs.** The most expensive cliff
is Antigravity's command-line ceiling, and it can only be cleared by changing
`AGY_BOOTSTRAP_MAX_CHARS` **at the same time** as shrinking the core. Fixing one is not enough.

The repo has already proven the central proposition: `javis_schedule` has a tool so it costs ~600
characters of prose, while creating an agent has no tool so it costs 2,875 characters for a simpler
job. What is missing is not architecture, but a process that forces prose to be removed when a tool
is born.
