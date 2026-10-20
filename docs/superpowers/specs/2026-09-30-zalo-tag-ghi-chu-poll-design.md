# Zalo: tag the right person, notes, reminders, polls (0.65.6)

## Problem

The project owner (2026-09-30): in a Zalo group, Jarvis 007 cannot tag the exact person who needs a reply (like "@minhquy"), and cannot yet
create notes, reminders or polls on Zalo.

The MCP of `zalo-agent-cli` version 1.6.2 exposes only seven tools, and the send tool (`zalo_send_message`) takes text only. But that same CLI already
has all four features: `msg send --mention`, `group note-create`, `reminder create`, `poll create` (checked by reading the source and by running it with Commander 14.0.3, the version the CLI bundles).
1.6.2 is the newest version on npm, so waiting for upstream to expose more tools means waiting forever.

## Approach

Same mold as `zalo-image` (0.36): a new bundled plugin `zalo-group` that calls the CLI itself with the Zalo session that is already signed in (setting `HOME` to the
connection's session folder), with no package fork and no second QR scan. Five tools, callable by every engine through the MCP Hub:

| Tool | Job | Minimum level |
|---|---|---|
| `zalo_group_members` | group members (uid + name), or look up by name | read-only |
| `zalo_send_mention` | send a group message, tagging the right person | full |
| `zalo_create_note` | group note, can be pinned | full |
| `zalo_create_reminder` | reminder shown inside Zalo, can repeat | full |
| `zalo_create_poll` | poll for the group | full |

The shared CLI-running part is split out into `server/zalo_cli.py` for both `zalo-image` and `zalo-group`.

## Easy places to break (canaries are in the tests)

1. **Tagging the wrong person.** Zalo tags by uid, but the user only says a name. Look in two places: people who have posted in the group (Inbox,
   `conversations.group_speakers`), then the Zalo member list (`group info` + `group members-info`). Normalize ignoring case, diacritics and spaces.
   An exact match beats a contains match. **A duplicate name, or no match, returns an error with candidates, never a guess**: a wrong tag cannot be taken back.
2. **Text position.** Zalo reads `pos:uid:len` in UTF-16 units like JavaScript (an emoji takes 2). Counting by Python characters shifts the highlight.
   `@Quý` must not eat into `@Quýnh` (`(?!\w)`).
3. **Argument order.** The multi-value flag `--mention` swallows every argument after it, so positional arguments go first and flags after.
   An argument that starts with `-` is treated as a flag, so in that case the flags go first, then `--`.
4. **Lying exit codes.** The CLI does not exit non-zero when Zalo refuses (`error()` only prints "✗ ..." to stderr). Success = exit code 0 **and** JSON on stdout.
   This also fixes `zalo_send_image`, which used to report "sent" even when Zalo refused.
5. **Reminder time.** The CLI reads `--time` in the MACHINE's time zone; the user speaks in Jarvis 007's time. On a VPS in UTC, "9 am" becomes 16:00 if sent as typed.
   Convert to the machine clock before calling, and reject times already in the past.
6. **Windows + cmd.exe.** When `npx.cmd` runs through `cmd /c`, the characters `& | ^ %` in the message body are interpreted by cmd (breaks the message and is a command injection hole).
   Run `node npx-cli.js` directly; if it falls back to cmd, refuse dangerous arguments.
7. **Timeout = unknown outcome.** The CLI may have finished creating the item before it was killed. The error says "unknown whether it was created, check the group before trying again", to avoid two polls.
8. **Several Zalo accounts.** Without a `connection_id`, refuse and list the options, never guess (sending from the wrong account means sending under someone else's identity).

## Out of scope

- The bot tagging the person it is replying to by itself: done in 0.65.7 (switch the bot's send path to the CLI, a few seconds slower per reply).
- Editing or deleting notes, reminders, polls; voting in a poll; locking a poll. The CLI has these, nobody has asked yet.
- Adding long instructions to the system prompt: only one short line in `CLAUDE.md`, the detail lives in the tool descriptions.

## Testing

`tests/python/test_zalo_group.py` (runs against a fake CLI: checks the exact command built, tag positions, name lookup, duplicate names, reminder time, Zalo errors, several accounts,
plugin declaration) and `tests/python/test_zalo_cli.py` (argument order, Windows, result reading, HOME, timeout). Actually sending into a Zalo group must be tried by the
owner on a real account; the sandbox has no Zalo account.
