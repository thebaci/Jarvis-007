# Calling Jarvis 007: ChatGPT Live

October 1, 2026. The project owner approved the design in a session on the same day. This is the
ONLY design document for voice: the older voice specs (Voice V1, V2, headset-again, adaptive pacing,
focus, the 09/24 audit) have had their still-valid parts merged into Appendix A and were then deleted.
Code points back to this document.

**Status: done**, all three steps of section 6: ChatGPT Live in 0.65.17, the calling experience in
0.65.18, the tidier settings page in 0.65.19. One cleanup is still pending: removing the disabled
adaptive-pacing code entirely (Appendix A8).

## 1. Goal and decisions already settled

The user wants to talk to Jarvis 007 like a phone call: listen and speak at the same time, interrupt
whenever they like, get a near-instant reply, and configure as little as possible.

| Decision | Settled |
|---|---|
| Pressing the mic button | **Phone call**: one press opens the call, another press (or Esc) hangs up |
| Screen during a call | **A thin call bar above the chat frame**, both sides' words become ordinary chat bubbles |
| Who answers | **Split the work**: small talk goes to the conversational model that replies instantly; anything needing data, MCP, files, memory or opening a page goes to the Jarvis 007 brain the user chose |
| Main path | **ChatGPT Live** (Codex realtime, no API key needed) |
| Long silence | After 30 seconds of silence, **drop the listening connection**; the first real sentence reconnects it, no need to say a name (0.65.22); the call bar stays |
| Space key | **Removed** as a push-to-talk shortcut. Only the mic button remains, Esc hangs up |
| Default voice | **juniper** |
| Name shown | Only **ChatGPT Live** (labels, notices, CHANGELOG). The term "full duplex" is not used anywhere the user reads |
| Settings | The main page keeps 3 things; the machine infers everything else (section 5) |
| Claude ears | Not built: Claude models do not accept audio, and Claude Code's voice needs a claude.ai token that Jarvis 007 does not read |

## 2. Measurements used as evidence

**Listening to Vietnamese mixed with English** (`tools/stt_bench`, 20 commands, Edge TTS synthetic voice):

| Way of listening | Wrong words | Correct terms | Fully correct commands | Time |
|---|---|---|---|---|
| Raw Chrome Web Speech | 41% | 11/42 | 4/20 | instant |
| Chrome, then a model fixes the text | 23% | 28/42 | 11/20 | one extra model turn |
| Groq Whisper via /stt (0.65.15) | 14% | 33/42 | 13/20 | 0.9 seconds |
| ChatGPT realtime | 13% | 33/42 | 12/20 | text arrives 0.46 seconds after speech ends |
| Gemini listening to a file via agy | 5% | 39/42 | 17/20 | 7 to 17 seconds, rejected |

The `safe_transcript_rewrite` guard blocks 9 of 13 correct rewrites, and in one case Chrome lost
information outright, so fixing the text after listening is not the main path.

**ChatGPT Live trial** (Codex 0.153.4 and 0.159.3, 10/01, synthetic-voice script):
- Natural Vietnamese, correct forms of address ("Dạ, em vẫn ổn anh ơi, cảm ơn anh", meaning "Yes, I'm still fine, thank you" in a polite younger-to-older register).
- Jarvis 007's first sound comes out **0.44 to 0.85 seconds** after the user finishes speaking (about 2 seconds for the first turn).
- Handoff arrives up to **0.5 seconds** after the question; the result comes back through `appendSpeech`, and the model reads it out almost verbatim.
- Interrupting while Jarvis 007 is telling a story: Jarvis 007 stops and answers "Dạ vâng, em dừng đây ạ" (roughly "Yes, I'll stop here").
- A 15-minute session did not drop. Isolated bugs: the first sentence after 3 minutes of silence was split in two ("Doanh" / "là bao nhiêu em", meaning "Revenue" / "is how much") and the text arrived about 29 seconds late. Dropping the connection after 30 seconds of silence and merging short requests (section 3.2) handle this.

## 3. Architecture

### 3.1 Choosing the call path

The key `voice.call_engine` = `auto` (default) | `chatgpt` | `api` | `basic`. `auto` picks in this order:

1. **chatgpt**: ChatGPT is connected (Models page) and Codex can run realtime (probed once, then remembered).
2. **api**: Live through an existing API key (`voice.live_provider` gemini | openai | gpt-live), when a key exists.
3. **basic**: the Basic fallback path for every machine and every brain (section 3.6).

If a path is chosen by hand but cannot run, it falls to the next path and the "Using" line states the
reason, the same as `voice_ear.select_ear`.

### 3.2 The `codex-plan` provider (server)

A new class in `server/voice_live.py`, with the same `LiveProvider` interface, needing NO key
(`make_provider` gets a keyless branch).

**Process.** One long-lived `codex -c features.realtime_conversation=true app-server` for the whole
server (the flag is required by Codex before 0.159 and harmless from 0.159; Docker pins 0.153.4). The
binary is found with `claude_cli.find_codex_cli()`. The JSON-RPC pattern follows
`codex_models.list_models` (`initialize` with `capabilities.experimentalApi = true`, rejecting every
permission approval request the server sends back). Every call, and every reconnect after a
silence drop, opens a NEW thread: reusing a thread for a second `realtime/start` breaks ICE.

**Thread.** `thread/start {ephemeral: true, cwd: <empty temp folder>, sandbox: "read-only",
approvalPolicy: "never", developerInstructions: "Reply only: [FINAL]"}`.

**Realtime session.** `thread/realtime/start`:
- `version: "v3"`, `outputModality: "audio"`, `transport: {type: "webrtc", sdp: <the browser's offer>}`.
- `voice`: `voice.chatgpt_voice`, default `juniper`. Valid list for v3: juniper, maple,
  spruce, ember, vale, breeze, arbor, sol, cove (marin, alloy... are rejected).
- `prompt`: the Jarvis 007 persona for voice (section 3.3).
- `includeStartupContext: false`. REQUIRED: by default Codex stuffs about 5,300 tokens of machine and
  working-directory scanning into the prompt.
- `clientManagedHandoffs: true`, `delegationAckFiller: true`, `flushTranscriptTailOnSessionEnd: false`.
- `realtimeStartInstructions: "Do no work. Reply only: [FINAL]"`.
- `initialItems`: the memory index (`memory/MEMORY.md`) and about 12 most recent chat turns of the
  session, within a ceiling of 128 items and 8,192 tokens.

Audio goes DIRECTLY from the browser to OpenAI. The Jarvis 007 server only relays the SDP handshake
packet, so it also works when Jarvis 007 sits on a VPS. Jarvis 007 never reads the token: the app-server
handles login itself.

**Handoff to the Jarvis 007 brain.**
1. The event that arrives is `thread/realtime/itemAdded` with `item.type == "handoff_request"`, carrying
   `input_transcript`. There is no dedicated method (the old `GPTLive` frame guessed the name wrong).
2. A request that is too short (under 3 words) is merged with what the user just said in the previous ~10 seconds.
3. Emit `tool_call ask_javis` like the other Live providers: `_voice_ask_javis` runs in the background,
   carrying the interface-context block, using the main brain the user chose.
4. Codex ALWAYS opens an agent turn on its own for every handoff (`turn/started`): call `turn/interrupt`
   immediately. The `developerInstructions` above is a safety net for when the interrupt loses the race.
5. When there is a result: the FULL version appears as a chat bubble (tables, links, files). The SPOKEN
   version is derived from it (strip markdown, keep figures, ceiling about 600 characters) and sent with
   `thread/realtime/appendSpeech`, through a QUEUE (0.65.23): pushing while the model is mid-speech makes it
   mix two pieces of content into one turn (measured on Codex 0.153.4 and 0.158, the project owner
   heard it as two overlapping voices), so it only pushes when the model has been silent for 0.4
   seconds; right after a push, if the model has not started speaking, it waits up to 8 seconds; 4
   seconds with no new text counts as silent; ceiling 90 seconds. `send_tool_result` returns
   immediately, the route does not stand waiting. The model turn spoken right afterwards is a
   READ-BACK of the version already shown: the route does not send its text to the browser and does not
   write it to history (0.65.21), otherwise the user sees the same content twice. When the user speaks
   or types again, or interrupts, that flag is cleared so the new reply still appears.
6. **Extra speech while waiting** (0.65.21, bug reported by the project owner 10/01): Codex treats a
   handoff that arrives while the earlier job is still running as a STEERING message for that job, so a
   sentence like "Ok, tell me when it's done" ("Ok, xong thì báo anh nhé") turned into another handoff.
   The route filters handoffs per call session: a sentence made only of acknowledgement words
   (`voice_live.is_followup_ack`) or one that merely repeats the running request (`is_same_request`) is
   closed with `send_tool_ack` (ChatGPT Live: says nothing; Live over API: returns an acknowledgement
   sentence to match the tool call) and the brain is not run; a sentence with a new intent runs with
   `parallel_request` (along with the running jobs, stating clearly that they are NOT done yet), and
   when the brain returns `JAVIS_NOOP` because there is nothing new, there is no bubble and no speech.
   The prompt also tells the model not to hand off again when the user is only acknowledging. (0.65.21
   queued a sentence with a new intent AFTER the running job; 0.71.2 dropped that lock, see section 7.)
7. **Asking mid-way is no longer met with silence** (0.71.2, reported by the project owner 10/03): the
   0.65.21 queue lock made EVERY handoff sentence wait for the whole long job to finish. When a job ran
   for minutes, "is it done yet" and "can you hear me" both met silence, and when the job finished the
   waiting sentences ran one after another and the old answers were read out in a rush (the 17:45
   question answered at 17:56). Now the route keeps a `jobs` ledger (which job, when it started, the
   current step from the `progress` of `_voice_ask_javis`) and:
   - a PROGRESS QUESTION (`is_progress_question`, deliberately narrow) while a job is running: answered
     IMMEDIATELY with `status_line` through `say_status`, without running the brain. A vendor with no
     extra speech channel (Live over API) gets exactly that sentence returned through `send_tool_ack`.
     It is not marked `readback`, because the model itself says a filler sentence right after every
     handoff, and marking it would wrongly swallow that filler;
   - a genuinely new job runs IN PARALLEL, in its own engine thread (a single-use `key`,
     `_voice_ask_javis` cleans up its in-RAM session), the result returns whenever it is ready and is read
     out then, each result answering its own handoff;
   - `_heartbeat`: a job running past `STATUS_FIRST_S` (60 seconds) gets Jarvis 007 speaking a progress
     sentence by itself every `STATUS_EVERY_S` (90 seconds), only when `is_quiet()` (nobody is talking,
     the read-aloud queue is empty). This sentence is a `readback`, so it does not become a bubble and
     does not enter history;
   - `ChatGPTLive.say_status` shares the queue with result read-outs (it does not cut into a sentence
     being spoken) and is DROPPED from the queue if the real result arrives first, otherwise "I'm still
     working on it" would be read after "done".
   Not yet run on a real ChatGPT Live call: checked with the route running against a fake provider.

**Events translated into the shared Live frame.** `sdp` becomes `webrtc_answer`; `started` becomes `ready`;
`transcript/delta|done` becomes `transcript` (the user's `done` is `final`); assistant `done`
becomes `turn_done`; `error`/`closed` becomes `error` (reconnect once before telling the user). Interruption is
handled by the model itself (server-side VAD): `interrupt` and `truncate_played` do nothing.

### 3.3 Voice persona

A dedicated prompt for the conversational model, in Vietnamese, short: talk like a person on the phone,
1 to 2 sentences; FORM OF ADDRESS follows how the user addresses themselves (the memory in `initialItems`
tells it), not forced to a fixed one; small talk and general-knowledge explanations are answered directly;
EVERY sentence that needs real data or an action (figures, orders, calendar, email, files, opening a
page, sending a message, remembering) gets one filler sentence and then a handoff, no guessing; when a result
arrives it is read back with no added numbers; when interrupted it stops and listens.

### 3.4 The `/ws/voice-live` frame and the browser

`/ws/voice-live` stays the control channel, with a WebRTC mode added:
- `ready` carries `transport: "webrtc"` when the provider is `codex-plan`.
- The browser sends `{type: "webrtc_offer", sdp}` and receives `{type: "webrtc_answer", sdp}`.
- `transcript`, `tool`, `turn_done`, `error` keep their shape; a `handoff_result` frame (the full
  version) is added to draw the result bubble.

`dashboard/voice-live.js` gets a WebRTC branch: an `RTCPeerConnection` with an audio transceiver
`sendrecv` taking the mic track (`echoCancellation`, `noiseSuppression`), the data channel `oai-events`
(it must be present in the offer), Jarvis 007's voice played through an `<audio>` element; both sides'
audio levels for the orb come from an analyser (the remote track must be attached to a media element
before it flows into WebAudio). The PCM path of the other Live providers is skipped. Phones work because
WebRTC uses only ONE mic path.

### 3.5 Hang up on long silence, speak to reconnect (0.65.22)

After 30 seconds of silence (counted from when both sides are silent) it runs `thread/realtime/stop`,
closes WebRTC, and the call bar changes to "Waiting, just speak to continue" (`call.waiting_wake`). The browser's free listener (`liveWake` in
app.js) waits for a REAL SENTENCE (`attention.wakes`: it has a call name, or is two words or more); once heard
it opens a new thread and sends that sentence as the first words (`appendText`). From 0.65.24 it reconnects EARLY: the first interim text
of two words starts the WebRTC handshake right away without holding the mic (`deferMic`, the listener
still holds the mic, a phone allows only one holder), and only once the sentence is final does it `attachMic` and send the sentence; if the final
sentence is only a filler sound, or 12 seconds pass with no sentence, it closes. While waiting, a complete
sentence is finalised after 0.7 seconds (an unfinished sentence keeps the longer wait). Measured on the test server
(Codex 0.153.4): from the final sentence to Jarvis 007's first text went from 3.29 seconds down to 1.35 seconds. Benefit: saves quota while
silent, and avoids the bug of a session that sits silent for a long time. Text being heard shows as a draft, and `console.debug` logs the sentence heard and
the decision.

Versions 0.65.15 to 0.65.21 forced the user to say "Jarvis 007" and had a "Focus" switch (when off, the connection
was kept throughout). The project owner dropped both on 10/01: the browser often transcribes the name as "David" so
saying the name could not reconnect (Groq is not used for this because basic users do not install it), and while
connected the Live path already listens to every sound in the room so requiring the name did not block the TV
much. The Basic path has no connection to drop so it listens through the whole call (`attention.enabled` is only on in Live, `datCheDoGiong`).

A machine with no browser speech recogniser (or where it is blocked): fall back to measuring mic volume
(`SpeechLevel`, the floor learns only from quiet samples and has a ceiling). Someone speaking reconnects the call, but that sentence loses its words.

**Reconnect failing mid-call (0.65.25).** A call that has connected ChatGPT Live at least once
(`_cuocGoiDaNoi`) does NOT switch to the Basic path when a reconnect fails: it retries once after 0.8 seconds
with the very sentence just spoken, and if that still fails it shows one line ("Chưa nối lại được ChatGPT Live. Cứ nói lại là
Jarvis 007 thử tiếp.", meaning "Could not reconnect ChatGPT Live yet. Just speak again and Jarvis 007 will try again.") and goes back to waiting. The project owner reported on 10/02: a failed reconnect fell to the Basic path reading
in the Edge voice so it sounded as if Jarvis 007 changed from a female to a male voice midway, whereas the intent was
for ChatGPT to carry the whole call. Only a failed FIRST open of the call switches to the Basic path as in section 3.1. The early reconnect
is not inside any tap, so `AudioContext.resume()` may only be awaited for at most 1 second (an iPhone can
hang it forever).

**Screen awake.** When a phone locks its screen the browser cuts the mic and the call goes silent (the project owner
reported it on an iPhone, app opened from the home screen). During a call, `screen-awake.js` requests a Screen Wake Lock
right inside the mic tap, requests it again when the page becomes visible again, and releases it on hangup. A device that does not support it is skipped.

### 3.6 The `basic` fallback path

The same calling experience but only one side speaks at a time, for machines with no Live: Web Speech does the draft and the
sentence stop point, the headset-again (Groq) finalises the text, the Fast lane if there is a voice brain (otherwise the main brain),
the Edge voice. The mic reopens itself after every sentence, interrupting works with the tone-flash trick (Appendix A2). This is exactly the
current hands-free mode, only the shell changes.

## 4. The calling experience

- **Mic button** turns into **Hang up** during a call. Esc also hangs up. The Space key does nothing any more.
- **Call bar** sits right above the chat frame, on every page that has a chat frame (including the Chat page):
  a status dot + text ("Listening", "Jarvis 007 is speaking", "Working: <job name>", "Waiting, speak to
  continue", "Reconnecting"), a call timer, a **Mute** button (`track.enabled =
  false`, Jarvis 007 can still speak) and a **Hang up** button.
- **Bubbles**: the user's words appear as a draft while they speak and then settle; Jarvis 007's words run along with the
  spoken voice; a handoff result is one full bubble. All of it enters session history like ordinary messages.
- **Orb** (home page) and the mascot still follow the real state, drawn through `capNhatOrb()`.
- **Errors**: if the path in use cannot connect, show one line and automatically move down to the next path in
  section 3.1, without making the user go into settings. A reconnect MID-call of ChatGPT Live is the exception and does not
  switch path (section 3.5).
- Typing during a call still works: the text is sent into the call (`appendText`).

## 5. The Voice settings page

```
VOICE
  Using: ChatGPT Live                                <- with the reason when on a fallback path
  Jarvis 007's voice [ juniper                 v ] [▶]    <- list changes with the call path
  > Advanced
      Call path      [ Automatic v ]  (Automatic / ChatGPT Live / Live with an API key / Basic)
      Quick-reply brain [ Automatic (now ...) v ]  (Basic path only)
      Model          [ Provider default v ]  (model of the brain in use, 0.65.26)
      Speaking rate  [ 1.10x  v ]   (Basic path only)
      ElevenLabs     key + Voice ID (only when an ElevenLabs voice is chosen)
```

- **Every field saves itself on change**, there is no Save button any more. Laid out in one column.
- **Jarvis 007's voice**: the chatgpt path shows the 9 v3 voices, "Preview" plays a pre-recorded sample
  (`dashboard/voices/<voice>.mp3`, a few tens of KB per voice); the api path shows that provider's
  voices; the basic path shows Edge voices, OpenAI voices once a key exists on the Models page, and the
  separate ElevenLabs voice (key and Voice ID under Advanced). On the basic path, choosing a voice also chooses the
  speech provider.
- **Removed from the UI, the machine handles it**: reading replies aloud with voice (duplicates the mic button), the
  experimental conversation pacing (the input field is removed entirely; the control code is forced off, awaiting a separate cleanup PR), words that are often misheard (it takes the assistant's name and the MCP connection names on its own), the
  OpenAI API key field (it is on the Models page), listening language (follows the interface language), silence before sending (default
  1.2 seconds), interrupting by voice (always on), headset-again (always auto-selected), the dead key
  `loc_tap_am`, the old key `stt_provider`.
- **Quick-reply brain** (removed in 0.65.19, brought back in 0.65.25 because the project owner wanted to adjust it; since 0.65.31 the whole brain + Model block is only SHOWN when `call.engine` is basic, including when Automatic falls to Basic, because showing it next to ChatGPT Live reads as if that brain were answering): Automatic
  (the first brain available on the plan, with the name in use noted), Main brain (saves `mode = standard`), or
  a specific brain (saves `mode = fast` + `brain_provider`); a brain not ready is written "(not ready)". Used
  only on the Basic path: ChatGPT Live listens and answers by itself, and work needing data goes to the main brain.
- **Model** (0.65.26): the model of the brain in use (on Automatic, that of the brain the machine picked); hidden when
  Main brain is chosen. Saved PER brain (`brain_models` = {brain: model}, sent up with
  `brain_model_for` + `brain_model`), because a model name only means something to its own vendor. The old shared key
  `brain_model` is ignored at run time: when the brain was changed in 0.65.25 while that key still held a ChatGPT model name,
  Antigravity received `--model gpt-6-luna` and rejected it. The list loads separately through
  `GET /voice/brain-models?provider=` (it runs `agy models` only when Antigravity is chosen); API brains have no
  list yet so they only have Default. A saved model that is no longer in the list still shows, marked "(no longer listed)". The message in the chat frame for a model-name error points only to this field, and does not say to go to
  the Models page.
- **Keep old data**: values the user already saved in the removed fields are still read and still used (for example, words
  already declared in hotwords still go into the priming words); only the input field disappears. A new key never overwrites the old key.
- The `POST /settings` allowlist (the `voice` branch) and `test_luu_cai_dat_giong.py` are updated together.
- **Self-chosen voice brain** (`voice_brain.auto_brain`): in the Fast lane, when the `brain_provider` key is empty
  it uses the first brain available on the plan in the order antigravity, codex, claude, grok (probing the binary and
  the saved token, no network question, remembered for 60 seconds). If none exists, messages from the mic go to the main brain.
  The old key `mode = live` counts as the Fast lane because Live is now its own call path.
- The read endpoint `GET /voice/options?brains=0`: drops the brain list so it does not run `agy models` (sometimes
  up to 30 seconds); it also returns `call` (the call path), `tts` (the basic-path voice), `voice_brain`, and
  from 0.65.25 `brain_choices` (`voice_brain.brain_available`: plans check the binary and token, APIs check the saved
  key) along with `brain_auto`.

## 6. Order of work (one PR per step, reserve the version number first per `docs/quy-uoc-dev.md`)

1. **ChatGPT Live**: the `codex-plan` provider, the WebRTC frame on `/ws/voice-live`, the WebRTC
   branch in `voice-live.js`, handoff to the Jarvis 007 brain + result bubble, drop after 20 seconds of silence,
   the juniper voice, pre-recorded samples for 9 voices. Selectable in the existing Live provider field.
2. **Calling experience for every path**: call bar, Hang up button, Mute, remove Space, automatic call
   path choice (section 3.1), the basic path using the new shell.
3. **Tidy the settings page** as in section 5, remove adaptive pacing from the UI.

## 7. Testing

- **Python** (a fake app-server through `popen_factory`): the shape of `thread/start` and `realtime/start` (with
  `includeStartupContext: false`, the feature flag, default voice juniper); handoff becoming `tool_call`
  with a merged request when too short; `turn/started` being interrupted; the result going out as shortened `appendSpeech`
  and a full bubble; refusing permission approval requests; one reconnect on `closed`; call path selection.
- **JS** (node): the WebRTC branch creates an offer with `oai-events`, sets the answer, plays no PCM; the call bar
  follows state; Esc hangs up, Space does nothing; 30 seconds of silence drops it and a real sentence reconnects (`liveWake`); the settings
  page saves itself and no longer has the removed fields.
- **Real trial**: computer and phone (Android Chrome, iPhone Safari): small talk, asking for figures
  (handoff), opening a page, interrupting, silence past 30 seconds then speaking again, a 15-minute call.
- **Benchmark harness**: `tools/stt_bench` for the listening part; the test set in the scratchpad of the 10/01 session
  (`spike_live.py`) is the template for a later Live runner.

## 8. Risks

- **The Codex realtime API is experimental**: capability is probed when a call opens, and if it fails it drops to the
  next path by itself and states the reason. Track new Codex versions (0.159 stabilised the realtime flag).
- **ChatGPT plan quota**: both the call and every interrupted Codex turn count toward the quota. The project
  owner accepts this. Dropping on 30 seconds of silence reduces it significantly.
- **Plan terms of use**: OpenAI has not spelled out the limits for this use. One person sitting and calling is
  close to ordinary personal use; several people sharing one plan through the same Jarvis 007 falls outside
  personal use, like the note in CLAUDE.md about the Claude plan and the xAI plan. Do not offer empty reassurance.
- **The voice and personality of the outer layer belong to OpenAI**: the brain the user chooses only does the work
  behind it. Anyone who wants a different voice forces the call path to Basic.
- **Privacy**: audio goes to OpenAI the whole time it is listening. Dropping on silence and muting the mic limit
  this; `includeStartupContext` is always off so machine information is not exposed.

## Appendix A. The voice layers that are running

Distilled from the older specs (Voice V1, V2, headset-again, adaptive pacing, focus, the 09/24 audit), keeping only
what was checked against the code on 10/01/2026. Code points back to the entries below.

### A1. Turn director (voice-turn.js) and orb state
- A pure module, touching no DOM or audio. voice.js and app.js send events in and get back an ARRAY of actions (`commit`, `hold`, `stop_tts`, `stop_turn`, `pause_tts`, `resume_tts`, `listen`, `speak_filler`, `flush_deferred`) which they carry out themselves.
- State is derived from flags by a priority list (`_recompute`): reconnecting, error, interrupted, user_speaking, waiting_for_user, speaking, processing, listening, idle. To add a state, add it to this list, do not hand-write each transition pair.
- End-of-turn waiting uses two thresholds, a single clock, reset when new words arrive. A sentence ending in a conjunction, preposition, comma, filler sound ("ừm", "ờ", "kiểu", Vietnamese hesitation words roughly like "um", "uh", "like") or only calling "Jarvis 007" waits `maxDelay` 2200 ms; otherwise it waits `minDelay` 1200 ms (`javis.endpoint`). It never commits an empty turn. "à" is not in the list because "vậy à" ("is that so") is a finished sentence. No end-of-turn detection model is used because LiveKit does not support Vietnamese.
- The WAIT/STOP phrases must match the whole sentence after removing "Jarvis 007 ơi" (a Vietnamese vocative, "hey Jarvis 007") and trailing particles; a stuttered version is still accepted if every word belongs to the vocabulary; a sentence with an unknown word ("khoan, mở Chrome", meaning "hold on, open Chrome") is a normal message. WAIT does not send and holds for at most 90 seconds. STOP only stops reading aloud (0.65.28): the running turn finishes writing its answer into the chat frame, and the rest is not read.
- **During a call nothing stops a turn on its own** (0.65.28, settled by the project owner 10/02 after seeing "Đã dừng lượt này" ("This turn was stopped") over and over on the Basic path): a turn stops only on hangup or the Stop button. A sentence spoken while Jarvis 007 is answering is queued (`xepCauChoLuot`, several sentences are merged), shown as a draft, and sent only when the old turn is done AND the speaker has finished reading (`guiCauChoLuot`, called from `turn_done`, `onSpeakEnd` and the speaker watchdog tick). Cutting in or saying "thôi" ("enough") makes `stop_tts` mark the running turn `imLoa` (speaker silenced): no more reading aloud, the text shows in full instead of following the speech. Outside a call (one-shot mic) it still stops the old turn and then sends, as before.
- Progress sentence: if processing exceeds 2.5 seconds (1.2 seconds while calling a tool) with no real text yet out of the speaker, it speaks exactly once per turn.
- Background news (the `push` frame) is read only in `idle`/`listening`, deferred in other states; the text still shows immediately.
- The orb only shows the real state taken from the director (`ORB_LABEL` in app.js), drawn only through `capNhatOrb()`. The SLOW NETWORK suffix only appears when a TTS chunk takes more than 2500 ms to play.

### A2. Ears and mouth in the browser (voice.js, voice-chunker.js)
- Web Speech captures the mic on its own stream, with no echo cancellation, so recognition must stop while TTS plays, otherwise it transcribes Jarvis 007's voice as the user's words. For the same reason a "ừ, à" (Vietnamese "uh-huh" / "ah") filler sound is deliberately not made.
- Interrupting works by a TONE FLASH: 2 beats of 100 ms above the threshold is only a suspicion; lower the speaker to 12% for 4 beats and measure again, echo drops with the volume while a human voice does not (still above 45%). If it is a person, `bargeConfirmed` stops the reading outright (without waiting for text); the running turn is NOT stopped (0.65.28, see A1). The room's echo level is self-learned, saved as `javis.nenVong`, capped at 0.3.
- A phone allows only ONE mic capture path: mobile does not record in parallel and has no headset-again on the Web Speech path. WebRTC (section 3.4) uses exactly one path so it works.
- Chrome Android delivers the final as the whole sentence and still revises the sentence between fragments: merge with `ghepManh`, not `+=`. iOS forces `continuous=false` and often fails to finalise (merge `_duoiTam`). Each turn is at most 30 seconds.
- Text already shown at commit time is immutable: a late final, the secondary STT or AI must not silently edit it. Stopping before any result arrives accepts the first final.
- Edge TTS streams bytes immediately; the first chunk is fetched before the response is returned so an error becomes a real 502. A failed chunk is retried once with the same voice and then reported, without changing provider and without switching to the device's voice. An epoch blocks stale audio callbacks. Emma Multilingual is the default Edge voice.
- voice-chunker.js for every lane: the first chunk is cut early (6 words with a comma or conjunction, or a full 12 words), later chunks are cut at the end of a sentence or past 220 characters; after 400 ms of silence it only pushes a chunk when the speaker is quiet. It does not read each streamed fragment because each chunk is one TTS request. Code blocks are dropped, stopping at `<!--`. "so"/"or" are not in the conjunction list.

### A3. The Fast lane: the voice brain (voice_brain.py)
- Messages carrying `voice: true` (including text typed while hands-free) go to the voice brain. Every brain only needs the contract `stream(text, history)`, and closes itself after 5 minutes of silence.
- Four markers never reach the speaker: `JAVIS_NGHE`, `JAVIS_ASK_MAIN`, `JAVIS_UI`, `JAVIS_BO_QUA` (the last is only a legacy: the prompt forbids using it, and it no longer deletes speech).
- With no `JAVIS_NGHE`, or when the paraphrase is rejected by `safe_transcript_rewrite` (phonetic threshold 0.6, at most 4 words per phrase, not touching numbers, negations or commands), the main brain receives the verbatim text with `GHI_CHU_CAU_NGHE`. This fall-through is SILENT (only a fleeting status line), so the context block standing before the speech must be split out completely: `nghe_sua.split_ui_context` accepts both the FILE ĐANG MỞ block and the NGỮ CẢNH GIAO DIỆN block (0.65.29). Before that, with a file open, every spoken turn silently went to the main brain even though a quick-reply brain was chosen.
- `JAVIS_ASK_MAIN`: the voice turn ends immediately, the job runs in the background under the lock `voice:<sid>:<id>`. The task must hold a reference (`_nho_viec_nen_giong`) or the garbage collector swallows it. Duplicate jobs are blocked (word similarity 0.8), at most 3 in parallel. "Stop the background job" is a hard rule in code and does not become a new job.
- `JAVIS_UI` does not wake the main brain (that turn sometimes carries over 200 thousand tokens of context).
- `MODES`, `BRAIN_PROVIDERS`, `STT_PROVIDERS` are the single source for both the Settings page and the `POST /settings` save branch.
- The deterministic name-fix layer `nghe_sua.sua` ("David" becomes "Jarvis 007") runs before saving; remove it and Jarvis 007 answers "anh nói là David" (Vietnamese for "you said David", in an older-brother register).

### A4. Headset-again (voice_ear.py, stt.py, nghe_sua.py)
- `voice.ear` = auto | groq | off, DELIBERATELY with no default in config.py; the old key `stt_provider: "groq"` still counts as a manual choice.
- `transcribe_upload`: Groq Whisper, `loc_ao_giac`, `nghe_sua.sua`, then `khop_ban_nhap` (anti-fabrication: if it deviates from the draft, keep the draft). MCP connection names only prime Whisper, they do not enter the fuzzy fix layer.
- Upload only when the recording covers the entire turn; length is not taken as evidence of which version is right. The first turn after page load waits for the mic stream before opening recognition.
- `loc_ao_giac` cuts the YouTube outro sentences that Whisper invents, judged per sentence; better to miss one invented sentence than swallow real words. On meeting a new invented pattern, add the pattern AND add a real sentence close to it to the test.
- Measurements and the paths rejected: sections 1 and 2. Codex realtime: section 3.2.

### A5. Live over an API key (voice_live.py, voice-live.js)
- The browser sends PCM16 at 16 kHz and receives 24 kHz. A new provider only needs one `LiveProvider` subclass.
- `ask_javis` runs in the background. Gemini 3.1 Flash Live (default) has no asynchronous tool yet so the model waits silently; OpenAI Realtime must queue `response.create` until `response.done`.
- Interruption: the browser sends `played` (the real ms played) so the server cuts the context at exactly where it was heard. Gemini must wait for `setupComplete` before sending PCM; the user transcript is separate from the model's `turnComplete`.
- `generation` owns the socket and callbacks of each session. GPT-Live has never run for real, and guessed the delegation frame name wrong (section 3.2).

### A6. Controlling the UI by voice (ui_bridge.py, plugin javis-ui, desktop-apps)
- Control goes through a TOOL, not a text block in the answer: the server strips every `JAVIS_*`, there is no path to report a result back, and Telegram would see garbage.
- `ui_bridge.request` sends `ui_action` to the tabs and waits for `ui_result`; with no tab it reports an error immediately, and after 4 seconds it times out. The dashboard re-checks the target before running.
- A new page must be added in THREE places: `RAIL_ITEMS` (console.js), `PAGES` (ui-actions.js), `PAGES` with the diacritic-free aliases in `server/ui_targets.py`. Sidebar groups use the key `id` because labels change by language.
- desktop-apps: opening and closing happen right away with no confirmation (the project owner's choice). Closing is by default a polite close so the app asks to save itself; `force` only when the user says to force quit. It blocks itself when running in Docker or on headless Linux.
- The `[NGỮ CẢNH GIAO DIỆN: ...]` (interface context) block is stripped from bubbles and titles; `kênh=giọng` (channel=voice) asks for an answer of 2 to 4 sentences. The `JAVIS_UI` shortcut only has `open_page`, `open_group`, `sidebar`, `scroll`; `open_file` and `open_task` exist only in the `javis_ui` tool.

### A7. Attention gate on long silence (voice-attention.js)
- This is an attention gate, NOT speaker recognition. From 0.65.22 it is only on in the Live path: 30 seconds of silence (`IDLE_MS`) drops the provider, and the first real sentence (`wakes`) reconnects it. The Basic path listens through the whole call.
- The `focus_mode` switch has been removed from the Settings page; the server still accepts the old key but app.js does not read it. Words already received are not deleted based on guessing noise from the text.
- An opening sentence close to the call name ("David ơi", "hey David") does not open the gate, it is only handed to headset-again.
- Live while waiting: close the connection, send the calling sentence exactly once after `ready`, reload at most 12 messages or 8,000 characters.
- Known limit: a TV saying "Jarvis 007" can still wake it.

### A8. Adaptive conversation pacing (removed from the UI in 0.65.19, code still awaiting cleanup)
- It was once switched on through `javis.adaptive` (off | observe | natural). From 0.65.19 `voice-adaptive-ui.js` forces `off`, ignores the saved value, and no field remains on the page; the control code (`voice-adaptive.js`, the `adaptive` branch in `app.js`) awaits a PR to remove it entirely.
- The SQLite receipt (`voice_turn_protocol.py`) guarantees that a resend does not rerun an action. `ack_only` (acknowledging without answering) is very narrow: when unsure, answer normally.
- When removing the UI, keep two guarantees: committed text is immutable, and the epoch blocks old callbacks.

## Appendix B. Rules guarded by tests

- `test_voice_turn.js`: the state machine, two-threshold waiting, WAIT/STOP, interruption, deferring background news.
- `test_orb_trang_thai_that.js`, `test_ngat_loi_nha_tieng.js`: the orb only goes through the director; tone-flash constants, `bargeMinTicks = 2`.
- `test_mic_dien_thoai_mot_duong_thu.js`: one mic capture path on phones. `test_mic_doc_chong_va_loa_theo_mic.js`: no accumulating fragments on Android. `test_mic_khong_tu_gui.js`: the mic does not send noise by itself.
- `test_voice_capture_lifecycle.js`, `test_voice_app_session.js`: the recording covers the turn, STT order, late final, changing chat.
- `test_voice_chunker.js`, `test_voice_v3_mot_luong.js`, `test_voice_v2_day_noi.js`: chunk cutting and the wiring.
- `test_ui_actions.js`: the three page lists and two group lists must match. `test_ui_bridge.py`, `test_desktop_apps_plugin.py`, `test_channel_ui_prompt.py`, `test_ui_context.js`: UI control and the context block.
- `test_tts_stream.py`: Edge streaming, an immediate error becomes 502. `test_voice_privacy.py`: the `/tts` query does not enter the log.
- `test_luu_cai_dat_giong.py`: save then re-read the voice settings (trap: it must use `base_url=http://127.0.0.1:7777`, otherwise 403).
- `test_stt_ao_giac.py`, `test_stt_route.py`, `test_voice_ear_select.py`, `test_voice_ear_upload.js`: headset-again.
- `test_voice_brain.py`, `test_voice_transcript_integrity.py`, `test_voice_turn_integrity.py`, `test_voice_ten_javis.py`, `test_nghe_sua.py`, `test_voice_tap_am.py`: markers, the `JAVIS_NGHE` guard, fixing the Jarvis 007 name.
- `test_viec_nen_giong_khong_chet_lang.py`, `test_viec_nen_giong_dung_khung_chat.py`: background jobs hold their reference, report back to the right chat frame.
- `test_voice_attention.js`, `test_voice_focus_app.js`, `test_voice_live_focus.py`: focus.
- `test_voice_live.py`, `test_voice_live_transcription.py`, `test_voice_live_language.py`, `test_voice_live_lifecycle.js`: Live.
- `test_voice_adaptive*.js`, `test_voice_turn_protocol.py`, `test_voice_protocol_ws.py`: adaptive pacing and the receipt.
- `test_route_table.py`: adding or changing a route means re-snapshotting the table (`--update`) in the same commit.
