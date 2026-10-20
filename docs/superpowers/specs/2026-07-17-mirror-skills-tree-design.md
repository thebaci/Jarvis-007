# B4: mirror_skills copies the whole subtree + a signature gate

Date: 2026-07-17
Status: design approved, waiting for the implementation plan

This is the standalone spec for B4, the part that was DEFERRED from the A+B plan on 2026-07-16
(see `2026-07-16-skill-telemetry-authoring-design.md`, section "DEFERRED: B4").

## A finding that overturns the decision to defer

Last time I recommended deferring on the grounds that "going recursive would turn every chat
turn into a walk + hash of the whole skill tree". That reason rested on **inference, not
measurement**. Measured for real:

| brain | files | `mirror_skills` NOW (reads + hashes SKILL.md per skill) | signature step alone (stat-only, NOT the whole function) | `mirror_skills` AFTER THE FIX (whole function, measured) |
|---|---|---|---|---|
| My Bullet Journal | 41 | **52.48 ms** | 5.79 ms | **8.30 ms** (6.3x) |
| Ngọc Thu Phạm | 30 | 44.23 ms | 6.02 ms | **6.05 ms** (7.3x) |
| Brain Default | 9 | 11.62 ms | 1.64 ms | **2.28 ms** (5.1x) |

Two things fall out of this:

**1. `mirror_skills` already costs ~52ms EVERY CHAT TURN, right now, with no recursion at all.**
It reads and hashes `SKILL.md` twice (source + destination) for every skill, every time it is
called. And it is called from `build_system_prompt` (`main.py:184`), a SYNCHRONOUS function that
runs on every dashboard chat turn, every Telegram message, every Kanban task, every loop round,
every reminder, every learn spawn. This is a PRE-EXISTING performance bug nobody knew about, and
it blocks the event loop just like the two bugs the A+B round just patched (`bump` had to go
through `to_thread`, `BrainLock` had to have its timeout lowered to 1s).

**2. The signature gate uses only `stat`, reads no bytes** - and it covers subfolders too. The
third column in the table above measures the signature step ALONE, NOT the whole
`mirror_skills` function (the function also has to `iterdir`/`rglob`/`copy2` when the tree
changes, and has a real-copy branch on first run); do not take that number as the function's
real speed.

So the recursive version WITH a signature gate is clearly faster than 52ms. I re-measured the
WHOLE `mirror_skills` function (not just the signature step) on those same 3 brains after
finishing the work: 8.30 ms / 6.05 ms / 2.28 ms, i.e. about 5 to 7 times faster depending on the
brain (6.3x / 7.3x / 5.1x in the order above), NOT "9 times" as the first draft claimed. That 9x
was computed from the signature-only column (~52ms / ~6ms), not from the full function - **it
measured the wrong thing**. It is still not "high risk in exchange for zero benefit": the
improvement is REAL, just smaller than the original number suggested.

Lesson recorded: the six blockers last time were all REAL, but the conclusion "defer" was wrong,
because it rested on an assumption about cost that nobody measured. Measure first, conclude
after - and measure THE RIGHT THING: this spec's own first draft measured only the signature
step and took it as the speed of the whole function, nearly repeating the exact "concluding from
inference / measuring the wrong thing" mistake this lesson preaches against.

## The six old blockers, status now

1. **Per-chat-turn cost** - SOLVED by the signature gate. 52ms -> about 2-8ms depending on the
   brain (whole function measured for real, not one fixed number), so an improvement, not a
   regression.
2. **Blocking the event loop** - SOLVED. About 2-8ms is acceptable, and the lock is taken in a
   non-waiting way so it never queues.
3. **The lock problem** - SOLVED with a SEPARATE lock for the mirror. Verified by reading the
   code: `_LOCK` (`system_sync.py:280`) is taken in EXACTLY TWO places - `sync_brain:289` and
   `ensure_synced:369` - and `mirror_skills` NEVER takes it. A separate lock is taken only
   inside `mirror_skills`, and no other lock is taken while holding it => no cycle => no deadlock.
4. **Double call at startup** - SOLVED for free. The second call either sees the signature
   unchanged, or fails to get the lock, and exits immediately either way.
5. **No tests** - build `test_system_sync.py` from zero. In scope.
6. **Cannot fix `html-to-webcake`** - CORRECT, and still out of scope (Quy settled it). The hole
   is in `_system_items` (`system_sync.py:142-160`), ABOVE `mirror_skills`.

## Architecture

### Two-tier gate inside `mirror_skills`

**Tier 1 (hot path, about 2-8ms depending on the brain, 99% of calls):** compute a signature
using ONLY `stat` over the `<root>/skills` tree. Compare against the in-memory cache keyed by
the resolved root. Unchanged -> return IMMEDIATELY.

**Tier 2 (rare):** signature changed -> real recursive copy -> update the cache.

### Components

- `_mirror_signature(canonical: Path) -> str` - walks recursively with `os.scandir`, folding
  `(relative path, st_mtime_ns, st_size)` of EVERY file into one sha256. Reads NO file
  content. Skips `.disabled`. `follow_symlinks=False` on both `is_dir` and `stat`. Returns an
  empty string if the directory does not exist. OSError -> skip that entry, do not raise.
- `_MIRROR_SIG: dict[str, str]` - module-level cache, key = resolved root. Cleared per process
  (lost on restart).
- `_MIRROR_LOCKS: dict[str, threading.Lock]` - a per-root lock, taken with
  `acquire(blocking=False)`.
- `_MIRROR_RETRY: dict[str, set]` - slugs of skills whose copy FAILED on the previous run and
  need to be retried INDIVIDUALLY (so the whole brain is not dragged into a full rglob every
  turn just because 1 skill is permanently broken). Added after the first version was written -
  it took three consecutive review rounds to catch this permanent-failure case.
- `mirror_skills(root)` - the coordinator: signature -> check cache -> take the non-waiting
  lock -> RE-CHECK the signature a SECOND time inside the lock (double-checked locking: getting
  the lock does not mean "nobody just finished this work" - another thread may have just
  finished copying + writing the cache and only then released the lock, right when we got it;
  without this re-check, 2 threads that both see "changed" at tier 1 would both copy the same
  thing) -> recursive copy (only the owed slugs if the tree is unchanged, the whole tree if the
  tree changed) -> update the cache (using the signature SNAPSHOT taken BEFORE the copy pass,
  not recomputed afterwards) -> release the lock.

### Why the lock is non-waiting

If another thread is already mirroring that very root, it is doing EXACTLY the work we were
about to do. Queuing to wait only blocks the event loop and gains nothing. Returning at once is
correct.

This is also how blocker 4 is handled: `ensure_synced` -> `sync_brain` -> `mirror_skills`
(holding `_LOCK`), then `main.py:184` -> `mirror_skills` again. The second call sees the
signature was just updated and exits at tier 1, never needing the lock.

### Recursive copy

```
rels = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file())
for rel in rels:
    dst_f = dst_dir / rel
    dst_f.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(d / rel), str(dst_f))
```

**Drop content hashing in the mirror entirely.** The signature gate already answers "did the
content change", far more cheaply. Keeping both is redundant.

`skill_hash` is NOT touched - `sync_brain:303`, `LEGACY_HASHES:388-405` and the CLI `--hash`
depend on its exact output. We just STOP using it in `mirror_skills`.

### Invariants to preserve

- Add/update-only. Delete NOTHING in `mirror/<slug>` that the source lacks. Removing the mirror
  when a skill is disabled/deleted is the endpoint's job (`main.py:2186` rmtree).
- Skip `.disabled` (mirroring a disabled skill = accidentally re-enabling it natively).
- The entry gate is still `(p / "SKILL.md").is_file()`.
- try/except per skill: 1 failing skill does not block the rest.
- `mirror_skills` must ABSOLUTELY NOT take `_LOCK`.

## A pre-existing bug patched for free

Today the skip gate hashes only `SKILL.md` (`system_sync.py:251-256`) but the copy loop copies
EVERY top-level file (`:258-260`). So when a sibling asset file changes content but `SKILL.md`
does not, the mirror **never receives it**. The `stat` signature covers every file, so this bug
disappears.

## Testing

Build `server/test_system_sync.py` from zero - today NOT ONE test in the repo touches
`mirror_skills`, and the file the A+B spec assumed exists does not.

House convention (mandatory): NO pytest. A script run directly, `check(name, cond)` + `_fails`
+ `sys.exit(1)`. Pattern: `server/test_loop_ambient.py:23-30` and `:117-120`. The
`JAVIS_STATE_DIR` env is set BEFORE import. The file name must be `server/test_*.py` for CI
(`.github/workflows/ci.yml:29-39`) to glob it. Run command:
`cd server && ../.venv/Scripts/python.exe test_system_sync.py`.

Coverage:
- `references/` and `scripts/` reach the mirror (what B4 was born to do).
- A sibling file changes -> the mirror receives it (the pre-existing bug above).
- Skips `.disabled`.
- Add-only: a foreign file in the mirror is NOT deleted.
- Nothing changed -> **count 0 copies**. Use a spy on `shutil.copy2`. ABSOLUTELY do not check
  with `mtime`: `shutil.copy2` preserves the SOURCE's mtime so the destination always has the
  same mtime whether or not it was copied again - a test like that stays green even when the
  code is wrong. A lesson paid for in the A+B round.
- Nothing changed -> **no file content is read**. Spy on `Path.read_text`/`read_bytes`, or
  count through `shutil.copy2`; prove tier 1 really stops at `stat`.
- Two concurrent threads on the same root -> one exits immediately, no hang.
- A binary file passes through intact (the signature uses stat so it does not touch content,
  but it needs to be pinned down).

## Risks

**A self-healing step backwards (real, reported and accepted by Quy).** The cache is in memory
and the signature is computed on the SOURCE. If the mirror is damaged from outside while the
source is unchanged, `mirror_skills` will skip and the mirror stays broken until the process
restarts. Today's code compares source against destination so it heals itself.

Mitigation: when a skill is disabled, the disable branch in `/skills/toggle` (`main.py`) does an
rmtree of the mirror, moves the source to `.disabled` (the signature changes), AND calls
`mirror_skills` again RIGHT THERE so the cache immediately records the disabled signature -
re-enabling afterwards is guaranteed to see a signature different from the cache and copy
everything again. **The first draft of B4 only moved the source and did NOT call
`mirror_skills` again in the disable branch** - that hole was a real CRITICAL (not hypothetical):
`rename` preserves `st_mtime_ns`/`st_size`, so re-enabling afterwards computes a signature
IDENTICAL to the value the cache remembered from BEFORE the disable (the cache never saw the
disabled state in between), tier 1 thinks "nothing changed" and skips permanently until a
restart. Patched by adding that call to the disable branch, together with a test that walks
exactly the disable->enable sequence (`server/test_system_sync.py`). Wrecking `.claude/skills`
by hand (not through toggle) is still not a normal operation and still needs a process restart
to self-heal - that is the REMAINING accepted risk.

**First-time cost per process:** empty cache -> the first chat turn for each brain pays one full
copy. Acceptable, and still cheaper than 52ms x every turn as it is today.

**`rglob` over a tree with symlinks could loop.** Checked: the disk currently has NO symlink
under any skill folder. `follow_symlinks=False` is still used to be safe.

## Out of scope (deliberate)

- `_system_items` shipping subtrees for SYSTEM skills, i.e. fixing `html-to-webcake` which is
  broken in every brain. It requires changing the manifest from per-item to per-file - the thing
  that decides whether the app overwrites a skill the user edited. A separate job, needing
  separate thought.
- Removing `mirror_skills` from `main.py:184` (the hot path). With the signature gate, about
  2-8ms depending on the brain is acceptable, and keeping it there preserves the property that
  "a skill written mid-session shows up immediately without a restart" - the very reason line
  184 exists.
- Making `build_system_prompt` async. A big change touching many call sites, unnecessary once
  the cost is down to about 2-8ms depending on the brain.
