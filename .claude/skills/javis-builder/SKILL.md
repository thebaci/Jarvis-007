---
name: Jarvis 007 Builder
description: "Create or edit a Jarvis 007 capability: agent, skill, workflow, loop, plugin. Ships file templates and the rules against duplicates."
description_en: "Create or edit a Jarvis 007 capability: agent, skill, workflow, loop, plugin. Ships file templates and the rules against duplicates."
group: AI
---

# Jarvis 007 Builder - create an agent / skill / workflow / loop

## When to use

Activate when the user says things like: "create an agent for X", "add a skill for Y",
"build a workflow that researches then writes", "create a loop that does Z every 2 hours", "write a tool/plugin
that calculates ...", "make Jarvis 007 able to ...".

When the user wants Jarvis 007 to gain a capability, you WRITE THE .md FILE YOURSELF in the standard below into the
vault (the brain currently selected). Studio / the matching page picks up the new file on its own. Always give a short report after creating it.

## Procedure (follow this order)

1. **Understand the need.** If the description is clear enough, just do it; if a core point is missing (goal, desired
   output), ask 1 short question and then do it. Do not ask rambling questions.
2. **Pick the right TYPE of capability:**
   - A reusable how-to or knowledge for answering, needed many times -> **skill**.
   - A specialist "role" with its own system prompt -> **agent**.
   - A chain of several steps, several roles linked together -> **workflow** (create any missing agents first).
   - Work that REPEATS on a cycle and runs by itself in the background -> **loop**.
   - A new native TOOL is needed (doable in Python, reusable, callable by every engine) and no MCP exists -> **plugin**. Only instructions on how to work with existing tools -> skill. An external data source that already has an MCP -> connect the MCP.
   - A one-off job -> create NOTHING, just do it or propose a Kanban task.
3. **Avoid duplicates.** BEFORE creating, read the matching folder (agents/ workflows/ skills/
   loops/). If something similar already exists -> update the old one, do not spawn a copy.
4. **Write the file** with the right frontmatter (templates below). slug = ASCII without diacritics, hyphenated. The display name
   is in the user's language. NEVER use the em dash character, use "-".
   **Classification is MANDATORY.** An agent uses `tags` (a list, several tags allowed); a skill and a workflow
   use `group` (a single group). Before choosing, read the tags in use in `agents/*.md` and the groups in use
   in `workflows/*.md` and `skills/*/SKILL.md`, then take the closest one; if none fits, make up
   a new short name by domain. An agent with empty `tags` lands in "Untagged", a skill/workflow with empty
   `group` falls into "General". A tag is only for sorting and finding agents: it does not add an agent to a chat group,
   does not pick a reviewer, does not grant permissions.
5. **Short report** in spoken prose: what type you created, the name/file path, where it is used.

## File templates (write EXACTLY like this)

### Agent -> `<brain>/agents/<slug>.md` (FLAT at the brain root - NOT Javis/agents, the app will not see anything written there)
```
---
type: agent
name: <display name>
slug: <ascii>
role: <role in 1 sentence>
tags: [Marketing, Copywriting]   # one or more tags; examples: Marketing, Sales, Content, Operations, Finance, AI, Productivity, Personal
skills: [slug-skill]      # [] if none assigned yet; only assign skills that already exist in skills/
model: ""                 # "" default | sonnet|opus|haiku|fable (Claude) | gpt-5.5|gpt-5.4|gpt-5.3-codex (ChatGPT/Codex)
updated: <YYYY-MM-DD>
---
<system prompt: how to work, principles, desired output format>
```

**Write the agent's system prompt in the metaprompt frame** (taken from Anthropic's metaprompt - do NOT write 1-2 generic sentences like "you are an expert in X"):
1. Role + goal: 1 sentence naming the role, 1 sentence saying what a good result looks like.
2. Business context: 2-3 lines about the product/customers/field, taken from Memory if relevant.
3. Procedure: numbered working steps, in the order the agent should really do them.
4. Output format: be SPECIFIC (length, structure, tone, language); if the output has a fixed shape, attach 1 short sample.
5. Hard cases: what the agent does when data is missing / the request is ambiguous / out of scope (state an assumption and continue, ask 1 question, or refuse).
6. Prohibitions: only SPECIFIC ones with a reason (e.g. do not invent numbers, no em dash), do not write a whole string of "must not".
A good prompt is usually 10-25 lines. After writing, read it as a fresh agent would: is it enough to do the work without asking anything more? A skill body follows the same frame (drop item 1, replace it with a description of the trigger).

### Skill -> `skills/<slug>/SKILL.md`
```
---
name: <Skill name>
description: <state the capability DIRECTLY, AT MOST 150 characters - e.g. "Summarize meeting minutes into a to-do list.">
group: <Marketing|Sales|Content|Operations|Finance|AI|Productivity|Personal>
---
<detailed instructions for the AI when the skill activates>
```

#### Skill writing standard (mandatory - NOBODY is guarding this, you must hold the line yourself)

**There is no safety net.** A skill written by following this document is WRITTEN STRAIGHT TO DISK: it does not go through
`POST /skills`, so there is no server-side check, and the CI lint only inspects SYSTEM skills, not
skills in the brain's `skills/`. Breaking the standard below produces NO error message at all -
the skill just silently breaks at run time. You are the only line of defense.

1. `description` is **AT MOST 150 characters**. **After writing, COUNT, do not estimate** - this is
   mandatory, not advice. The router cuts at exactly that point (`skill_router.SKILL_DESC_MAX`) in
   both the system prompt and the tool description, so anything longer has its tail LOST SILENTLY and the skill cannot be
   routed. Nobody warns you: not counting means it breaks without you knowing.
2. `description` states the capability DIRECTLY. Do NOT open with "Activate when...", "Use this skill
   when..." - every skill opens that way, so it burns 29 characters and distinguishes nothing.
   Good: `Summarize meeting minutes into a to-do list.`
   Bad: `Activate when the user wants to summarize meeting minutes...`
3. If `description` contains a colon, the whole value must be wrapped in double quotes, or YAML
   reads it as a mapping.
4. Put the full trigger examples in the BODY, in the `## When to use` section - where nothing is cut and which is only
   read once the skill is loaded. The index is for FINDING, the body is for DOING.
5. Order of sections in the body: `## When to use` / `## Preparation` / `## How to run` /
   `## Procedure` / `## Pitfalls` / `## Verification`. Drop any section with no real content,
   do not invent filler.
6. Do NOT invent flags, paths or APIs you have not seen in the source. If you did not see it, do not write it.
7. Keep the body around 100 lines for a simple skill, 200 for a complex one. Longer than that, move
   the content down to `skills/<slug>/references/<topic>.md`, scripts down to
   `skills/<slug>/scripts/`, and point to them by relative path. Since version 0.9.64: the mirror
   into `.claude/skills` (the route Claude Code loads NATIVELY) copies the whole tree RECURSIVELY, so for a skill
   in the brain, `references/`/`scripts/` are reachable by BOTH the router route and the native route. Since version
   0.33.0, SYSTEM skills (bundled with the app, installed into the brain via system sync) also ship the WHOLE
   subtree - before that it carried only `SKILL.md`, so any system skill that needed `tools/` was broken in
   every brain. Writing a system skill with a subtree is now valid.
8. Do NOT write a router-style skill that only points to another skill.

### Workflow -> `<brain>/workflows/<slug>.md` (FLAT at the brain root - NOT Javis/workflows)
```
---
type: workflow
name: <Name>
slug: <ascii>
status: 'off'             # new ones start 'off' so the user can preview and then turn them on; KEEP the quotes (bare off = boolean). A workflow that is off does not run in the background
group: <Marketing|Sales|Content|Operations|Finance|AI|Productivity|Personal>
description: <short description>
steps:
  - agent: <agent-slug>
    task: "<the job; {{input}}=user input, {{prev}}=result of the previous step>"
    verify_agent: <agent-slug>   # optional: an agent that checks for errors, MUST return JSON {"pass":true|false,...}; if it still fails after max_retries the workflow STOPS
    max_retries: 1               # optional
    tools: [javis_generate_image] # optional: the plugin tool this step needs when running in the background under Full access (e.g. create/view images); WebFetch, WebSearch are also accepted
updated: <YYYY-MM-DD>
---
<description>
```
If the workflow references an agent that does not exist yet -> CREATE that agent first.

### Chat group -> tool `javis_team` (do NOT write files by hand, do NOT drive the browser)
The user wants a chat group made of several assistants: call `javis_team` op=create once, `members` are the slugs of existing assistants, `new_agents`
are the assistants to create new (`name`, `role`, `prompt`, `model`, `model_provider` if a separate model is wanted), `leader` is the slug or name of the group
leader. To edit: op=update, add_member, remove_member, set_leader, set_agent_model. To delete: op=archive first, then op=delete with confirm=true only
when the user clearly says to delete. Preview the existing assistants with op=list_agents to avoid creating duplicates.

### Loop -> `Javis/loops/<slug>.md`

**For a NEW repeating job: prefer CALLING the tool `javis_schedule`** (op=create, name/prompt/schedule - e.g.
schedule="120m" or "every 2 hours") instead of writing the file yourself. The tool sets the right slug, the right frontmatter
(including `goal: custom` below - missing this field is a real bug that has happened: self_improve.py defaults to
`goal: business`, so the loop only reads MCP numbers and COMPLETELY IGNORES the task in the file body), and blocks
duplicate names. **Write the file by hand ONLY** (template below) when: (a) EDITING an EXISTING loop, or (b) you need an advanced
field the tool does not accept yet - `quiet_hours` (quiet hours, e.g. "23-07"), `max_runs_per_day`, `workspace`
(+ `tools_profile: code` when the loop edits code in an outside folder - it has Bash/Web, NO MCP),
`ambient_mcp` (lets the loop SEE the machine's claude.ai connectors - Gmail/Drive/calendar; OFF BY DEFAULT so a clean
fork stays clean, turn it on only when the user clearly asks; Bash/Web remain hard-blocked), `notify: false` (when a loop is too noisy,
stop it reporting every iteration), or a `goal` other than `custom` (`business`/`brain`/`product`).
```
---
type: loop
name: <Name>
slug: <ascii>
enabled: false            # ALWAYS create it OFF - the user presses Turn on on the Work page
mode: full                # full=full access (DEFAULT) | auto=drafts only | suggest=read/suggest only
goal: custom              # REQUIRED when writing by hand - without this line self_improve.py defaults to
                           # 'business' (reads MCP numbers only, ignores the file body below entirely)
interval_min: 120         # minimum 5
owner_chat: "<chat_id>"   # chat_id of the PERSON WHO ASKED (created through Telegram chat) - so reports reach the right person;
                           # leave empty if created on the web (reports go to the first Telegram ID)
updated: <YYYY-MM-DD>
---
<task description: each loop iteration does EXACTLY this work - this IS the loop's prompt, write it self-contained>
```

### Plugin -> GLOBAL by default `<JAVIS_STATE_DIR>/plugins/<slug>/` (shared by every brain); for one brain only, `<vault>/plugins/<slug>/`. 2 files: plugin.yaml + plugin.py
`plugin.yaml`:
```
name: <display name>
slug: <ascii>
version: 1.0.0
description: <what this tool does, when engines should call it>
author: <who created it>
enabled: false            # ALWAYS create it OFF
min_mode: readonly        # readonly=read/compute only (default) | safe=writes | full=real actions
tools: [<ten_tool>]
hooks: []                 # e.g. [post_tool_call] if a hook is used
```
`plugin.py`:
```python
def register(ctx):
    def handler(args, ctx):            # args=dict; return str (or dict). On error -> "ERROR: ...". May be async.
        return "..."
    ctx.register_tool(
        name="ten_tool", description="description for the engine + parameters",
        handler=handler, min_mode="readonly",
        schema={"type":"object","properties":{},"required":[]})
    # optional hook: ctx.register_hook("post_tool_call", lambda tool_name="", **_: None)
```
ctx has `ctx.vault_root`, `ctx.data_dir` (the plugin's own state, does not touch the vault), `ctx.slug`.

## Safety rails (MANDATORY)

- A loop created through chat is ALWAYS `enabled: false` (the user presses Turn on on the Work page) and defaults to `mode: full`:
  the project owner dropped the rule "never hand money/orders/posting/customer messaging to automation" (2026-09-10), so a
  loop that acts on the outside by itself needs NO risk warning. Only lower to `mode: auto/suggest` when the user
  wants that loop to be lighter.
- NEVER let one loop/automation create or turn on another loop by itself (stops unbounded growth) - only PROPOSE.
- A skill produced by the engine's SELF-LEARNING -> created already ON (marked `origin: javis-learned`), but it must NOT overwrite
  an existing skill and must NOT resurrect a skill the user turned off; an automatic agent -> left as a draft awaiting approval. A skill
  the user asked for directly -> created ON right away, but you must check for duplicates and make `description` state the capability clearly,
  distinguishable from other skills (a vague description makes Jarvis 007 pick the wrong skill). Do not create a skill that duplicates
  the function of an existing skill.
- User plugins (global and vault) run REAL PYTHON CODE in the server process -> create them `enabled: false`,
  `min_mode: readonly`, and TELL the user clearly: the plugin stays off until they turn it on in the app. Since 2026-10-15
  Jarvis 007 loads user plugins by default; a machine that wants to block them entirely sets the env `JAVIS_ENABLE_USER_PLUGINS=false`
  and restarts. A plugin that performs outside actions declares `min_mode: full` correctly, and the hub judges by the permission level of the caller.
- After creating, do NOT run anything with side effects on your own; let the user preview it.
