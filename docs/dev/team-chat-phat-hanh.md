# Team chat: integrating T0 to T5 into main, release 0.140.0

14 Oct 2026. Integration branch `claude/team-chat-release`, PR [#649](https://github.com/blogminhquy/javis-os/pull/649).
Spec: [2026-10-13-team-chat-design.md](../superpowers/specs/2026-10-13-team-chat-design.md). Per-milestone records:
`team-chat-t1.md` to `team-chat-t5.md` (the version numbers written in those records are PLACEHOLDER numbers from the time of the work, and were never released).

## The chain and how it was integrated

Six stacked PRs, straight, no merge commits, all on the same base `bfb1c29f` (0.109.0):

| Milestone | PR | Head | Old placeholder number | Commit on the integration branch |
|---|---|---|---|---|
| T0 Resonance switch + design docs | #627 | `83a1be54` | 0.110.0 | `4ddf0aa3` |
| T1 team chat core | #628 | `cee0159d` | 0.111.0 | `14be8af8` |
| T2 six reactions and feedback | #639 | `a82c0d05` | 0.120.0 | `97c05db4` |
| T3 Team lead full authority | #640 | `c9f4d97c` | 0.121.0 | `5b76feac` |
| T4 long history, search, measurement | #643 | `bc7d653b` | 0.124.0 | `68cf5821` |
| T5 compact Teams page, real images, pinning | #645 | `95db0f57` | 0.129.0 | `359e9293` |

- **Method:**
  - main had moved on by 38 commits (to 0.137.0, `24cfe57c`). The integration branch starts from `origin/main`.
  - Apply each PR's changes relative to the previous PR in dependency order (`git diff prev..head`, `git apply --3way`), one commit per PR, DROPPING the old placeholder `VERSION` and CHANGELOG commits.
  - Do not bring back any commit already on main: main contains no commit of the chain.
- **Text conflicts:** none. The added and removed line counts of each of the 61 files match exactly between "the chain against the old base" and "the integration branch against main".
- **Four files that main also changed since the common base,** each checked separately:
  - `dashboard/i18n/vi.json`, `en.json`: fully merged, both sides have the same 3998 keys, correct format.
  - `server/main.py`: the `/teams` registration still comes after main's last route.
  - `tests/python/route_table.json`: re-captured. main's 422 routes keep their order, with the 25 `/teams` routes appended after.
- **Release number 0.140.0:**
  - At the start, main was at 0.137.0 and another open PR held a lower number, so I reserved 0.138.0 (the first commit on the branch and the draft PR #649).
  - During integration, #644 shipped as 0.139.0 (`be1f8aa2`), passing the reserved number. By convention, the branch is brought onto the new main by rebase: drop the old placeholder commit, resolve the CHANGELOG conflict (keep main's 0.139.0 block, put the team chat block on top).
  - Renumbered to 0.140.0, and PR #649 was retitled 0.140.0 as soon as this was noticed.
  - The commits in the table above are the SHAs after the rebase. The bodies of a few commits still say "0.138.0", which was the number at the time of the work.

## Fixes made at release

- **The snapshot label changed from `.pre-0.111.0` to `.pre-0.140.0`.** Applied to `team_migration.py`, the tool `tools/team_chat_restore_pre.py` (`.post-0.140.0-<timestamp>`), comments in `sessions.py`, `task_store.py`, `ui_targets.py`. Why: 0.111.0 was never released, and users would see a file carrying an odd number.
- **The rollback test runs real 0.139.0 code** (`be1f8aa2`, the last release before team chat; initially it was 0.137.0 `24cfe57c` before main moved on) instead of 0.109.0. Applied to `test_team_rollback.py` and the fetch step in `ci.yml`. The old code opens the upgraded store and does not pick up team work; the restore tool returns to exactly the snapshot (31 cases).
- **New test `test_team_release.py`:** a T1-era team store (schema copied verbatim, without `pinned_at`, `identity_json`, `committed_at`) opened with the release code adds the columns by itself. Old data is kept intact, pinning and identity snapshots work, and opening a second time raises no error.
- **A single 0.140.0 CHANGELOG block**, short and written around what users see; the placeholder blocks 0.110.0 to 0.129.0 are not carried onto main.

## Review of the whole integration result

A fresh reviewer (the strongest model) went over all of `origin/main..HEAD`, not only the final fixes. Verdict "Ready with fixes": 2 Important, 8 Minor.

**Checked, no defect:**
- Every main function that the team code calls still exists, with a compatible signature.
- The team part of `main.py` does not overlap main's 38 commits. main's new features (Zalo replying when the owner is silent, `agy update`, the answer when a turn fails) are untouched.
- i18n merged correctly; team routes come after the last route; snapshot labels are consistent.
- Team work is fully separate from the Tasks board (every query filters by lane).

Fixed, each with a test that ran red first:

| Item | Fix | Test |
|---|---|---|
| Important: clicking a message about blocked team work opens the main chat box, and typing on becomes an authorless message in the team session | A message on channel `team:<id>` opens the right team on the Teams page through `JavisTeams.open`; if not yet on the Teams page, go to the page and then open it when the list arrives | `test_teams_ui.js`; browser smoke test (below) |
| Important: `conversations.db.pre-0.140.0` and `.post-0.140.0-*` are not gitignored, so the whole chat could be copied onto git | `.gitignore` adds `server/conversations.db.pre-*` and `.post-*` | `test_team_release.py` (`git check-ignore` for all three stores) |
| Raised to Important: the voice alias "nhom" (Vietnamese for "group") matches sub-phrases, so "nhóm việc" ("task group") opens the Teams page instead of Tasks (also "nhóm code", "mở nhóm trợ lý", "nhóm hệ thống") | "nhom" matches only when the whole sentence is exactly it; "nhom tro ly" removed | `test_team_release.py`: sentences about the sidebar group come out exactly as in the pre-release version |
| Raised to Important: the assistant's general prompt promises "the hub's toolkit" while a team turn is text only, and calling a tool breaks the turn | Every team turn appends a fixed `TEXT_ONLY_NOTE` paragraph after the assistant's prompt | `test_team_ux.py` |
| Minor: the reminder for work blocked over 24 hours checks only the last 500 events, so a busy team is reminded repeatedly | `TeamStore.has_reminder` checks directly in the store | `test_team_ux.py`: more than 600 events, no repeated reminder |
| Minor: the team API's background jobs were not held by reference | `TeamApi._bg` holds them until done | `test_team_ux.py` |
| Minor: when creating the store, the lazy runner does not lock between threads | `RLock` on creation | |
| Minor: the comment in `console.js` still says "0.111.0" | fixed | `test_teams_ui.js` |

**Left as is** (recorded clearly, not fixed in this release):
- The server does not yet block a turn from the main chat box on a `team:` session. The UI path leading there is closed, and search has filtered team sessions since T1.
- The first run of 0.140.0 takes one synchronous snapshot of `conversations.db` (not measured on a large store; the snapshot does not clean itself up).
- A team session stores the raw brain name (`brain`, not through `_brain_key`); currently this does not affect function.

## Checks

**Local machine** (project `.venv`, temp SQLite, fake engine, no model calls):
- Compile `server`, `system/plugins`; `main` loads.
- `tests/run.py --js`: 186/186.
- `tests/run.py` full Python: 678/692. 14 files red, none in the team chat group:
  - 12 files are on this machine's already-red list (agy, antigravity_cli, grok_cli, terminal, windows_no_console, cai_windows, install_admin, link_file_uri, memory_hoa_thuong, model_theo_phien, ollama_local, ba_loi_mac_va_telegram);
  - `test_machine_translations` reads translation files that the branch does not touch (identical to main);
  - `test_project_khung` is green when run alone.
- After the review fixes: the `team*`, `route_table`, `ui_targets`, `ui_bridge` tests 20/20; `test_team_rollback` 31 cases with real 0.137.0 code (rerun with 0.139.0 after renumbering, section below).

**Browser smoke test** (sandbox on port 7788, daily ceiling 0):
- Re-enabled the "Product launch" team: three waiting jobs were blocked immediately at the turn-holding step, and three `team:` channel messages arrived in the inbox.
- On the home page, click the bell and then click a message: goes to the Teams page, opens the right team, with an "Allow more turns" button.
- All three teams show 0 turns, 0 engine calls; the team was paused again after the test.
- Screenshot: `exports/reviews/team-release-0.138.0/chuong-mo-dung-nhom.jpg`.

**CI:**
- `9d8ce139` (release commit, before renumbering): green on both push and pull_request.
- `eb85f38b` (after the review fixes, before renumbering): see the PR #649 description.
- Final HEAD (after moving onto 0.139.0 and renumbering to 0.140.0): recorded in the PR #649 description and the release report.
