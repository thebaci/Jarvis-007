# Team chat T3: full-authority team lead (0.121.0)

Spec: [2026-10-13-team-chat-design.md](../superpowers/specs/2026-10-13-team-chat-design.md) sections 13, 15.2, 21.3 (D4 to D6); cases TC31 to TC36. Stacked on T2 (PR #639).

## Flow

1. The owner opens the team's Settings tab, section **Full authority for the team lead**: a scoped grant box, team-managed assistants, providers allowed unlimited model turns, billing source, each cap (the value, and the maximum cap the team lead may set, each field with "Unlimited"), the "May interrupt the running job" permission, and the caps that always apply and cannot be lifted. Click **Enable full authority**.
2. The team lead's prompt gets a "Full authority" block: the caps in force, the admin commands available (a `JAVIS_TEAM` block), and the limits that cannot be exceeded. Interrupting a job only appears when the owner allows it.
3. The team lead replies with commands attached: open a task, prioritize or deprioritize a waiting task, add or remove a member, create a new assistant (becomes a team-managed assistant), set a cap within the maximum, edit the prompt or toggle Resonance of a team-managed assistant, interrupt a running job (if allowed). Each action shows up as a system message in the team and as an event with `by=leader:<code>`.
4. The owner clicks **Revoke** at any time, or changes the team lead: the team goes back to Limited authority immediately.

## Code map

| Part | File | What it does |
|---|---|---|
| Store | `server/team_store.py` | Table `team_authority` (one active row per team, `revoked_at`); `grant_authority`, `revoke_authority`, `active_authority` (only while the team lead is still the same one), `update_authority_caps` (CAS on the unrevoked row), `set_managed` (each agent has at most one managing team), `teams_with_member`; changing or removing the team lead revokes in the SAME transaction |
| Runner | `server/team_runner.py` | `effective_caps` (None = Unlimited, D6 per provider), `_caps` at every cap check; `grant_authority`, `revoke_authority`, `set_managed`, `authority_view`; `_apply_admin` (nine commands) called inside `accept_lock` in the accept phase; the "Full authority" block in `_context` |
| Host | `server/main.py` (`_TeamAdmin`) | Creates a new assistant without overwriting (slug `-2`, `-3`), adds the "Team" tag; prompt edits keep the frontmatter; enabling Resonance records `by=leader:<code>`; issues the code. Lock order: `accept_lock` then `_AGENT_META_LOCK`, same as `delete_agent` |
| Routes | `server/team_api.py` | `POST /teams/{id}/authority {mode, grant}`, `POST /teams/{id}/members/{key}/managed {on}`; `GET /teams/{id}` includes `authority` (the row, effective caps, caps that cannot be lifted), and members include `managed` |
| UI | `dashboard/teams.js`, `console.css`, i18n | `authorityHtml`, `readGrant`, the "Team-managed" switch on the Members tab |

## Rules kept

- The team lead has no way to enable full authority itself: only the owner's route (auth, CSRF) calls `grant_authority`; an unknown command in the `JAVIS_TEAM` block is dropped with a note.
- "Unlimited" is stored as `{"unlimited": true}` in the grant box and comes back as `None` in the effective caps; the cap-check code treats `None` as no cap and never substitutes a large number (`reserve_turn` accepts `daily_cap=None`, `task_cap=None`).
- A cap set by the team lead must stay within the maximum cap set by the owner; a missing maximum means the team lead cannot change that cap; if the maximum is a number, "Unlimited" cannot be set.
- D6: unlimited model turns (`task_turns`, `daily_turns`) apply only when the turn's provider (derived like the adapter does: an agent's own Claude model is `anthropic-cli`, everything else is `aux`) is in the list the owner ticked; any other provider uses the team's cap.
- D5: the team lead only edits the prompt and Resonance of assistants that have `managed_by_team` for this team; editing an assistant that is also in another team makes the system message list the affected teams.
- Revoke (13.5): `revoked_at` is written inside `accept_lock`; admin commands are applied in the accept phase and Full authority is checked INSIDE the same lock, so a command arriving after the revoke point is rejected; the reply text is still posted as under Limited authority; caps go back to the limited level at the next reservation, and only a job that exceeds the cap newly enters `cap_reached`.
- M11: changing the team lead (or removing the team lead from the team) revokes in the same transaction, with event `authority_revoked` and reason `leader_changed` or `leader_removed`.
- Interrupting a running job only when `can_interrupt`; the reason is recorded in the `job_interrupted` event and shown in the team.
- No progress under Unlimited: still detected, the job is blocked with `no_progress`, and an inbox message is sent; it never keeps running silently.

## Verdicts and what is not done

- **Per-team goal caps (13.6, the goal rows) and A4 write-scope approval inside the team folder (D4): not done.** A team turn is still text only (T1 verdict R3): there is no path that creates a goal or writes a file from a team turn, so these caps have nothing to apply to. Cost if this is wrong: when tools are opened to team turns, both parts must be done at the same time.
- Changing the model of a team-managed assistant: not done (only the prompt and Resonance).
- The cap "one turn per agent at a time" stays at 1; there is no field for the owner to change it.
- Admin commands use the `JAVIS_TEAM` block (T1 verdict R1) instead of the `javis_team` tool; the spec 15.2 `submit` is not needed because the result is the reply itself.
- Tasks opened by the team lead have a per-turn dedupe key (`leader:<turn_id>:<command order>`): a repeated handling of the same turn does not create a second task; two different turns opening the same title make two tasks.
- The text of system messages and of dropped-command notes is Vietnamese only (like the other server-side text from T1).

## Checks

| Command | Result |
|---|---|
| `tests/python/test_team_authority.py` | TC31 to TC36 with the real runner, a fake engine and a fake host: no self-enable, owner enables, the prompt has the Full authority block, add member, create a team-managed assistant, by=leader event, system message, reorder, open a task; Unlimited is null, D6, caps within the maximum cap; D5 and the other-team notice, one managing team per agent; revoke mid-turn, cap_reached after revoke, changing the team lead revokes; interrupting a job needs the permission; no progress under Unlimited |
| `tests/python/test_team_api.py` | added cases for the `authority` route, `managed`, and the real `_TeamAdmin` (no overwrite, keeps frontmatter, Resonance) |
| `tests/js/test_teams_ui.js` | added cases for the grant box and the Team-managed switch |

## Final review (fresh reviewer, strongest model)

Verdict "Ready with fixes": 0 Critical, 2 Important, 6 Minor. Reordered by impact:
- **Important:** the "team-managed" flag survived removing a member: another team could not take over management, the owner could not turn it off, and re-adding the member brought the flag back to life. Now both removing and re-adding a member clear the flag; the "another team is managing" check only counts active members.
- **Important:** D6 derived the provider on its own, which diverged from the real engine (an old agent with a Claude model but no provider runs Claude Code yet was treated as a background model, so it slipped into Unlimited). Now the provider is the exact label `engine_for` returns; it is only built while the team is on Full authority.
- Other fixes:
  - the daily cap for chat messages is computed by the recipient's provider, so it no longer blocks wrongly when the team lead has Unlimited;
  - the source key of tasks opened by the team lead no longer ends in a number (`_source_id` used to misread the command order as a message id);
  - a prompt edit on a file whose frontmatter cannot be read is rejected (it used to wipe name, role and model);
  - the owner can set a cap without a maximum cap, and the team lead then cannot change that cap;
  - at most 10 admin commands per turn;
  - the caps form in Settings says clearly when Full authority is on (the caps come from the Full authority section).
- Left as is: a revoke landing between reading Full authority and reserving the turn can let one turn run under the old caps (a single turn, accepted).

Review cases #1 to #4, #7, #8 in `test_team_authority.py` were red first, then green; case #5 (`test_team_api.py`) and #6 (`test_teams_ui.js`) were written after the fix.

**UI smoke** (sandbox port 7788, team paused, daily cap 0, daily cap not opened): enabling Full authority through the UI with "Unlimited" turns per task (the number field disables itself), the state and the caps in force show correctly, system message in the team; revoked back to Limited authority; no horizontal scroll at 375px. Screenshots in `exports/reviews/team-t3-smoke/`.
