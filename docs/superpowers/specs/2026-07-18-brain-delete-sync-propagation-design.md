# Design: deleting a brain propagates to every machine through Sync (tombstone + 30-day trash)

Date: 2026-07-18
Status: Design approved, waiting for the implementation plan.

## 1. Background and problem

Jarvis 007 syncs the whole `brains/` folder in both directions between several machines through
a private GitHub repo (`git_brain.sync_brains`, model `machine A ⇄ repo ⇄ machine B/VPS`). The
user's real topology: **2+ machines running in parallel**, all of which can edit/delete.

Sync currently follows the policy "a delete NEVER beats a surviving copy" to prevent data loss:
- `_merge_with_policy` (`git_brain.py`): when one side deletes and the other edits the same
  file, KEEP the edited copy.
- The self-heal block in `_sync_brains_locked` (lines ~663-669): a file present in the mirror
  HEAD but missing from `brains/` is always applied back (restored).
- The restore branch (`_integrate_remote` when `pre_head is None`) and the unrelated-history
  merge (`--allow-unrelated-histories`) pull the whole remote copy back.

Consequence: **a brain deliberately deleted on machine A can be "resurrected"** when syncing
with machine B or a remote that still holds it. The user wants this: deleting a brain is a
deliberate action (the UI forces typing the project name EXACTLY before allowing deletion), so
it must **propagate the delete to every machine** and not be resurrected.

## 2. Goals and out of scope

Goals:
- A single deliberate brain delete (through `/brains/delete`, with the exact name typed) must
  propagate to every synced machine, overriding the "delete does not win" policy for THAT delete
  only.
- Do NOT loosen the general data-loss shield: every case where a folder disappears WITHOUT a
  deliberate delete (volume not mounted, engine half-written, a new empty machine) is still
  protected as before.
- Each machine keeps a local copy (trash) for 30 days for rescue; the delete says so clearly.

Out of scope (v1):
- A "Trash" UI with a restore button. v1 restores by hand (move the folder from the trash back
  to `brains/`).
- Syncing the trash between machines (the trash is LOCAL to each machine, never goes to git).
- A realtime push channel so other machines delete instantly (still relies on each machine's
  sync cycle).

## 3. Design decisions made

- **Option A**: a synced tombstone + a local trash. (Option B "delete always wins" was rejected
  because it breaks the shield; Option C "delete straight on the remote, no tombstone" was
  rejected because machine B still resurrects it.)
- The trash keeps items for **30 days**, auto-cleaned. On delete, the confirmation says plainly
  "kept in the trash for 30 days".
- The tombstone is kept **180 days** (longer than the trash) so a machine that was offline for a
  long time does not resurrect the brain when it returns. This is an internal constant, not
  exposed in the UI.

## 4. Architecture (components)

### 4.1 Tombstone store (synced)
- Location: `<BRAINS_DIR>/.javis-tombstones/<name>.json` - the file name uses EXACTLY the brain
  folder name (the result of `_safe_brain_name`, which already strips the dangerous characters
  `\/:*?"<>|` + truncates to 60 characters, keeping Vietnamese diacritics). One file per brain.
  Because brain folder names are unique and already filesystem-safe, tombstone names do not
  collide, so no separate slug is needed.
- Why one-file-per-name: when merging across machines, files with different names do not
  collide -> git merges cleanly, naturally unioning every delete. Deleting the same name again
  overwrites the file (newer ts).
- This dot-dir syncs with the repo (`_backup_skip` skips only `.git`, the conversations/log
  folders, `.lock`, `.tmp` - it does NOT skip other root dot-dirs) and does NOT show up as a
  brain (`/brains` skips names starting with `.`). Sync reads/writes Vietnamese paths through
  `core.quotepath=false` + `-z` (already in `git_brain`).
- JSON format (`name` = the brain folder name, used to locate the directory when applying the
  tombstone):
  ```json
  { "name": "<brain folder name>", "deleted_at": 1752800000, "host": "<host tag>", "v": 1 }
  ```

### 4.2 Local trash (NOT synced)
- Location: `<STATE_DIR>/brain-trash/<name>__<YYYYMMDD-HHMMSS>/` (OUTSIDE `brains/` so it never
  goes to git; each machine has its own trash). `STATE_DIR` = local `server/`, `/data` on
  Docker - both separate from `brains/` (local `<project>/brains`, Docker mount `/brains`).
- Automatic cleanup: delete entries older than 30 days, run at the start of each sync
  (`_sync_brains_locked`). No GC at startup (keeps the scope tight); sync runs often enough that
  the trash does not bloat.

### 4.3 The tombstone-apply step in sync
- A new function `_apply_tombstones(brains_dir, mirror_dir, trash_dir, sync_start)` in
  `git_brain.py`, called in `_sync_brains_locked` AFTER `_integrate_remote` (the mirror has
  merged the tombstones from every machine), BEFORE the push step. It returns the list of
  deleted brains + errors (if any) to keep the invariant "applied incompletely -> do not push".

## 5. Detailed data flow

### 5.1 Delete flow (`server/main.py`: `/brains/delete`)
Keep the old guards (block deleting the default brain, `confirm == name`, only delete folders
inside `BRAINS_DIR`). Change the execution part:
1. `_safe_brain_name(name)` -> `root = BRAINS_DIR/<name>`.
2. Move `root` into the trash: `<STATE_DIR>/brain-trash/<name>__<ts>/` (use `shutil.move`; if it
   is on a different disk, copytree + rmtree). No more hard `rmtree`.
3. Write the tombstone `<BRAINS_DIR>/.javis-tombstones/<name>.json` (name = the brain folder
   name) with `deleted_at = now`, `host`.
4. Trigger one best-effort background sync (if backup is configured) so the remote receives the
   delete + tombstone right away, instead of waiting for the 6-hour cycle. Do not block the
   response; a sync error does not break the local delete.
5. Return `{ok: true, name, trashed: true}`.

Frontend (`dashboard/brains-ui.js` `deleteBrain`): change the final confirmation into a clear
notice that it "will be moved to the trash, permanently deleted after 30 days, and the delete
will be synced to your other machines".

### 5.2 Sync flow (`git_brain.py`: `_sync_brains_locked`)
New order (inserting the tombstone-apply step), the rest unchanged:
1. Clean trash entries older than 30 days (top of the function).
2. `_sync_mirror(brains_dir, mirror)` + `git add -A` + backup commit (as before). Because the
   brain was already moved into the trash in the delete step, `_sync_mirror` automatically prunes
   the brain from the mirror + the new tombstone gets added.
3. fetch + `_integrate_remote` (as before) -> the mirror merges every tombstone + every change
   from the remote.
4. **`_apply_tombstones`** (NEW): for each tombstone in the mirror after integration:
   - `bn = tombstone.name`; skip if `bn` is the default brain (immune) or the name is invalid.
   - Time guard: if `brains_dir/bn` still exists and any file has `mtime > deleted_at` -> the
     brain was deliberately rebuilt/edited after the delete -> SKIP + remove the tombstone file
     (superseded).
   - Otherwise (a definitive delete):
     - `brains_dir/bn` (if it still exists): move it into the trash (hold
       `BrainLock(brains_dir/bn)` while doing so; if the lock cannot be taken after the timeout,
       skip this round and apply again next time - no blind delete).
     - `mirror/bn` (if it still exists): `git rm -r --` to stage the delete.
   - If any `git rm` happened: commit the mirror with `sync: áp tombstone xóa <n> não` (Vietnamese
     commit message, "sync: apply tombstone, delete <n> brains") so HEAD reflects the delete ->
     the self-heal block (5.3) does not resurrect it.
   - Return `{deleted: [...], failed: [...]}`. A non-empty `failed` -> keep the invariant:
     roll back the mirror + do NOT push (same as the existing failing `_apply_back` branch).
5. The self-heal block (lines ~663-669) + `_apply_back` + push: as before. Because the tombstone
   already removed the brain from the mirror HEAD, self-heal no longer sees it as "missing from
   brains" (it was legitimately deleted on both sides).

Machine B on its sync: fetch receives the tombstone (step 3) -> `_apply_tombstones` deletes the
brain on B (moved into B's trash) + git rm from B's mirror -> push (if B is the pushing side) or
simply is already in agreement with the remote. The delete propagates without B ever knowing the
original delete command.

### 5.3 Why it is no longer resurrected
- modify/delete "keep the edited copy": even when the merge keeps a few of the brain's files,
  `_apply_tombstones` running AFTER will definitively delete that brain's whole subtree (because
  a tombstone exists).
- The self-heal block: runs AFTER the tombstone has committed the delete out of the mirror HEAD
  -> sees nothing "missing".
- The restore/unrelated-history branch: after pulling the remote copy, the tombstone (also inside
  that remote copy) is applied -> deletes again the brains that have tombstones.

## 6. Safety guards and invariants

- A tombstone can only delete a brain that is a **direct child** of `brains_dir` (check that
  `resolve()` sits exactly under `brains_dir`, like the guard in the current `/brains/delete`).
  It never touches anything wider.
- **The default brain is immune**: `_apply_tombstones` skips a tombstone pointing at the default
  brain's name. The delete flow already blocks deleting the default brain so that tombstone
  cannot legitimately arise; this is a two-layer block.
- **Time guard**: a brain with a file newer than `deleted_at` is treated as deliberately rebuilt
  -> not killed.
- **No half-done push**: a failing move-to-trash or git rm -> `failed` -> roll back the mirror,
  postpone the push.
- Tombstones are only produced by `/brains/delete` (exact name typed). No other endpoint creates
  a tombstone.
- `_safe_brain_name` sanitizes the name before every path operation.

## 7. Testing

A new test file in `server/` (following the existing test pattern: standalone, run with
`python test_*.py`, no real network - use a local `file://` remote). Cases:
1. **Delete propagation**: set up brains_A, brains_B, mirror_A, mirror_B, a bare `file://`
   remote. Create brain "Foo" on both, sync to bring them into agreement. Delete "Foo" on A
   (tombstone + move to trash), sync A -> push. Sync B -> "Foo" is deleted on B, sits in B's
   trash, and the remote no longer has "Foo".
2. **Time guard**: after the "Foo" tombstone exists, recreate a new "Foo" (file mtime >
   deleted_at) and sync -> the new "Foo" is NOT deleted, and the tombstone is removed.
3. **Protection when there is NO tombstone**: manually delete the folder "Bar" from brains_B
   (not through the endpoint, no tombstone) then sync -> "Bar" is restored (the old shield
   intact), not permanently deleted.
4. **Default brain immune**: a fake tombstone pointing at the default brain ->
   `_apply_tombstones` skips it, the brain stays.
5. **Delete endpoint**: call `/brains/delete` -> the brain goes into the trash
   `<STATE_DIR>/brain-trash/...`, the tombstone is written, and it is no longer in `brains/`.
6. **Trash cleanup**: create a fake trash entry with mtime > 30 days -> it is deleted after the
   cleanup runs; a new entry is kept.

## 8. Risks and open questions

- A machine offline for > 180 days that comes back could still resurrect a brain (the tombstone
  has been cleaned up). Acceptable: rare, and the constant can be relaxed if needed. Not
  exposed in the UI.
- A rare conflict: two machines delete the same name almost simultaneously -> two tombstones
  with the same slug, merged by the existing policy (nearly identical content, no loss). No
  extra handling needed.
- An eager sync at delete time may coincide with the scheduled sync: there is already a
  `_SYNC_LOCK` (non-blocking) so the overlapping run is safely skipped, and the tombstone still
  goes out in the next run.
