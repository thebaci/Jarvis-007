# Team chat T0: the Resonance switch on the assistant row (0.110.0)

Spec: [2026-10-13-team-chat-design.md](../superpowers/specs/2026-10-13-team-chat-design.md) section 10 (D1 to D7 settled). Plan: [2026-10-13-team-chat-t0-t1.md](../superpowers/plans/2026-10-13-team-chat-t0-t1.md), part T0.

## Changes

- **Partners page** (`dashboard/workspace.js`):
  - Reads `GET /resonance/agents` once, in the same pass as `/agents`. If this request fails the list still shows and the row has no switch (the state is not guessed).
  - Each assistant row shows "Auto: On/Off" (the Resonance state label on screen) and a switch (`rowToggleHtml`). The switch sits outside the item-select button.
  - An assistant that is `missing` or `retired` gets a "Needs confirmation" / "Retired" button, which opens the right column on the Settings tab, where the two A1 confirm buttons are.
- **Clicking the switch** (`toggleAgent` in `dashboard/resonance-agent.js`):
  - calls A1's own `POST /resonance/agents/toggle`, with no `session_id`;
  - locks while waiting; changes only when the server returns `ok`;
  - on error, states the reason under the filter bar and reloads the real state;
  - turning off an assistant that still has open goals asks again, with the number of goals.
- **One place only:**
  - the Resonance panel in the right column keeps only the state text and the line "Turn it on or off in the assistant list on the left";
  - the Settings page keeps only the summary "N assistants have Auto on", a button to the Partners page, the text list of assistants needing confirmation, orphaned items, Waiting for assignment, and the old-brain note.
- **Two-tab sync:**
  - the enable, disable and confirm routes broadcast a WS packet `{"type": "resonance_agents"}` (`ResonanceApiDeps.broadcast` calls `ChatRuntime.publish`); a failure of this packet does not break the owner's command;
  - `app.js` turns the packet into the event `javis:resonance-agents-changed`; the Partners page, the right panel and the Settings page reload the real state.
- **`.gitignore`:** added `server/resonance.sqlite3*` and `server/team.sqlite3*`, because a server run from a worktree without `JAVIS_STATE_DIR` set would write these stores into `server/`.
- **A1 contract unchanged:** only the owner can change it; `missing` needs confirmation; turning off always works; the state of an open session is still asked of the host by the right panel (`session_id` on `GET`).

## Checks

| Command | Result |
|---|---|
| `python tests/run.py team_t0 resonance_a1 resonance_a5_ui workspace i18n route_table ignore_files` | 18/18 green |
| `tests/js/test_team_t0_toggle.js` | State as text; switch on the row; `missing`/`retired` have no toggle box; locked while saving; nothing drawn when there is no data; HTML injection blocked; asks again on turn-off; right panel and Settings page no longer have a switch; `toggleAgent` with 200, 409, network drop; wiring on the Partners page, `app.js`, CSS |
| `tests/python/test_team_t0_broadcast.py` | Enable and disable broadcast exactly one packet; 404 broadcasts nothing; a failed packet still lets the command succeed |

**UI smoke test** (sandbox on port 7788, state inside the worktree, zero model turns). Screenshots are in `exports/reviews/team-t0-smoke/`, outside the repo.
- The row shows "Auto: Off"; a name with HTML characters appears verbatim.
- Turning on Lan: changes to "On" after the server confirms.
- The right column shows only the state text.
- The second tab changes by itself when the first tab turns on Minh, no F5.
- Moving Lan's file away and back: the row says "Needs confirmation"; clicking "Same assistant" returns both tabs to "On".
- The Settings page shows "2 assistants have Auto on.", with no switch.
- At 510px width: the left column becomes a drawer, and the switch is still usable.

## Limits

- The confirm dialog for turning off an assistant that still has open goals was checked only by unit test: the sandbox has no goals.
- The team member list (spec section 10.1) does not exist yet: it belongs to T1.
