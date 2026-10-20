# Proposal: connecting 9Router to the Models page

Many customers have asked whether Jarvis 007 can use the 9Router API. This document is the digging done
before building: what 9Router actually is, where connecting it to Jarvis 007 gets stuck, and the
available paths.

## STATUS: SHELVED, NOT BUILDING (decided 2026-08-04)

The repo owner read it and decided **not to build it**, and kept the document on file. The reasoning, in their own words:

> Not a fit for now. It is not realistic and only suits people who want things cheap. Jarvis 007 is
> about to move into enterprise environments, so it has no need for mixing like this.

This reasoning **outlasts 9Router itself**, so read it carefully before reopening any proposal of the same kind:

- **The product direction is enterprise.** Enterprises buy stability and one clear line of
  accountability, not a patchwork of cheap accounts stitched together. A feature whose core
  value is "save money by mixing sources" pulls the product toward exactly the customer group
  opposite to the direction it is heading.
- **Automatic source mixing works against what enterprises need most: knowing for sure what they are running.**
  The selling point of 9Router is that it jumps to another provider when quota runs out. For an
  individual user that is convenient. For an enterprise it means "nobody knows which model
  produced the last answer, or where the data went" - an audit question that cannot be answered.
- **It requires a process running on the user's machine.** One more thing that can be switched off, and Jarvis 007
  cannot manage it.

**This does NOT mean everything in the document is useless.** Three parts can still be reused if
a different need comes up later:

- Section 2 (the wall that "localhost on a VPS is not the user's machine") applies to **every** proposal to connect
  a service running on a local machine: LiteLLM, vLLM, home-run Ollama, one-api.
- Section 3 (the risk of silently losing tool calling) applies to **every** new provider. It is a test
  that should be run before accepting any unfamiliar endpoint.
- Section 6 (the list of places to touch when adding a provider) is a map that is usable right away for the next
  provider added, whoever it is.

The rest of the document is kept exactly as it was when presented, not edited to match the conclusion.

---

## 1. What 9Router is, stated correctly

**It is NOT an online service where you buy an API key.** This is the easiest thing to misunderstand,
and misunderstanding it makes the whole plan wrong.

A comparison to make it easier to picture:

| | OpenRouter (what Jarvis 007 has) | 9Router |
|---|---|---|
| Where it runs | On their servers, on the Internet | **On the user's own machine** |
| Address | `https://openrouter.ai/api/v1`, fixed, the same for everyone | `http://localhost:20128/v1`, different for each person |
| Where the API key comes from | Sign up at openrouter.ai | Generated in the dashboard of your own 9Router |
| Who you pay | You pay OpenRouter | 9Router is **free forever**, the money goes straight to the underlying providers |
| How to install | Nothing to install | `npm install -g 9router` or run Docker |

Put another way: 9Router is **a switchboard installed at home**. The user declares in it the accounts
they already have (a Claude Code plan, a ChatGPT plan, Copilot, GLM, MiniMax, free providers such as
Kiro or OpenCode), and then 9Router receives requests and picks the cheapest route that still has
quota. When quota runs out in one place it jumps to another, so work is not cut off midway.

Two things make people like it:

- **Automatic failover when quota runs out** (they call it a "combo": a list of models in priority
  order, and when the first runs out it falls to the next).
- **Token compression (RTK)**, which they claim cuts input tokens by 20-40% by filtering out redundant
  parts of tool results before sending.

On the technical side, the part Jarvis 007 needs to know:

```
POST http://localhost:20128/v1/chat/completions
Authorization: Bearer <the user's own api key>
{"model": "cc/claude-opus-4-6", "messages": [...], "stream": true}

GET  http://localhost:20128/v1/models     → returns models + combos, OpenAI format
```

The format is **identical to OpenAI**, and model names carry a provider prefix (`cc/`, `glm/`, `kr/`...).
This is good news: Jarvis 007 already has a whole path for OpenAI-style endpoints (OpenRouter,
Groq, Gemini and Ollama all share it).

---

## 2. Where it gets stuck: exactly the wall Jarvis 007 already hit once

In version **0.16.1**, Jarvis 007 **deliberately dropped** the ability to connect a home-run Ollama, keeping only Ollama
Cloud. The reason is written straight into the code (`server/engine.py:310`, `server/config.py:61`):

> Jarvis 007 DELIBERATELY connects only the Cloud edition: the home-run edition needs its own address field, which is a single
> special case running through the whole provider layer, while most Jarvis 007 users run it on a
> VPS - where "localhost" is the container itself and not their machine.

9Router runs into **exactly those two things**:

1. **It needs an extra address field.** The eight current providers only need one API key field, and the address is a
   constant in the code. 9Router is the first where each person has a different address.
2. **`localhost` on a VPS is not the user's machine.** Your Jarvis 007 runs on a VPS. Users
   install 9Router on their personal computer. When Jarvis 007 calls `http://localhost:20128` it is calling
   the Jarvis 007 container itself, where there is nothing. This is not a bug that can be patched, it is network
   geography.

So the real question is not "how do we code it" but: **where do your users run Jarvis 007?**

| Where the user runs Jarvis 007 | Where 9Router runs | Can it connect? |
|---|---|---|
| A personal machine (Windows, `setup.bat`) | The same machine | **Yes**, `localhost:20128` means what it says |
| A VPS | Their personal machine | **No**, unless they expose 9Router to the Internet |
| A VPS | That same VPS | **Yes**, but they must install 9Router on the VPS themselves |

The address field is still needed in all three cases, because the port and host differ per person.

---

## 3. The biggest risk, and it is not where everyone thinks

The risk is not "the connection fails". A failing connection is very easy to see. The risk is **the connection
works but Jarvis 007 loses capabilities and nobody knows**.

Jarvis 007 lives on **tool calling**: reading MCP, writing vault files, handing out Kanban work, running skills. Take
tools away and Jarvis 007 is just a chat frame.

And 9Router **does not say a word about tool calling** anywhere in its public documentation
(I read the 54KB README, the setup guide page, and the home page). Not being stated does not mean
it is absent, but it does not mean it is present either.

There is a strong inference leaning toward "yes": their docs explain how to point **Claude Code**, Cursor,
Cline and Codex at 9Router. Those four tools cannot run for a second without tool calling. So it is
almost certain that 9Router forwards `tools`.

But **inference is not enough to ship**, and there is a deeper layer of risk:

> The selling point of 9Router is that it **jumps to another provider when quota runs out**. Not every
> model supports tool calling. If the jump lands on a model with no tools, Jarvis 007 will
> accept the task and then return a plain text answer - no MCP call, no file write, no error.

This is exactly the kind of failure this repo hates most and already patched once in 0.17.1: *"the engine will CONFIDENTLY accept
the task and then silently do nothing. The user sits waiting for work that never runs, and there is not
a single error line anywhere."*

So if we build it, **a detection layer is mandatory**: send a fake tool and see whether the model calls it
back; if not, tell the user plainly that the current combo cannot use tools, and do not let
them find out three days later.

---

## 4. Three paths

### Path A - A new `9router` provider, with its own address field (the recommended pick)

Add an entry to the Models page like OpenRouter, but with **two fields**: the server address and the API
key. The address is pre-filled with `http://localhost:20128/v1` so someone running on a personal machine only has to
paste the key.

- **Pros**: it is exactly what customers asked for, and it reuses almost all of the existing OpenAI-compat path.
- **Cons**: it breaks the rule "every provider needs only one key field" - this is exactly what 0.16.1 avoided.
  But this time there is a very different reason from Ollama: **customers are asking**, whereas nobody
  asked for home-run Ollama.
- **Effort**: medium. Estimate in section 6.

### Path B - Merge into one generic "OpenAI-compatible server" entry

Instead of building something specific to 9Router, build **one** provider called "OpenAI-compat server" that takes an address
+ key. It can connect 9Router, LiteLLM, home-run Ollama, vLLM, one-api, and anything that comes later.

- **Pros**: a single special case, usable for a whole family of products and not just one
  name. If 9Router goes out of fashion tomorrow the effort is not lost.
- **Cons**: users must know for themselves what they are connecting; there is no dedicated 9Router guide,
  so newcomers will be more confused. It does not "answer the customer's question" the way path A does.
- **Compromise**: do path B at the data layer, but have the connector store carry a ready-made **9Router
  template** with the address and guide pre-filled. Users still see the word "9Router", while the code
  has no special case.

### Path C - Do not connect, guide users to go through Claude Code

9Router already supports pointing Claude Code at it. In theory the user can configure Claude Code
to point at 9Router and then Jarvis 007 uses Claude Code as usual.

- **Pros**: not a single line of code.
- **Cons**: very fragile. Jarvis 007 manages the Claude Code lifecycle quite deeply (login, model, MCP,
  sessions), so wedging a proxy in the middle breaks easily in hard-to-trace places. And it does not answer the
  customer's question: they want to see 9Router **on the Models page**.

**My recommendation: path B with a pre-filled 9Router template.** The same effort but it opens a whole family, and
it leaves no special case named after a third-party product in the provider layer.

---

## 5. What must be verified BEFORE writing code

These four questions have no confident answer yet, and all four change the design if answered differently.
Check by installing 9Router on a machine and running a few commands, about 30 minutes.

1. **Does it forward `tools`?** Send a request with `tools` and see whether `tool_calls` appears in the
   response. If NOT, stop the whole proposal, because Jarvis 007 cannot use it.
2. **Does it stream together with tools?** Jarvis 007 streams text word by word. If `stream: true` is on and tools
   break, we must fall back to non-stream mode, and the user must be told up front.
3. **What shape does `GET /v1/models` return?** The Jarvis 007 Models page lists models dynamically. We need to
   know how combos show up so they can be told apart from regular models.
4. **What happens when a combo jumps to a model with no tools?** This is the risk in section 3. How to check: build a
   combo with a non-tool model in second position, force the first one out of quota, and see what happens.

A quick command to check questions 1 and 3, run on a machine with 9Router installed:

```bash
KEY=<key from the 9router dashboard>
BASE=http://localhost:20128/v1

curl -s $BASE/models -H "Authorization: Bearer $KEY" | head -40

curl -s $BASE/chat/completions -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" -d '{
  "model": "<fill in the model or combo name>",
  "messages": [{"role":"user","content":"What time is it? Use the tool."}],
  "tools": [{"type":"function","function":{"name":"gio_hien_tai",
    "description":"Returns the current time","parameters":{"type":"object","properties":{}}}}]
}' | python -m json.tool
```

Seeing `tool_calls` in the result means it passes. If not, stop.

---

## 6. If we build it, what gets touched

Listed here so you can see the real size, not to start right away.

**Provider layer (the main part)**

- `server/config.py` - add the key field + address field to the config, add them to the secret-masking list
  (line 374), add model seeding.
- `server/engine.py` - build the address from config instead of a constant; add it to the `endpoints` table
  (line 613); the stream function; the tool loop function (`*_chat_with_mcp`).
- `server/aux_engine.py` - add to `API_PROVIDERS` and `_KEY_FIELD` so background jobs can route.
- `server/main.py` - `/provider/models` queries the user's `GET /v1/models`;
  `_WORKFLOW_ROUTABLE_PROVIDERS`; `_TG_PROVIDERS` (the model picker buttons on Telegram).
- `server/usage_index.py` - add to `_API_PROVIDERS` to count tokens.
- `server/connect_health.py` - health probing; **add a dedicated branch for the "cannot reach the address" error**,
  because this is the first provider where a network error is an everyday occurrence (machine off, port changed,
  VPS cannot see the home machine).

**UI**

- `dashboard/console.js` - `KEYFIELD` (line 3066), `MCP_PROVIDERS` (4060), `_UZ_PROV` (372),
  the engine label table (4438). Plus an **address field**, which no provider has yet, so the Models
  page form has to be extended and not just given one more row.
- `dashboard/usage.js`, `dashboard/app.js` - labels.

**New safety layer (not existing, must be written)**

- A tool-calling check when Connect is clicked: send a fake tool, and if it is not called back, warn right on the
  connection screen instead of letting it be discovered late.
- An address guard: allow `http://` only when pointing at a local machine; pointing out to the Internet must be `https://`,
  otherwise the API key travels over the network in the clear.

**Docs**

- `docs/10-models-va-engine.md` - a new section, including a plain statement that a VPS cannot see the home machine.
- `CLAUDE.md` - the sentence "**Eight** brains are currently usable..." must be fixed. That sentence appears in the system
  prompt on every chat turn, so if it is wrong Jarvis 007 says the wrong thing to every user.

**Estimate**: about one small release (like 0.19.0), with most of the effort in the safety layer and in the UI
with the address field, not in calling the API.

---

## 7. What I do NOT recommend

- **Do not pin `localhost:20128` as the default and call it done.** It is right for a personal machine and wrong for
  every VPS deployment. There must be a real address field, with an explanation right next to it.
- **Do not promise "automatically saves 20-40% tokens".** The RTK figure is published by 9Router; Jarvis 007 cannot
  measure it and cannot control it. Repeating someone else's number as if it were ours is the cheapest way
  to lose credibility.
- **Do not make 9Router the default provider.** It depends on a process running on the user's
  machine; when that process is off, Jarvis 007 dies and the user does not understand why.

---

## 8. Three things you need to decide

1. **Path A or path B?** (I lean toward B: one "OpenAI-compat server" entry with a pre-filled 9Router
   template, opening a whole family instead of one name.)
2. **Where do your customers run Jarvis 007?** If most run on a VPS, the real value of this
   feature is much lower than it looks, and we should tell them up front instead of finding out after building.
3. **Who can run the verification step in section 5?** It needs a machine with 9Router installed. My build machine
   cannot install it (there are no provider accounts to declare in 9Router).

Once those three questions are answered we can start right away.

> **The three questions above are no longer valid.** The proposal was shelved at a higher level: it is not that the wrong path
> was chosen but that we are not going in this direction. See the Status section at the top of the document.
