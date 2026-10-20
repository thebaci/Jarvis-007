# A bot in a Zalo group tags the person it is replying to (0.65.7)

## Problem

The project owner (30 Sep 2026): in a Zalo group, when a customer asks something, the bot should open its answer with "@Minh Quý ...", so the asker gets notified and the whole group knows
who the bot is talking to. The send tool of the `zalo-agent-cli` MCP accepts text only so it cannot tag; the CLI itself does have `msg send --mention` (already
used in 0.65.6 for the `zalo_send_mention` tool, see `2026-09-30-zalo-tag-ghi-chu-poll-design.md`).

## Decisions

- **No settings toggle.** On by default for every personal Zalo group the bot is in (the owner wants few settings, the machine handles it).
- **Groups only.** A private chat does not need a tag.
- **The tagged person = the sender of the message the bot is replying to** (`meta["user_id"]`, `meta["user_name"]` supplied by the read loop). The "Reply for me" button
  in the Inbox also tags the sender of the last customer message, to match the bot's own replies. When the owner types by hand, there is no tag.
- **2 to 4 seconds slower per reply** (one more CLI process runs). The owner has accepted this.

## Approach

`channels.zalo_personal.gui(tk, chat_id, text, chat_type, mention=None)`: when it is a group and `mention={"uid","name"}` is given, it sends through
`zalo_cli.run_cli` (`msg send <group> <text> -t 1 --mention pos:uid:len`). `channels.gui` passes `**extra` to the channel (only personal Zalo uses it).
`Transport._gui` and the route `POST /conversations/{id}/ai-reply` are the two places that pass along the person to tag.

Text: if the model already wrote "@Name", the tag goes at exactly that spot; if not, "@Name " is placed at the start of the message. The position is measured in UTF-16 (an emoji counts as 2);
"@Quý" does not eat into "@Quýnh". (Quý and Quýnh are Vietnamese names, kept as the example of the name-boundary check.)

## Fragile spots (canaries already exist in `test_bot_zalo_tag.py` and `test_bot_zalo_nhom.py`)

1. **Two messages under the owner's name.** A timeout is an unclear outcome (the CLI may have finished sending before being killed). Only when the CLI fails CLEARLY does it fall back to
   a normal send through the MCP. On timeout it returns an error (written to the bot log) and does not resend.
2. **The bot silences itself.** The echo of a tagged message carries the "@Name" too, so it does not match the sentence the bot remembered; the read loop thinks the owner just typed and the bot stays quiet for
   10 minutes. Remember the tagged version as well (`ghi_da_gui`) BEFORE sending. Try both the form with the isSelf flag and the one without.
3. **A permanently broken tag slows every reply.** After 3 consecutive failures, tagging rests for 10 minutes; messages still go through the MCP as before. One success resets the count.
4. **uid goes into a command argument.** Only all-digit uids are accepted; if the asker's name is not yet known, a normal send is used.

## Speed (0.65.8)

Measured on the owner's Windows machine: `npx -y zalo-agent-cli@1.6.2 --version` takes 3.1 seconds (three measurements 3.06 to 3.32), while `node index.js --version` of the
pre-installed copy takes 0.72 seconds. Both exclude login and sending. So `zalo_cli` keeps ONE pinned copy in `<state>/tools/zalo-agent-cli`
(`npm install --prefix`, about 7 seconds, once) and runs `node index.js` directly; until the install finishes it still runs through npx as before.

- The silent install starts on the first `run_cli` call when no install exists. That call still goes through npx and does not wait for the install. If it fails, it waits 30 minutes before trying again.
- The `.javis-installed` marker (written AFTER the install finishes, containing exactly the pinned version string) decides whether to use it: a half-finished install or a changed pinned version means it is not used.
- On Linux, the Zalo session's HOME is its own directory, so npx may re-download the whole package into that HOME's cache on every connection; a fixed install directory avoids this too.
- If Windows cannot find `npm-cli.js`, the install is skipped (no path is put into cmd.exe); the npx route still works.
- The first run after install may be slow because antivirus software scans the new files (measured at 7.7 seconds once, then 0.7 seconds); still within the 40-second cap.

## Out of scope

- Tagging several people, tagging a person mentioned in the answer (`zalo_send_mention` already exists for that, called deliberately by the model).
- Tagging in Zalo Bot (OA) groups or Telegram: different channels, different mechanisms.
- Using Zalo "reply" (quoting) instead of a tag: CLI 1.6.2 does not offer it for `msg send`.

## Testing

A fake CLI and a fake MCP. Real sending into a Zalo group has to be tried by the owner on a real account (the sandbox has no account): a customer asks in the group, the bot answers
"@Name ...", the asker gets a notification, and the bot does not reply to itself afterwards.
