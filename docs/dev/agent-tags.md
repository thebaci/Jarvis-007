# Agent tags (0.100.0)

Agents are classified by **multiple tags** instead of a single group. Project owner's decision: "Real tags: every agent can carry several tags, and the old group becomes one tag."

**Only agents change.** Workflows and skills keep the `group` field and their existing contract. The Zalo group, the team chat group and the Resonance work/review team are three different concepts, unrelated to tags:
- A **tag** is only for classifying and finding agents (Marketing, Content writing, Engineering).
- A **chat group** is where the user and several agents talk. Attaching a tag does not add anyone to a chat group.
- An **execution team** (Resonance A5, being designed) is the maker and reviewer of one goal. A tag does not pick a reviewer, grant permission, turn on Resonance, change a quota or open a model turn.

## Data contract

### Frontmatter of `agents/<slug>.md`

```yaml
tags:
- Marketing
- Viết nội dung
```

(`Viết nội dung` = "Content writing", kept in Vietnamese here because tags are free-form user text and the Vietnamese diacritics matter below.)

- `tags` is the **source of truth** whenever this key is present, even `tags: []` (the user removed every tag).
- An old file **without a `tags` key**: read the real `group` in the frontmatter. A non-empty string `group` becomes exactly one tag (a real `group: Chung` becomes the tag "Chung"). No `group`, or an empty `group`, means no tag yet. Do not infer a tag from the "Chung" label that the old API fills in on its own.
- `tags` as a single string (a human or model hand-writing `tags: Marketing`) is read as one tag. Elements that are not strings, or are empty after normalisation, are skipped on read.
- **`group` mirror** (so a downgrade still has a label): on every canonical write, `group` = the first tag; with no tags left, delete the `group` key. Once `tags` exists, code from 0.100.0 on does NOT read the agent's `group`.
- Written with `yaml.safe_dump` like every other frontmatter, read with `fastyaml.safe_load`: a list comes back as a list, and strings with special characters are quoted.

### Normalisation and duplicates

- Unicode NFC; strip control characters; collapse every run of whitespace into one space; trim both ends.
- Empty after normalisation: not a tag.
- **Limits apply to NEW input only** (review round 1, R1): a tag the user adds, a whole-set replacement or a rename that goes past 40 characters is rejected (`tag_too_long`); an add that makes the set exceed 20 tags is rejected (`too_many_tags`).
- **Existing data is never truncated:** an old group longer than 40 characters (valid in 0.96.1) or a file with more than 20 tags is read whole and shown whole (the chip clips the text with CSS, the full name is in the title), and pinning, saving a form and importing a pack write back exactly what was read. Removing, renaming (the source name) or deleting a long tag still works; removing a tag while over 20 always works.
- **Identity key** = the normalised form, then Unicode `casefold()` (`agent_tags.tag_key`): "Marketing" and "marketing" are one tag; "Straße" and "STRASSE" are one tag; "Viết" in NFC and in NFD are one tag. Vietnamese diacritics are part of the tag: "Viết" and "Viet" are two different tags. Diacritic-free search is only for finding, it does not merge tags. Within one agent the first spelling seen is kept; across agents the spellings may differ but share a key.
- **One identity for every layer** (R3): the API returns `tag_keys` alongside `tags`; the Partners page and Studio count, filter and tick by that key and never compute their own (the browser's `toLowerCase` differs from `casefold`). The UI only displays the spelling the server returns.

### API

| Route | Agent | Notes |
|---|---|---|
| `GET /agents`, `GET /agents/get` | Returns `tags` (the normalised list) and `tag_keys` (identity keys, same order) | Still returns `group` = the first tag or "Chung" for old pages still in cache. Does not send a separate request per agent |
| `POST /capability/meta`, `kind=agent` | `add_tags` (JSON list): add to the existing set. `remove_tags` (JSON list): remove exactly those tags. `tags` (JSON list): replace the whole set, `[]` removes all | Sending no field = keep as is. Read and write happen in one server step, so two tabs adding/removing different tags do not overwrite each other |
| `POST /capability/meta`, `kind=agent`, only `group` (old client) | Agent already has two or more tags: reject with `409 stale_client` ("Trang đã cũ, tải lại trang", meaning "The page is out of date, reload it"), change nothing. Has at most one tag: a non-empty `group` becomes exactly one tag, an empty one removes the tag (the old meaning "back to Ungrouped") | Never silently replaces several tags with one |
| `group` sent together with `tags`/`add_tags`/`remove_tags` | Reject with `400 group_and_tags` | A clear conflict rule, no guessing |
| `POST /agents` (agent edit form) | No `tags` sent = keep the tags. `tags` sent (JSON) = replace the whole set. An old client's `group` follows the rule in the row above | A new agent with no tags sent gets `tags: []` |
| `POST /agents/tags/rename` (`brain`, `from_tag`, `to_tag`) | Renames a tag (compared by key) on every agent that has it, keeping the other tags. If `to_tag` has the same key as an existing tag they are merged, not doubled, using the spelling of the existing tag | Returns `changed`, `failed`, `merged`, `tag`, `tag_key`. If an agent write fails, `ok: false` with the lists of what was done and not done |
| `POST /agents/tags/delete` (`brain`, `tag`) | Removes that label from every agent | Does not delete agents, chat sessions, goals or teams. Returns as above |
| `kind=workflow` | Unchanged; sending a tag parameter for a workflow is rejected with `400` | |

Every tag belongs to **one brain** (that brain's `agents/` folder). Renaming or deleting a tag in this brain does not touch other brains.

**Write synchronisation and the event loop** (R4, R5): every path that reads, edits, writes or DELETES an agent file runs in a worker (`asyncio.to_thread`) and goes in sequence through the SAME lock (`_AGENT_META_LOCK`):
- `/capability/meta` (agent), tag rename, tag delete, the form's `POST /agents`, the six agent document/link routes (`/agents/{slug}/assets/...`), and `POST /agents/delete`.
- Reading `previous`, checking the file still exists, and then writing all sit inside the lock. Waiting for the lock also happens in the worker, so a multi-agent operation or a delete waiting for the lock does not block the event loop when the disk is slow.
- A form save interleaved with adding/removing tags does not overwrite them.
- **Deleting an agent is not undone** (R5): if a write is holding the lock, the delete waits for it to finish and then deletes. An operation arriving after the delete sees the file gone and does not recreate it: `/capability/meta` and the document routes return 404; a bulk tag rename or delete skips that agent (it goes in neither `changed` nor `failed`).
- `POST /agents` (form) is still create-or-edit as before: saving the form after the agent was deleted creates a NEW agent with the same name, carrying no old tags or role, and under rule A1 Resonance has to be turned on again.
- Workflows stay as they were before 0.100.0: `/capability/meta` for a workflow edits directly on the event loop like the other workflow routes (save, toggle, delete), not through a worker or this lock.

The numbers in the tests are simulated I/O (a write slowed by 80 ms, a barrier holding the worker), not measurements on a real machine.

## Migration

- **Read compatibly, write canonically on save.** There is no bulk migration, and no sweep that rewrites files when the list loads.
- An old agent is rewritten into the canonical form (`tags` + the `group` mirror) the first time a save operation touches it: saving the form, pinning, attaching or removing a tag, renaming or deleting a tag. Writing canonically twice gives the same result (safe to repeat): once a tag set exists it reads `tags` and does not read `group` again.
- Every other frontmatter key and the prompt body stay as they are (read, then only the tag key is edited). Written atomically with `_atomic_write_text`.

## Import, export, index, creating from chat

- **Export** copies the agent file as is: a new pack carries `tags`.
- **Import** writes the file as is: a new pack keeps all its tags; an old pack with only `group` is read as exactly one tag under the old-file rule, and becomes canonical on the first save.
- **Index** `Javis/index.md`: each agent is listed once, with "tags: A, B"; workflows and skills are still split by group.
- **Creating an agent from chat** (`javis-builder`, `CLAUDE.md`): the agent template uses `tags:` (a list), and reads the tags in use in `agents/*.md` before choosing.

## Rolling back

- **Downgrade to 0.96.1 (old code):** old code reads `group`, so an agent appears under the group = the first tag (the mirror), and an agent with no tags appears as "Chung" (General). The `tags` key stays in the file and old code keeps it on save (it has kept every unknown key since 0.59.x). Checked in a browser with `main` 0.96.1 opening a copy of the migrated data.
- **Limit:** an agent file that has `tags` but was never saved by 0.100.0 code (a human or model hand-writing only `tags`, or a pack imported from elsewhere) has no `group` mirror yet, so old code shows it as "Chung" until it is saved once by the new code. No tag is lost.
- **Upgrading to 0.100.0 again:** `tags` is the source of truth. Group changes made with old code during the downgrade (editing `group`) are **not** carried into tags; to keep them, attach the tags again. This is a known limit; in exchange a removed tag never comes back to life from `group`.
- There is no separate file backup: the migration only adds the `tags` key and syncs `group`, and deletes no content.
