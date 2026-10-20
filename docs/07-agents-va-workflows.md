# Agents & Workflows

***Tiếng Việt** · [English](en/07-agents-and-workflows.md)*

This is where you create specialised AI assistants (Agents) and chain them into automated pipelines (Workflows). For example: a research agent, a writing agent and a reviewing agent, chained into "research > write > verify" that produces a result in one run.

## What this feature is

- **An Agent** is an "AI employee" with a fixed role. Each agent has: a name, a role description, a detailed working instruction (system prompt), a list of skills it may use, a **model to run on**, and its **own memory** that accumulates over time. The model can come from **any provider you connected** on the Models page: Claude (Claude Code), ChatGPT (Codex), Grok Build CLI, Antigravity CLI, OpenRouter, Anthropic API, OpenAI, Google Gemini, Groq. The picker reads straight from your connected providers, so connecting more adds more choices. Every provider can read and write vault files and use MCP; Claude Code and Codex additionally have shell commands and can browse the web. If the chosen provider fails at runtime, Jarvis 007 falls back to another brain rather than leaving the agent silent. (Ollama cannot run agents yet, so it does not appear here.) An agent's model is REALLY applied when the workflow runs.
  - Safety note: when a workflow runs **automatically in the background** (the Kanban dispatcher, restricted file-tool mode), the agent always uses Claude Code to keep the safe tool restrictions, even if you picked another provider. Your chosen model applies when you send a message on the **Partners** page.
- **A Workflow** is a chain of steps, each handing one task to one agent. The result of a step can flow into the next. You can attach a **verification step**: another agent playing the reviewer, which by default assumes the result is wrong and must be proven otherwise; if it fails, the workflow retries a few times.
- Every agent and workflow is stored as an **.md file in the vault** (the selected brain), so you can read them, edit them by hand, and Jarvis 007 can create them from chat.

Related: choosing an agent model in [Models & engines](10-models-va-engine.md); creating and enabling skills to assign in [Skills](06-skills.md).

## Where to find it in Jarvis 007

Open **Capabilities > Partners** in the dashboard sidebar (port 7777 by default). The page has **Agents | Workflows** tabs. Skills and Plugins remain in Capabilities.

- Left: choose a tab, search or filter by tag (workflows: by group), then select a partner. Recently used agents and workflows appear first.
- Centre: chat with the selected partner.
- Right: agent settings and conversations, or workflow progress and run history.

On narrow screens, use the list and details buttons to open the side drawers. Switching brains switches the lists and conversations.

## Chatting with an agent

1. Choose **Agents**, then select an agent in the left column.
2. Send a message in the centre. Replies use the agent's configured role, instructions and private memory.
3. Edit its name, role, instructions, skills or model on the right and click **Save**.
4. Use the new conversation button to start a separate chat with the same agent. Each agent can have several conversations; reopen recent conversations on the right to continue.

Partner conversations are separate from Jarvis 007's main chat history. Returning to a partner resumes its most recent conversation.

### Unread messages and muting

From 0.205.0 the partner list works like a message list:

- A partner with a new message (you wrote, the partner replied, or a background job reported into its chat) **moves to the top**. Jarvis 007 Core and the **Pinned** ones still come first.
- A partner card shows its **unread count** in the bottom corner, next to the time. Opening that partner's chat clears it, in every open tab.
- Each card's **⋮** button has **Mute notifications**, with **For 1 hour**, **For 4 hours**, **Until 8:00 AM** or **Until turned back on**. A muted card shows a crossed-out bell and a grey unread count. Messages still reach the chat and the bell, just without a sound or a push notification. Press **Unmute notifications** to turn them back on.

## Creating, searching and Jarvis 007 Store

Choose the tab you need, then click the button to create an agent or workflow at the bottom of the left column. **Jarvis 007 Store** opens the matching package catalogue so you can add ready-made partners. Agents are sorted by **tags**, workflows by **group** (see below).

Search matches names, slugs, roles, descriptions and tag names, and supports typing without accents. The tag filter (the group filter on the Workflows tab) works together with search. Unused items follow the items you have used, ordered by name.

## Creating an Agent (step by step, through the form)

1. Open **Partners > Agents**.
2. Click the create agent button at the bottom of the left column. An editor opens on the right of the screen.
3. Fill in the following fields:

| Field | Meaning | Suggestion |
|---|---|---|
| **Name** | The agent name, shown on the card. Required. | e.g. "Email specialist" |
| **Role (short description)** | One sentence describing what the agent does. | e.g. "Writes sales emails in a friendly voice" |
| **Documents & links** | A button that opens a pane for attaching brain files and links to this agent alone. See the section right below. | A price list, a brand brief, product document links |
| **System prompt (detailed working instructions)** | A long, detailed instruction: how the agent works, its principles, the output you expect. | e.g. writing rules, banned words, output format |
| **Skills** | The skills available in the vault; tick the ones the agent may use. | Pick skills matching the role |
| **Model** | A picker with 8 options, see the table right below. | Sonnet for balance, Opus for deep reasoning, Haiku for fast and cheap |

4. Click **Save**. If you forget the Name, Jarvis 007 says "Enter a name".
5. The new agent card appears in the list with a 🤖 icon, the model name and the assigned skill labels. With no skills assigned, the card reads "no skills assigned".

A note on the Skills field: the list comes from the vault's skill folder. If the vault has no skills, the panel says "The vault has no skills in skills/ - you can still create the agent and assign skills later." You create the agent as usual and come back to assign skills later. Creating skills is covered on the [Skills](06-skills.md) page.

### What the Model picker offers

| Option | Group | Runs on |
|---|---|---|
| **Default (per CLI)** | (no group) | See the explanation under the table |
| **Sonnet** | Claude (Claude Code) | Claude Code |
| **Opus** | Claude (Claude Code) | Claude Code |
| **Haiku** | Claude (Claude Code) | Claude Code |
| **Fable** | Claude (Claude Code) | Claude Code |
| **GPT-5.5** | ChatGPT (Codex - requires a ChatGPT login) | Codex CLI |
| **GPT-5.4** | ChatGPT (Codex - requires a ChatGPT login) | Codex CLI |
| **GPT-5.3 Codex** | ChatGPT (Codex - requires a ChatGPT login) | Codex CLI |

Under the Model field there is a note: "The agent runs through the provider's CLI: choose Claude and it runs on Claude Code; choose ChatGPT and it runs on Codex (you must already be signed in to ChatGPT on the machine/VPS). Both read/write vault files and use MCP."

**What "Default (per CLI)" really does:** left empty, Jarvis 007 takes the **auxiliary model** you set on the **Models** page first (only when that auxiliary model is a Claude model); with no Claude auxiliary model it falls back to the CLI's default model. If you want an agent to always run on one specific model regardless of the global configuration, pick that model explicitly instead of leaving it empty.

### An agent's documents and links

Every agent has its own document cabinet: open **Assistant settings** in the right column and click **Open the documents & links pane**. The pane is the same one you already use for a project and for a single conversation, only the scope differs.

- **File tab**: find an existing file in the brain to attach, or upload a file from your computer (uploaded files go into the brain's `sources` folder). You can also drag and drop files onto the pane.
- **Link tab**: paste an `http://` or `https://` address together with a memorable name.
- **Pin button** on each file: pinning makes Jarvis 007 **preload the file's content** at the start of every turn the agent works (at most 2000 characters per file and 6000 in total), instead of only telling it the file name and letting it open the file when needed. Pin a price list and the agent can answer straight away without going to read it.
- **X button** detaches it from the agent but does **not** delete the file in the brain. To delete it for good, use the trash button next to it.

Scope: this list belongs to the **agent**, so every conversation with it and every workflow step that calls it sees the list. To attach documents to a single conversation only, use the **Files & links** button in the bar above the chat. It is stored in the agent's own `.md` file (the `assets` key in the frontmatter), so exporting the agent or copying the brain to another machine carries the list along.

A new agent that has never been saved has this button dimmed: the agent must exist before you can attach documents to it.

### Agent tags

Since version 0.100.0 each agent can carry **several tags** (for example Marketing, Content writing, Engineering); an agent's old group automatically became one tag. Tags are only for sorting and finding agents:

- **Add or remove a tag:** the **...** button on each agent, item **Tags**. Click a tag to add or remove just that tag; the **New tag** box creates and adds a new one. Other tags stay as they are.
- **Filter:** the bar above the list lets you choose **All agents**, **Untagged** or one tag. An agent with several tags shows under each of its tags but only once in the list.
- **Rename or delete a tag:** the **...** button next to the tag name in the filter bar. Renaming applies to every agent carrying that tag; renaming to a name that already exists merges the two tags into one. Deleting a tag only removes the label, never the agent, its conversations or its goals.
- Tags are not in the settings form: clicking Save in the form never changes tags.

A tag is **not** a chat group: tagging does not add the agent to any group conversation. A tag also does not pick a reviewer, grant permissions or turn on Resonance. Workflows are still sorted by **group** as before.

### An agent's own memory and run log

Besides the `.md` file, each agent has two more things inside the brain's `memory/agents/<slug>/` folder:

- **`MEMORY.md`, its own memory.** Every time the agent runs, Jarvis 007 reads this file and injects it straight into the agent's system prompt under the heading `# Bộ nhớ của bạn` (Vietnamese for "Your memory"; the code matches this exact heading, so it stays in Vietnamese). This is where long-term knowledge accumulates: house conventions, a client list, mistakes it was corrected on. The file has **two writers**: you by hand, and the agent itself, which **builds it up as it runs**. At the end of a task, if it learned something reusable, the agent proposes it and Jarvis 007 writes it into the file's `## Bài học (tự học)` section (that heading means "Lessons (self-learned)" and is matched by code, so it stays as is). Jarvis 007 holds the pen, not the model, so there are hard rails: duplicate lessons are dropped, only the 15 newest lines are kept so the memory gets denser rather than longer, and the part you wrote by hand outside that section is never touched. That means the agent gets smarter with each use, with no background job scanning in bulk. Since 0.105.0, rules you **tell the agent directly** in chat (for example "no markdown when messaging on Zalo") go into a separate `## Luật chủ dặn` section ("Rules from the owner", also matched by code): no ceiling, and they are never pushed out like lessons. Self-learning also no longer rewrites the whole agent body: it may only add rules to the `## Bổ sung (tự học)` section ("Additions (self-learned)") at the end of the body, and every write must keep every line you wrote intact, or Jarvis 007 does not write.
- **`runs/`, the run log.** Each time a workflow step finishes (verification steps included), Jarvis 007 appends an entry to `runs/<YYYY-MM-DD>.md` with the run time, the task given and the result (trimmed). This is where you look back at "what did this agent do yesterday" without reopening the tracking panel. This raw log does not go into the brain's git.

Both are ordinary text files: open, read and edit them by hand through the [File manager](05-quan-ly-tep-tin.md). To teach an agent something, write it straight into `memory/agents/<slug>/MEMORY.md` and it knows on the next run.

To be clear: this memory belongs to **one agent**; Jarvis 007's shared memory about you and the business lives in `memory/MEMORY.md` and `memory/facts/`, see [Second Brain: memory, Wiki, INGEST](13-second-brain-bo-nho-wiki.md).

### Editing or deleting an agent

- **Edit**: select the agent, change it in the right column and click **Save**.
- **⤓ Export**: package the agent (with its skills) into a `.zip` to share, see "Sharing" at the end of this page.
- **Delete**: click **Delete** and confirm in the "Delete agent ...?" dialog. Note: if a workflow uses this agent, that step will point to an agent that no longer exists, so after deleting, check the related workflows. Deleting an agent does **not** delete its `memory/agents/<slug>/` folder, so the old memory and log stay on disk.

## Creating a Workflow (step by step, through the form)

Create at least one agent on the **Agents** tab before creating a workflow.

1. Open **Partners > Workflows**.
2. Click **New workflow** at the bottom of the left column.
3. Fill in:
   - **Name**: the workflow name. Required.
   - **Description**: one line saying what this workflow does (optional but worth having; this line shows on the workflow card).
   - **Group**: the group name that files the workflow into the group column on the left. Type a new name or pick an existing group. Left empty, it goes into the "General" group.
4. In **Steps (each step = 1 agent · use {{input}} and {{prev}})**, every step is a block with:
   - A **Task** field: describe what this step must do. In the task you can use two special variables:
     - `{{input}}` = the content of the message you send to run the workflow.
     - `{{prev}}` = the result of the step immediately before.
   - A **Verification** section (optional): pick an agent to play the reviewer for this step, and how many retries are allowed. Leave it at "- no verification -" if not needed. The retry count defaults to 1 and ranges from 0 to 5.
5. Click **+ Step** to add a new step.
6. Click **Save**. If you forget the Name, Jarvis 007 says "Enter a name". A newly saved workflow is in the ready (active) state.

### The header row of a step

Each step has a header row, read left to right:

| Element | Meaning |
|---|---|
| Step number | 1, 2, 3... in the exact run order |
| Summary line | "agent name · task" condensed to one line |
| Agent picker | Change the agent in charge of this step |
| **↑** | Move the step up one place (dimmed on the first step) |
| **↓** | Move the step down one place (dimmed on the last step) |
| **✕** | Delete this step (at the END of the header row) |

**Collapsing and expanding steps:** click the header row (on an empty spot, not a button or the picker) to collapse or expand that step's body. When you open an existing workflow to **edit** it, all steps start collapsed so you see the whole chain first; click a step to open it for editing. A **newly created** workflow has just one step, so it starts open.

Text you are half way through typing is not lost when you collapse or expand, reorder or delete another step: Jarvis 007 keeps every step's content aside before each redraw.

### Example: a 2-step workflow

- Step 1: agent **Researcher**, task: `Research this topic thoroughly: {{input}}. Find sources, summarise the key insights.`
- Step 2: agent **Writer**, task: `Write a complete article about '{{input}}' based on this research:` then a line break and `{{prev}}`. In Verification, pick the **Verifier** agent with 2 retries.


### Editing, exporting or deleting a workflow

Select the workflow in the left column. The right column has **Edit**, **Export** and **Delete** buttons, plus the list of steps. Edit opens the workflow editor; after saving, the list and details update.

## Running a workflow

1. Open **Partners > Workflows** and select a workflow in the left column.
2. Send your request in the chat. Each message starts one run; the message text is the `{{input}}` input.
3. Follow each step's progress in the right column. If the workflow has verification, that step may run again based on the verifier's feedback and the configured number of attempts.
4. If approval is needed, read the request and use the approval button in the right column to continue. Errors and waiting states are also reported in the chat.
5. When it finishes, the result comes back to the chat. The next message in the same conversation remembers the previous result, so you can give feedback and run again, for example: "Keep the main idea, make it shorter".

The **run history** in the right column lists the most recent runs. Click a run to see the details and reopen its conversation if the run had a chat session. A workflow that just ran moves to the top of the list. You can also ask Jarvis 007 in the main chat: "How did the latest workflow run go?" to look up the saved history, including runs from Partners and from Kanban.

Each step still writes the agent's log under `memory/agents/<slug>/runs/`. If the connection drops, check the run history before sending again, to avoid running twice.

## Creating agents and workflows in words (through chat)

You do not have to use the form. In the chat with Jarvis 007 (see [Chat & voice](02-tro-chuyen-va-giong-noi.md)) you can ask in words, for example:

- "Create an agent that writes sales emails."
- "Create a workflow that researches then writes an article."
- "Add an editing step to workflow X."

Jarvis 007 then writes the matching .md file into the vault, sets an accent-free slug, tags the agent or files the workflow into a group on its own (it reads the tags and groups already used in the brain and takes the closest), assigns sensible skills from the available ones, and if the workflow mentions an agent that does not exist yet, creates that agent first. When done, Jarvis 007 reports briefly which files it created or edited. Go back to the Partners page and you see it at once, with nothing more to do.

This is handy when you can describe the intent in words but would rather not fill in a form, or want to change several steps at once.

## Where agents and workflows are stored

In a brain with the new layout, each agent is a file at `agents/<slug>.md` and each workflow at `workflows/<slug>.md`. The `slug` is lowercase, hyphenated and accent-free (for example "viết email" becomes `viet-email`).

**An old brain that has not been migrated** keeps those two folders at `Javis/agents/` and `Javis/workflows/`. Jarvis 007 detects this itself: if the new folder exists it uses it, otherwise it uses the old path. So if you open the Files page and do not see `agents/` at the brain root, look inside `Javis/`.

Because they are text files, you can open them through the [File manager](05-quan-ly-tep-tin.md) to read or edit by hand. The file structure:

- Agent: the frontmatter holds the name, role, tags (`tags`, a list), skill list, model, and the attached documents (`assets`, with `files` and `links`); the body is the detailed system prompt. Its own memory and run log live outside this file, in `memory/agents/<slug>/`.
- Workflow: the frontmatter holds the name, status (active or off), group (`group`), description and the list of steps (each step has an agent, a task, and optionally a verification agent with a retry count).
  - When writing it by hand, write `status: 'off'` WITH quotes: a bare `off` is read by YAML as a true/false value. Since 0.107.0 Jarvis 007 understands both spellings, but keep the quotes to be safe. A workflow that is off does not run in the background from Kanban or reminders; clicking Run in Partners still runs it so you can try it before turning it on.
  - A step may declare `tools: [javis_generate_image, javis_describe_image]` to get exactly those tools when the workflow runs in the background under Full access (normally the agent has only file tools then). It accepts plugin tool names plus `WebFetch` and `WebSearch`; Bash is never granted this way. The tool's own permission level is still checked at call time, so a step cannot raise its own level.

Editing the file by hand works too. Agent: write `tags: [Marketing, Content writing]`; once a `tags` field is present (even `tags: []`) Jarvis 007 reads only it. An old agent file that has just `group: Marketing` still reads as a single Marketing tag; on the first save Jarvis 007 adds `tags` and keeps `group` set to the first tag so older builds can still read it. Workflows and skills use `group`; without this field they go into the "General" group.

After you edit and save a file, the Partners page picks up the new content on the next reload.

## Tips

- **Always add a separate verification step for important work.** Make the verifier a different agent from the doer, because it is forced into the "assume the result is wrong" role. That is how you reduce sloppy or invented output.
- **The verification agent must return JSON** `{"pass": true|false, "reason": "...", "fixes": "..."}`. Since 0.107.0 verification fails closed: a verifier that errors, an unreadable answer, or running out of retries while still failing all count as NOT PASSED, and the workflow stops at that step instead of carrying on as it used to.
- **Each step does exactly one thing.** Do not cram "research and write and publish" into one step. Split it so each stage is easy to control and fix.
- **Use `{{prev}}` to link steps.** If a later step wants the previous step's result, it must mention `{{prev}}` in its task, otherwise the agent will not see the previous output.
- **Reorder with ↑/↓ instead of deleting and redoing.** A wrong order only needs a nudge up or down; the content moves intact.
- **Set a moderate retry count.** 1 to 2 is usually enough. Setting it too high makes the workflow slow and costly when the result is hard to reach.
- **Match the model to the job.** Reasoning-heavy steps (analysis, verification) suit Opus; simple, high-volume steps suit Haiku for speed and cost. Details in [Models & engines](10-models-va-engine.md).
- **Assign skills where they belong.** An agent is only strong with the right skills. For example, a sales page agent should carry the sales page skill. Skill management is in [Skills](06-skills.md).
- **Use the agent's own memory for things that repeat.** If the same instruction has to be repeated on every run, write it straight into `memory/agents/<slug>/MEMORY.md` rather than cramming it all into the system prompt.

## Sharing: Export / Import (agent, skill, workflow)

You can package an agent, skill or workflow into **one `.zip` file** to send to someone else, and bring someone else's file into your own brain.

- **Export:** each agent / skill / workflow card has a **⤓ Export** button. Click it to download a `.zip` package. The package **includes dependencies** so the recipient can run it immediately: exporting a workflow also includes the agents that workflow uses and those agents' skills; exporting an agent also includes the agent's skills. **System** skills are not packaged because every brain already has them.
- **Safety:** on import, Jarvis 007 blocks unusual paths inside the package (it will not write outside the agent/skill/workflow folders) and caps the size to avoid malicious files. Even so, only import packages from sources you trust, because skill content is instructions for the AI to follow.

Note: an exported package holds only the definition files. **An agent's own memory and run log do not travel with the package**: the recipient gets the role and the skills, but not the memories.

## Sharing a whole Team

On the Team page, a team's **⋯** menu has **Share team**: it downloads one `.team.javis.zip` file containing the team's partners, their skills, the leader and the pinned messages (as shared instructions). The file has **no** chat history, keys, passwords, models or Auto switch; text that looks like an API key, a bot token or a `password: ...` line is replaced with `[REDACTED]` before writing.

The recipient clicks **Import team** at the top of the team list, picks the file, previews which partners and how many skills it holds, then confirms. A partner with the same name that already exists in the brain keeps the recipient's own version; the recipient picks models and Auto later. This file can also be opened with the Import button on the Partners page of an older Jarvis 007 build (which then imports only the partners, without building the team).

Each chat turn that creates, edits or removes a schedule, recurring job, partner, workflow or skill also leaves a small line under the answer ("Schedule created: ..."). Something newly created has an **Undo** button: it cancels the schedule, or deletes the recurring job, partner, workflow or skill that was just created.

## Team waiting for your approval (since 0.207.0)

In a job given to a Team, when a partner needs a decision from you (choosing an option, spending money, sending a message or posting something outside), that step **really stops**: the job moves to **Waiting for your review**, frees its slot for the team's other jobs, and an **Approval request** card appears in the chat stating what will be done, the scope, the impact, the evidence and exactly the calls that will run. Previously a line like "@Lead, do you approve?" was treated as a result and the job closed itself.

- **Approve**: the partner continues in a new step, and only exactly the approved calls run, each call once. A restart or re-running the step does not redo an action that already ran.
- **Ask for changes**: write what you want changed, and the partner offers a new option (as a new card).
- **Reject**: write the reason, and the job stops there; you edit the request to send it in another direction, or cancel the job.
- **Revoke approval**: take back an approval that has not been used yet.

Editing the job's request or cancelling the job voids the old card. Text in the chat (yours or a partner's) never substitutes for the Approve button. Each click carries its own code, so clicking again on a flaky network does not act twice, and with two tabs open the later tab is told it was already decided.

**Team permissions** (Team tab, **The team's outside actions** section):
- **Needs your approval** (the default, including existing teams): partners read, search and write files in the brain and the team's folder on their own, and run read-only commands. Sending, posting, paying, ordering, deleting data or any other shell command is blocked BEFORE it runs and becomes an approval card.
- **The team acts without asking**: the same rights as when you chat privately with each partner (how Teams ran from 0.194.0 to 0.206.0).

In Needs your approval mode, Claude Code, Codex (with its own sandbox) and the brains that use an API key can block the action before it runs. Grok Build only does the part within scope (an approved action cannot run on Grok). Antigravity cannot block its own tools, so that step is refused with an explanation: switch the assistant to another brain or turn on "The team acts without asking".

## A Team's department mandate (since 0.208.0)

The Team tab has a **Department mandate** section. Existing teams have no mandate, so nothing runs by itself until you set one and click **Turn on**.

- **Outcome**: what this team is for. **How it is measured**: one criterion per line.
- **Granted sources**, one per line: `folder:bao-cao` (a folder in the brain), `kanban` (the brain's failed Kanban jobs), `mcp:<connection id>` (whether a connection is down), `test:<check command>` (a command that runs at the Coding page's draft-writing level, so it can run code such as `pytest` or `npm test`; only you can set it; a non-zero exit code or running over 2 minutes counts as a failure).
- **Scope it may work in**, **observation cadence**, **observations per day**, **jobs it may open per day**, and **stop opening jobs when N are open**.
- For each kind of opportunity (documents changed, Kanban job failed, check command failing, connection down) choose: **Only record it**, **Propose it to me**, **Open a job, wait for my approval** or **Open the job itself**.

Jarvis 007 reads the sources with code, without calling a model. A source that cannot be read shows **missing** with the reason, and no problem is invented. A change becomes an **opportunity** carrying its source, data version, and the reason tying it to the mandate and the benefit. The same data is not opened twice; an opportunity you **Skip** comes back only when the data changes; each source has a cooldown; and a proposal left over 48 hours expires. Once the day's job quota is used up or the open-job limit is hit, it only proposes.

A job opened by a mandate records the mandate, version, observation and opportunity right in its request, and every outside action it takes still goes through the approval gate. **Pause** stops observing; **Revoke** cancels mandate jobs that were opened but have not started and closes open proposals. Every edit is a new version, with history.

## Product acceptance for a Team (since 0.209.0)

On the Tasks tab, a job that is waiting or running has an **Acceptance** button to set criteria, one per line:

- `file: bao-cao/tuan.md`: the file must exist.
- `contains: bai-viet/a.md | 300 | giá, liên hệ`: at least 300 characters and every one of the phrases (the Vietnamese phrases "giá, liên hệ" mean "price, contact").
- `json: data.json | doanh_thu, don`: valid JSON with all of the keys (`doanh_thu` = revenue, `don` = orders).
- `cmd: pytest -q`: the check command must return code 0 (runs at the Coding page's draft-writing level).
- `confirm: bao-cao/tuan.md`: you confirm it yourself.

When a partner hands in its result, Jarvis 007 checks the product itself (the files) against each criterion: **pass**, **fail** or **unclear**, with evidence (path, sha256 hash, size, modified time). A model's opinion is never the verdict.

- All pass: only then is the job closed as **done**.
- Some criterion fails: that partner gets a fix step stating what failed. Past the fix-round limit (default 2) the job stops at **Not up to the criteria**; you edit the request to try again.
- Some criterion unclear or needing your confirmation: the chat shows a **Product acceptance** card with **Passes, close the job** or **Not yet, send back** (with a note). A file that changed after the check cannot be closed; it must be checked again.

Editing the job's request voids the old evidence. After acceptance, editing the product file makes the card read "The product changed after the check". A partner's learning score is only added when acceptance passes or you confirm, once per job.

## Quick actions and troubleshooting

- **Create new:** choose the tab and click the create button at the bottom of the left column; or open **Jarvis 007 Store**.
- **New conversation:** starts a separate session with the selected partner.
- **Edit / Export / Delete:** in the partner's right column.
- **Empty list:** check the selected brain, the search box and the tag (or group) filter, then create a partner if there is none.
- **Settings or history not visible:** open the details column with the button at the top of the chat, especially on narrow screens.
- **Agent missing in a workflow:** create that agent first, then edit the step to pick the right agent.
- **Connection lost or run error:** read the message in the chat and the run history before sending the request again.
- **Page stuck loading:** check the server on port 7777 and see [Troubleshooting & FAQ](17-khac-phuc-su-co.md).

## Related

- [Skills](06-skills.md) - creating, enabling and assigning skills to agents.
- [Plugins](20-plugins.md) - an item in the Capabilities group, for tools that run real code.
- [Models & engines](10-models-va-engine.md) - picking the main model, the auxiliary model and the providers.
- [Work / Kanban](21-viec-kanban.md) - where workflows run automatically in the background per task.
- [Second Brain: memory, Wiki, INGEST](13-second-brain-bo-nho-wiki.md) - telling an agent's private memory apart from Jarvis 007's shared memory.
- [File manager](05-quan-ly-tep-tin.md) - opening and hand-editing agent, workflow and memory files.
