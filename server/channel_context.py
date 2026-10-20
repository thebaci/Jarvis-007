"""
Ngữ cảnh kênh hội thoại - port ý tưởng gateway của hermes-agent (NousResearch).

Vấn đề: Javis nhận tin từ nhiều "cửa" (Telegram, dashboard web) nhưng model
không tự biết mình đang trả lời qua cửa nào, và file tạo ra không quay về
đúng kênh. Hermes giải bằng cách gateway CHÈN metadata kênh vào context mỗi
phiên (gateway/session.py: Source + User + Connected Platforms + Delivery
options). Module này làm đúng việc đó cho Javis:

1. build_channel_block()  - block metadata kênh chèn vào system prompt.
2. collect_turn_files()   - gom file sinh ra trong 1 lượt trả lời để gateway
                            tự gửi trả qua kênh chat (Telegram).
"""
import json
import os
import re
from pathlib import Path

# Trần an toàn khi auto-đính kèm file trả về kênh chat
MAX_FILES_PER_TURN = 10
MAX_FILE_MB = 50          # trần sendDocument của Telegram bot

# Không bao giờ auto-gửi file nằm trong các folder nội bộ/rác này
_EXCLUDE_PARTS = {".git", "__pycache__", "node_modules", ".obsidian", ".trash", ".tmp"}


# Chat apps that share one block (see the branch in `build_channel_block`):
# source -> (name, what a group chat is called there, lines only that app needs).
_CHAT_APPS = {
    "slack": ("Slack", "Slack channel", (
        "- In a Slack channel, your reply goes into the THREAD of the message that called you, "
        "so there is no need to repeat the question.",
        "- Bot commands on Slack are typed with an exclamation mark (`!stop`, `!new`) because "
        "Slack reserves `/` for its own commands.")),
    "whatsapp": ("WhatsApp", "WhatsApp group", (
        "- LIMIT of about 4000 characters per message. Write concisely from the start, do not "
        "let the gateway cut it for you.",
        "- WhatsApp only lets Jarvis 007 message first within 24 HOURS of this person's last "
        "message. For background work that runs longer than that, the result may not get "
        "through: say so clearly when handing off long-running work over WhatsApp.")),
    "discord": ("Discord", "Discord channel", (
        "- LIMIT of 2000 characters per Discord message. Write concisely from the start; "
        "anything longer is split by the gateway into several messages.",
        "- In a server channel, you are only called when someone @mentions the bot or replies "
        "to a bot message, so go straight to the point.",
        "- Bot commands are typed with an exclamation mark (`!stop`, `!new`) because Discord "
        "reserves `/` for its own registered commands.")),
    "lark": ("Lark/Feishu", "Lark group", (
        "- In a group, you are only called when someone @mentions the bot, so go straight to "
        "the point.",
        "- Lark shows basic markdown (bold, italic, links, bullets, code blocks) but NO "
        "tables.")),
}


def build_channel_block(source: str, meta: dict = None, telegram_running: bool = False,
                        port: int = 7777, brain_root: str = None) -> str:
    """Block 'KÊNH HỘI THOẠI HIỆN TẠI' để nối vào cuối system prompt.

    source: "telegram" | "dashboard". meta: dict do telegram_bot trích từ update
    (chat_id, chat_type, chat_title, user_name, username). Giữ block ỔN ĐỊNH
    giữa các lượt cùng 1 kênh (không nhét message_id hay giờ) - session CLI
    --resume không bị lệch context, giống cách hermes giữ prompt cache.

    brain_root: đường dẫn brain của PHIÊN này. NHÉT vào recipe curl POST /reminders để nhắc hẹn
    rơi ĐÚNG brain. Thiếu nó thì endpoint âm thầm dùng Brain Default (reminders.py) - đây chính là
    bug "chat bằng brain khác nhưng nhắc hẹn vẫn vào default": curl từ Bash không mang session/cookie
    nên brain CHỈ đi được qua body, mà recipe cũ lại bỏ trống field brain.
    """
    meta = meta or {}
    # Cặp key-value brain để chèn vào JSON body của curl (rỗng nếu không rõ brain → giữ hành vi cũ).
    # json.dumps để path có KHOẢNG TRẮNG ("My Bullet Journal") vẫn là chuỗi JSON hợp lệ.
    brain_kv = f'"brain":{json.dumps(brain_root)},' if brain_root else ""
    platforms = ["local (files on the machine running Jarvis 007)", "web dashboard"]
    if telegram_running or source == "telegram":
        platforms.append("Telegram bot")
    if source == "zalo":
        platforms.append("Zalo bot")
    if source == "slack":
        platforms.append("Slack bot")
    if source == "whatsapp":
        platforms.append("WhatsApp")
    if source == "discord":
        platforms.append("Discord bot")
    if source == "lark":
        platforms.append("Lark/Feishu bot")

    lines = [
        "", "",
        "# === KÊNH HỘI THOẠI HIỆN TẠI (inserted automatically by the Jarvis 007 gateway - real data, not guesses) ===",
        "- The user's message may come from a VOICE RECOGNIZER (mic, voice message): English words, proper nouns "
        "and tool names are often transcribed as similar-sounding words (Javis becomes David/Jarvis). Understand the "
        "sentence from the context of the conversation and follow what they meant to say; do not cling to the "
        "literal mis-heard word and do not comment on it. Only ask back when a wrong guess would cause harm "
        "(numbers, recipients, outside actions).",
        "- When the user asks about the CURRENT state of crons, recurring jobs, reminders or a medication schedule: "
        "you MUST call `javis_schedule` with `op=list` before answering. Do not infer from memory/index and do not say "
        "\"there is no tool\" when this tool is shown in the list.",
        "- When the user asks to CREATE/EDIT/DELETE/CANCEL/TURN OFF a cron, recurring job or reminder: you MUST use "
        "`javis_schedule`. For delete/cancel without an id, call `op=list`, match the right item, then call "
        "`op=cancel`; do not send the user to the Scheduled page to do it themselves, and only confirm after the tool "
        "returns success. If the tool fails: do NOT call DELETE, do NOT guess a JSON body and NEVER "
        "edit `Javis/reminders.json` directly - doing so can cancel the wrong job.",
        "- ONLY CREATE WHEN THE PRECONDITIONS HOLD: before creating any schedule or recurring job, check whether, by the time it "
        "runs, it will have EVERYTHING it needs - are the data sources connected (Gmail/Calendar/POS... check with "
        "`javis_connections`), and is there a channel to REPORT the result to. If something is missing, SAY SO PLAINLY and "
        "ask the user whether to connect it first or create it anyway; NEVER create it just to be done and then stay silent while the job "
        "fails every day without the user knowing.",
        "- ONLY call `javis_schedule` when the user clearly orders you to read/create/edit/delete Jarvis 007's automatic schedules. "
        "If the user only mentions \"scheduling\", booking, 1-1 consulting, an appointment, or is asking for opinions about "
        "a product/UX/marketing, that is a normal conversation: answer the question asked, do NOT `op=list`, "
        "do NOT list crons/reminders and do NOT create a schedule on your own.",
        "- For any live data or external account data (MCP/Google/POS...): you must call the "
        "right tool, or `javis_connections` / `javis_search_tools` to find the tool. If the tool really fails, "
        "state the exact error you just received; do not invent a status from old context.",
        "- DO NOT PROMISE WHAT YOU CANNOT DO. Your reply turn ENDS the moment you finish "
        "speaking: nobody wakes you up to finish the job, and you do NOT keep running in the background. So "
        "NEVER say things like \"I am looking into it/checking, I will report as soon as I have a result\", "
        "\"I will report back when done\", \"give me a moment\", \"I will wait and then summarize\", "
        "or any other variation of them. There are only two correct "
        "paths: (1) DO IT NOW in this turn and return the real result, or (2) hand it off as background work "
        "(`javis_task` op=add) / a reminder (`javis_schedule`) and say clearly what was handed off and where the result "
        "will land. If you can do neither, say plainly that it has not been done, do not make a promise.",
        "- ONLY QUEUE BACKGROUND WORK WHEN THE USER TELLS YOU TO. The Kanban queue is where a job the user "
        "just asked for RUNS when this turn cannot finish it, it is NOT a to-do notebook. Plans, "
        "recommendations and \"next steps\" that YOU came up with go in the text of your "
        "answer; until the user agrees, they remain proposals. Do not invent jobs like \"apply the plan "
        "just presented\", \"update the timeline\", \"follow up and remind\", \"keep reviewing\". "
        "A normal planning chat creating NO new jobs is correct.",
        "- Every job created fires a notification to the bell and to this chat box when it finishes or "
        "gets stuck, so creating extras annoys the user rather than showing diligence. If you are not sure whether the user wants to "
        "hand it off, ASK ONE QUESTION before creating, do not create first to be safe.",
        "- After handing off background work, READ the result the tool returns and report it exactly as it is. If the tool "
        "says orchestration is OFF, the job is only waiting in the queue and has not run - you must say that plainly "
        "and tell the user to turn on \"AI self-driving\" on the Tasks page, you must NOT shorten it to \"the job is "
        "running, the result will come back on its own\".",
        "- ADDING an MCP / connecting a new source: you MUST use the `javis_add_mcp` tool (op=find to look in the Connection Store "
        "first, op=add to connect). Only this way does the new source land in Jarvis 007's store and SHOW in the "
        "'Connected' area of the Connections page for the user to see, and every brain can share it. "
        "NEVER add it with `claude mcp add` / `codex mcp add` and never hand-edit the MCP config file: "
        "that way only one CLI sees it, and the user looking at the Connections page thinks nothing was added. If you do not see "
        "`javis_add_mcp` in the tool list, it is sitting behind `javis_search_tools` - find it and call it "
        "through `javis_run_tool`, do not conclude it cannot be done. After adding, SAY CLEARLY that it is on "
        "the Connections page, whether it is on or off, and what permission level it is at.",
    ]
    if source == "telegram":
        who = (meta.get("user_name") or "").strip() or "user"
        if meta.get("username"):
            who += f" (@{meta.get('username')})"
        if meta.get("chat_type") in ("group", "supergroup"):
            conv = f"group '{meta.get('chat_title') or '?'}', message from {who}"
        else:
            conv = f"DM with {who}"
        chat_id = meta.get("chat_id") or "?"
        lines += [
            f"- Source of this message: Telegram ({conv}, chat_id {chat_id}).",
            f"- Connected platforms: {', '.join(platforms)}.",
            "- Chatting via Telegram: reply SHORT, like a text message. Telegram can display "
            "bold/italic/`code` but does NOT display markdown tables - do not use tables.",
            "- Still format for readability within those limits: for 3 or more items use bullets "
            "`- `, bold the numbers and conclusions, and split long paragraphs onto separate lines. The gateway "
            "turns a `###` heading into a bold line so it is usable, but short messages do not need one.",
            "",
            "## Sending files to the user via Telegram (2 ways)",
            "1. AUTOMATIC (preferred - always goes to the RIGHT person asking): a file you create with the Write tool in "
            "this turn, a file with an ABSOLUTE PATH in the final answer, OR an image/file in the vault "
            "embedded as markdown ![](attachments/...) (e.g. an IMAGE Jarvis 007 just generated) - all are attached and sent by Jarvis 007 "
            f"via Telegram right after the answer (at most {MAX_FILES_PER_TURN} files per turn, each file "
            f"under {MAX_FILE_MB}MB). For an image you just created: ONLY embed ![](attachments/...) and the user "
            "receives it, NO need for curl (curl easily sends to the bot owner by mistake).",
            "2. SEND NOW / a file that already existed: use the Bash tool to call "
            f"`curl -s -X POST http://127.0.0.1:{port}/telegram/send-file "
            "-H \"Content-Type: application/json\" "
            "-d '{\"path\":\"<absolute path>\",\"caption\":\"<short description>\","
            f"\"chat_id\":\"{chat_id}\"}}'`",
            f"- ALWAYS keep \"chat_id\":\"{chat_id}\" in the command above so the file goes to the RIGHT person asking "
            "(without it the file is sent to the bot owner by mistake).",
            "- Do NOT say \"I sent the file\" until you have done one of the two ways above.",
            "- Files the user sends over Telegram have already been downloaded to the machine by the gateway - the path is right in the message.",
            "",
            "## Setting reminders (Jarvis 007 WAKES ITSELF UP to send later - use when the user wants to be reminded)",
            "When the user wants to be REMINDED at some time (\"remind me in 30 minutes...\", \"remind me at 8:30 tomorrow morning...\", "
            "\"every morning at 7 remind me to take my medicine\", \"tonight at 9 report today's revenue\").",
            "- PREFERRED WAY: call the `javis_schedule` tool (op=create) - it AUTOMATICALLY attaches this session's brain, "
            "so no worry about the reminder landing in the wrong brain. Only use the curl below if for some reason you cannot call the tool.",
            "- The curl way (if needed): use the Bash tool to call "
            f"`curl -s -X POST http://127.0.0.1:{port}/reminders "
            "-H \"Content-Type: application/json\" "
            f"-d '{{\"text\":\"<reminder text, short>\",{brain_kv}\"delay_min\":30,"
            f"\"chat_id\":\"{chat_id}\",\"mode\":\"notify\"}}'`",
            "- TIMING (pick 1): \"delay_min\": number of minutes from now (e.g. 30, 120); OR \"at\":\"HH:MM\" time of "
            "day (if already past it rolls to tomorrow); OR \"at\":\"YYYY-MM-DD HH:MM\" for a specific date. The server computes "
            "Vietnam time ITSELF - you do NOT need to know what time it is now, just map what the user said directly.",
            "- COMPLEX RECURRING SCHEDULES (every morning, every Monday, every 15 minutes...): use \"cron\" in place of "
            "delay_min/at, a 5-field cron expression \"minute hour day month weekday\" (weekday: 0=Sun..6=Sat). Examples: "
            "every day at 7:00 = \"0 7 * * *\"; every 15 minutes = \"*/15 * * * *\"; Monday 8:00 = \"0 8 * * 1\"; 9:00 on the 1st "
            "of every month = \"0 9 1 * *\". You convert the user's sentence into cron yourself. With cron it repeats on its own, no need for repeat_min.",
            "- SIMPLE REPEAT (no cron needed): add \"repeat_min\": number of minutes (e.g. 1440 = daily, 60 = hourly).",
            "- \"mode\":\"notify\" (default) = at the time, send back exactly the reminder text. \"mode\":\"task\" = at the time "
            "Jarvis 007 DOES the job described in the text ITSELF (reads MCP numbers, writes a draft) and sends the result here.",
            "- \"mode\":\"script\" = a monitoring job that does NOT need AI (cheap): runs one EXISTING script file in "
            "Javis/scripts (\"script\":\"<file name .py/.sh/.ps1>\"), pushes stdout here; empty stdout stays silent, "
            "a non-zero exit reports an error. Only runs files the user put in that folder themselves - do NOT invent arbitrary commands.",
            f"- ALWAYS keep \"chat_id\":\"{chat_id}\" so the reminder goes to the RIGHT person speaking.",
            ("- ALWAYS keep the \"brain\" field exactly as given in the command above (it points to the brain being chatted with) so the "
             "reminder belongs to the RIGHT brain; if dropped, the reminder lands in the Default Brain by mistake." if brain_root else
             "- (The session's brain could not be determined → the reminder will go to the Default Brain.)"),
            "- After calling curl, read the returned JSON: ok=true with due_human means it is set - confirm BRIEFLY in words "
            "(e.g. \"Ok, I will remind you at 8:30 tomorrow morning\"). Do NOT say it is set unless curl returned ok=true.",
            "",
            "## Fallback to CANCEL a reminder when javis_schedule really fails",
            "- Only use this fallback for a reminder with an id of the form `r_...`; a loop/recurring file must stop and report the exact "
            "tool error, never edit/delete the file yourself.",
            "- No id yet: read the real list with "
            f"`curl -sG http://127.0.0.1:{port}/reminders "
            f"--data-urlencode \"brain={brain_root or 'brain'}\"`; only pick an item with `status=pending` that matches for certain.",
            "- With the exact id: cancel with standard form-data "
            f"`curl -s -X POST http://127.0.0.1:{port}/reminders/cancel "
            f"--data-urlencode \"id=<r_id>\" --data-urlencode \"brain={brain_root or 'brain'}\"`. "
            "The endpoint has no DELETE and does not accept JSON.",
            "- Only confirm the cancel when the JSON returns `ok:true`; for `ok:false`, 401 or any other error, report the error as is and stop.",
            "",
            "## Creating a Loop / Task (Kanban) for the user via chat - report results to the RIGHT person",
            "A background Loop (each iteration) and a Kanban task (when it finishes) AUTOMATICALLY report their result to the Telegram of "
            "the PERSON WHO ASKED. To reach the person actually chatting (not the bot owner), attach their identity when creating:",
            f"- Creating a LOOP: add the line `owner_chat: \"{chat_id}\"` to the frontmatter of the file Javis/loops/<slug>.md.",
            f"- Creating a TASK: when you POST http://127.0.0.1:{port}/kanban/task, include the field \"chat_id\":\"{chat_id}\".",
            "- Leaving owner_chat/chat_id empty → it reports into the Javis Core box of that brain (and to the owner's own Telegram if linked), not to the person chatting.",
            "- To make a loop stop reporting every iteration (a noisy loop): set `notify: false` in that loop's frontmatter.",
        ]
    elif source == "zalo":
        # Kênh Zalo Bot. Cố ý KHÔNG gộp vào nhánh Telegram: hai chỗ khác nhau ở đúng những
        # thứ mà một câu hướng dẫn sai sẽ dạy Javis hứa hão - gửi tài liệu, trần độ dài, và
        # cách nhắc hẹn tìm đường về.
        who = (meta.get("user_name") or "").strip() or "user"
        conv = (f"group '{meta.get('chat_title') or '?'}', message from {who}"
                if meta.get("chat_type") == "group" else f"private chat with {who}")
        chat_id = meta.get("chat_id") or "?"
        lines += [
            f"- Source of this message: Zalo ({conv}, chat_id {chat_id}).",
            f"- Connected platforms: {', '.join(platforms)}.",
            "- Chatting via Zalo: reply SHORT, like a text message. Zalo can display "
            "bold/italic/`code` but does NOT display markdown tables - do not use tables.",
            "- For 3 or more items use bullets `- ` for readability, and bold the numbers and "
            "conclusions. Do not cram many points into one long prose paragraph.",
            "- LIMIT of 2000 CHARACTERS per message. A long reply is cut into several consecutive messages that read as fragments, "
            "so write concisely from the start instead of letting the gateway cut it for you.",
            "",
            "## Sending files to the user via Zalo - READ CAREFULLY, different from Telegram",
            "- Zalo Bot **does NOT yet have a document-sending API** (only images can be sent). PDFs, spreadsheets, .docx, "
            ".md can NOT be sent through this channel. NEVER say \"I sent the file\" - say "
            "plainly that it could not be sent via Zalo, then give the PATH in the brain so the user can open it themselves, "
            "or offer to summarize the content right in the message.",
            "- For an IMAGE, Jarvis 007 attaches it automatically when you embed `![](attachments/...)` as usual, "
            "but this path is experimental: if sending fails the user will see an error line.",
            "- Images the user sends have already been downloaded to the machine by the gateway - the path is right in the message.",
            "",
            "## Setting reminders and handing off background work",
            "- Reminders: call the `javis_schedule` tool (op=create). It automatically attaches this session's brain.",
            f"- Results of loops and Kanban tasks must go to the RIGHT person asking: set `owner_chat: "
            f"\"{chat_id}\"` for a loop, or the field \"chat_id\":\"{chat_id}\" when you POST "
            f"http://127.0.0.1:{port}/kanban/task. Keep the `zalo:` prefix EXACTLY - it is "
            "what the server reads to know to send to Zalo rather than Telegram.",
            "- Left empty, the result goes into the Javis Core box of the brain on the dashboard, meaning the person asking sees nothing.",
        ]
    elif source in _CHAT_APPS:
        # Slack and WhatsApp (0.71.0), Discord and Lark/Feishu (0.85.0). One branch because the
        # rules that matter are the same (short chat replies, no Markdown tables, keep the prefix
        # so results come back here); the lines that differ come from `_CHAT_APPS`. The prompt
        # stays in Vietnamese like every other block the model reads.
        ten, nhom, dong_rieng = _CHAT_APPS[source]
        who = (meta.get("user_name") or "").strip() or "user"
        conv = (f"{nhom}, message from {who}" if meta.get("chat_type") == "group"
                else f"private chat with {who}")
        chat_id = meta.get("chat_id") or "?"
        tien_to = source + ":"
        lines += [
            f"- Source of this message: {ten} ({conv}, chat_id {chat_id}).",
            f"- Connected platforms: {', '.join(platforms)}.",
            f"- Chatting via {ten}: reply SHORT, like a text message. {ten} does NOT display markdown "
            "tables - do not use tables. Bold/italic/`code`/code blocks are converted by the gateway to the "
            "platform's own format.",
            "- For 3 or more items use bullets `- `, and bold the numbers and conclusions.",
            *dong_rieng,
            "",
            f"## Sending files via {ten}",
            "- Jarvis 007 attaches images and documents automatically when you embed `![](attachments/...)` or a link to a "
            "file in the brain as usual. Do not say \"sent\" when you have not embedded anything.",
            "- Files the user sends have already been downloaded to the machine by the gateway - the path is right in the message.",
            "",
            "## Setting reminders and handing off background work",
            "- Reminders: call the `javis_schedule` tool (op=create). It automatically attaches this session's brain.",
            f"- Results of loops and Kanban tasks must go to the RIGHT person asking: set `owner_chat: "
            f"\"{chat_id}\"` for a loop, or the field \"chat_id\":\"{chat_id}\" when you POST "
            f"http://127.0.0.1:{port}/kanban/task. Keep the `{tien_to}` prefix EXACTLY - it is what the "
            f"server reads to send to {ten}.",
        ]
    elif source == "cli":
        # Terminal. Khác web ở chỗ KHÔNG render được gì: không ảnh, không bảng, không link bấm
        # được. Nói thẳng ra đây, nếu không Javis sẽ trả về markdown của web và người dùng nhận
        # một đống ký tự gạch dọc.
        who = (meta.get("host") or "").strip()
        lines += [
            "- Source of this message: Jarvis 007 CLI (the user is typing in a terminal"
            + (f", machine {who}" if who else "") + ").",
            f"- Connected platforms: {', '.join(platforms)}.",
            "- The terminal does NOT render markdown: NEVER use tables, do not embed images "
            "`![](...)`, do not use markdown links. For a file or image, print the ABSOLUTE PATH "
            "on its own line so the user can copy it or open it with another command.",
            "- Reply concisely and break lines often. Code blocks still use three backticks "
            "(the CLI can colorize them).",
            "- For 3 or more items use bullets `- ` (the terminal shows the dash correctly and it stays "
            "readable). Emphasize with CAPITAL LETTERS or sentence position, do not wrap in `**` because it shows the "
            "asterisks literally.",
            "- The person asking is in a terminal so a shell is at hand: paths and suggested commands are something they "
            "can use right away, more useful than a long description.",
        ]
    else:
        web_sid = str(meta.get("session_id") or "").strip()
        lines += [
            "- Source of this message: Jarvis 007 web dashboard (the user opens it in a browser, files appear as paths).",
            f"- Connected platforms: {', '.join(platforms)}.",
            "",
            "## How to format in this chat box (a channel for READING, not listening)",
            "- The web chat box renders FULL markdown: headings `#`..`######`, bullets, numbered "
            "lists, `- [ ]` checkboxes, **bold**, *italic*, `code`, highlighted ```code``` blocks, tables, "
            "quotes `>`, images `![](...)`, links, wikilinks `[[...]]`. Go ahead and use them, do not tighten yourself down to "
            "plain prose.",
            "- The user here READS with their eyes. When reporting work or answering a question, open with a short "
            "conclusion, and only then give the "
            "evidence and the work done; tool-call progress is already shown separately, do not retell every step "
            "in the final answer. A long answer poured out as several unbroken prose paragraphs "
            "is the worst formatting mistake in this channel. Use paragraphs of 1-3 sentences, bullets for 3 or more items; "
            "bold only 1-2 conclusions or deciding numbers, do not bold every "
            "figure. A long answer with 3 or more distinct parts gets a `###` heading for each part.",
            "- This channel CAN draw tables, so use one when comparing the same set of fields across 2 or more "
            "items. For just a flat list, bullets read faster than a table.",
            "- Interactive cards (only this chat box draws them, other channels turn them into text): insert the hidden block "
            "`<!-- JAVIS_CARD: {...} -->` as one line of JSON. `{\"type\":\"chart\",\"title\",\"kind\":\"bar|line\","
            "\"labels\":[..],\"series\":[{\"name\",\"data\":[number]}]}` for daily/weekly trends; "
            "`{\"type\":\"stats\",\"items\":[{\"label\",\"value\",\"delta\"}]}` for a few key numbers; "
            "`{\"type\":\"buttons\",\"buttons\":[{\"label\",\"reply\"}]}` (at most 4) when the owner needs to pick quickly, "
            "a click sends `reply` as the owner's message. Only use with REAL NUMBERS you just fetched; still write the conclusion in words.",
            "- Do NOT write worse out of fear of the voice: the dashboard's speaker button strips markdown (headings, "
            "bold, bullets, links, code blocks) before reading aloud, so formatting does not "
            "hurt the audio.",
            "- Still keep the voice of a person speaking and stay concise. Formatting is for readability, not an "
            "excuse to write longer or to break a small point into three bullets.",
            "",
            "## Controlling the dashboard and the computer by voice (Voice V1)",
            "- When the user tells you to OPEN a page / file / task on Jarvis 007 (\"open the Tasks page\", \"open file X\", "
            "\"show me the task I just assigned\", \"scroll down\"): call the `javis_ui` tool (action open_page | "
            "open_file | open_task | scroll) and then report exactly what the tool returned. Do not describe "
            "manual click paths when the tool can do it.",
            "- \"scroll down\" means scrolling WHAT THEY ARE LOOKING AT, which is not always the chat box: "
            "just pass target `top`/`bottom` and let the dashboard choose based on the page that is open. Only use "
            "`chat_top`/`chat_bottom` or `page_top`/`page_bottom` when the user says clearly which to scroll. "
            "The tool returns exactly what was just scrolled, just report it accordingly.",
            "- When the user tells you to OPEN or CLOSE an app on the computer (\"open Chrome\", \"close Excel\", \"which apps "
            "are open\"): call `javis_app_open` / `javis_app_close` / `javis_app_list`. The tool says so itself when "
            "Jarvis 007 is running on a server rather than the user's machine; in that case relay exactly that sentence. "
            "Closing an app is done right away as the user wishes, only pass `force=true` when they say to force-quit.",
            "- The `[NGỮ CẢNH GIAO DIỆN: ...]` block (if present) at the start of the message is what the user is LOOKING AT: `trang=` is the "
            "open page, `chọn=` is the passage they have highlighted. \"this\", \"this passage\", \"this spot\" "
            "point there, do not ask again. `ngắt_lời=` means they just interrupted you while you were reading that sentence: "
            "continue the answer from that point, do NOT read from the start again.",
            "- `kênh=giọng` in that block means the user is TALKING BY VOICE and your answer "
            "will be READ ALOUD the moment you write it. In that case the formatting rules above YIELD to the rules for "
            "speech: answer like a person speaking, 2 to 4 sentences, a short first sentence so the sound starts quickly, conclusion "
            "before detail; no headings, no tables, no bullets, no emoji, no "
            "code blocks unless they ask for exactly that. If you want to go longer, ask whether they need the details. "
            "For a long job, first say one short sentence about what you are doing and then do it.",
        ]
        if web_sid:
            lines += [
                "",
                "## Hand off background work and REPORT BACK TO THIS EXACT CHAT BOX",
                f"- Current chat session id: `{web_sid}`.",
                "- When you POST http://127.0.0.1:%d/kanban/task, ALWAYS include the field "
                "`\"chat_id\":\"web:%s\"`. That is how the result lands straight back in this chat box when the job "
                "finishes. Left empty, the result only goes to Telegram - a user sitting on the web will see nothing at all." % (port, web_sid),
                "- For a Loop created from here: set `owner_chat: \"web:%s\"` in the frontmatter, for the same reason." % web_sid,
                "- NEVER promise things like \"I will wait for the agents to finish and then summarize for you\" "
                "(or any other variation): "
                "your reply turn ENDS right after you speak, there is nowhere for you to sit and wait "
                "and nobody wakes you up to summarize. Background work reports its RAW result to the "
                "chat box by itself when it finishes. Say exactly that: how many jobs were handed off, what each one does, the result "
                "will appear here on its own, and progress is on the Tasks page. If a comparative summary is wanted, tell the user to "
                "message again after the results come back, OR hand off one final job dedicated to summarizing "
                "(use `deps` pointing at the earlier jobs) instead of making an empty promise.",
                "- Jarvis 007 CHECKS promises ITSELF: at the end of each turn the server scans the answer for a promise to report back, "
                "then compares it with the background work that really exists. If a promise is made and there is no job, the "
                "server pastes a correction line right under your sentence for the user to see. So an empty "
                "promise does not get you off the hook, it only makes the answer look worse.",
            ]
        if telegram_running:
            lines += [
                "- If the user wants to receive a file via Telegram: use the Bash tool to call "
                f"`curl -s -X POST http://127.0.0.1:{port}/telegram/send-file "
                "-H \"Content-Type: application/json\" "
                "-d '{\"path\":\"<absolute path>\",\"caption\":\"...\"}'`",
                "- If the user wants to be REMINDED later (\"remind me in 30 minutes...\", \"8am tomorrow...\"): prefer calling the tool "
                "`javis_schedule` (op=create) so the reminder lands in the RIGHT selected brain; or use the Bash tool to call "
                f"`curl -s -X POST http://127.0.0.1:{port}/reminders -H \"Content-Type: application/json\" "
                f"-d '{{\"text\":\"<content>\",{brain_kv}\"delay_min\":30}}'` (or \"at\":\"HH:MM\" / "
                "\"at\":\"YYYY-MM-DD HH:MM\", add \"repeat_min\" to repeat). Keep the \"brain\" field as is so the reminder "
                "belongs to the right brain. The server computes Vietnam time; at the time Jarvis 007 reports into the Javis Core box of that brain (and to the owner's Telegram if linked).",
            ]
    return "\n".join(lines) + "\n"


# ---- Trích đường dẫn file từ câu trả lời ----
# 3 mẫu: trong nháy/backtick (cho phép khoảng trắng - vault hay có "01 - Daily Log"),
# đường dẫn Windows trần, đường dẫn POSIX trần (không khoảng trắng).
_QUOTED_RE = re.compile(r"[`\"']((?:[A-Za-z]:[\\/]|/)[^`\"'\n]{2,300})[`\"']")
_WIN_RE = re.compile(r"(?:^|[\s(<])([A-Za-z]:[\\/][^\s`\"'()\[\]<>|*?]+)")
_POSIX_RE = re.compile(r"(?:^|[\s(<])(/[^\s`\"'()\[\]<>|*?:]+)")


def extract_paths(text: str) -> list:
    """Mọi chuỗi trông giống đường dẫn tuyệt đối trong text (chưa lọc tồn tại)."""
    out = []
    t = text or ""
    for rx in (_QUOTED_RE, _WIN_RE, _POSIX_RE):
        for m in rx.finditer(t):
            out.append(m.group(1).strip().rstrip(".,;:!?…"))
    return out


# Media/liên kết NHÚNG trong markdown: ![alt](path) hoặc [text](path).
# Chấp nhận cả đường dẫn có khoảng trắng KHÔNG bọc <> vì model thường trả
# ![](99 - Attachments/anh.png), dù CommonMark chuẩn yêu cầu <...>.
# Target được phép chứa MỘT tầng ngoặc tròn cân bằng: tên file kiểu "30 Ngày Làm Chủ Antigravity
# (CES Global).md" là chuyện thường trong wiki, và bản cũ (`[^\n)]*?`) cắt ngay ở dấu ")" đầu tiên,
# nên link đúng bị coi là "không thấy file" và bị chuẩn hoá hụt đuôi (2026-09-09). Dashboard
# (chat-render.js) đã nhận ngoặc cân bằng từ trước; hai đầu phải cùng một luật.
_MD_LINK_RE = re.compile(r"(!?)\[([^\]\n]*)\]\(\s*(?:<([^>\n]+)>|((?:[^\n()]|\([^\n()]*\))*?))\s*\)")
_MD_TITLE_RE = re.compile(r"""\s+(?:"[^"\n]*"|'[^'\n]*')\s*$""")


def _md_link_target(match) -> str:
    raw = (match.group(3) if match.group(3) is not None else match.group(4)) or ""
    raw = _MD_TITLE_RE.sub("", raw.strip())
    return raw.strip().strip("'\"")


def _vault_markdown_candidate(raw: str, vault_root: str):
    """Resolve một target Markdown về file bên trong vault; URL/anchor/path thoát vault → None."""
    if not raw or not vault_root:
        return None
    if "://" in raw or raw.startswith(("#", "mailto:", "data:", "tel:")):
        return None
    try:
        vroot = os.path.normpath(os.path.abspath(vault_root))
        if os.path.isabs(raw) or re.match(r"^[A-Za-z]:[\\/]", raw):
            cand = os.path.normpath(os.path.abspath(raw))
        else:
            cand = os.path.normpath(os.path.abspath(os.path.join(vroot, raw)))
        vroot_nc = os.path.normcase(vroot)
        cand_nc = os.path.normcase(cand)
        if cand_nc == vroot_nc or cand_nc.startswith(vroot_nc + os.sep):
            return cand
    except Exception:
        pass
    return None


def resolve_vault_relative(text: str, vault_root: str) -> list:
    """Đường dẫn nhúng Markdown → path tuyệt đối NẰM TRONG vault.

    Hỗ trợ path tương đối có khoảng trắng, dạng <path>, và path tuyệt đối trong chính vault.
    URL hoặc '../' thoát vault luôn bị bỏ.
    """
    out = []
    if not vault_root:
        return out
    for m in _MD_LINK_RE.finditer(text or ""):
        cand = _vault_markdown_candidate(_md_link_target(m), vault_root)
        if cand:
            out.append(cand)
    return out


# URL http/https trong text. Cắt đuôi bằng dấu câu vì model hay viết "xem tại https://a.vn."
# và dấu chấm cuối câu không thuộc về địa chỉ. Dấu ) đóng cũng cắt: link trong markdown
# `[tên](https://...)` sẽ nuốt luôn dấu đóng nếu không chặn.
_URL_RE = re.compile(r"""https?://[^\s<>"'`\)\]}]+""")
_URL_DUOI = ".,;:!?…\'\"`"


def extract_urls(text: str) -> list:
    """Mọi URL http/https trong text, giữ thứ tự xuất hiện, không lặp."""
    seen, out = set(), []
    for m in _URL_RE.finditer(text or ""):
        u = m.group(0).rstrip(_URL_DUOI)
        if len(u) < 11 or u in seen:      # "https://a.b" là ngắn nhất còn có nghĩa
            continue
        seen.add(u)
        out.append(u)
    return out


def markdown_targets(text: str) -> list:
    """Target của mọi link/ảnh markdown trong text, kèm nhãn: [{"raw","nhan","hinh"}].

    Khác `resolve_vault_relative` (chỉ trả path đã resolve được vào vault): ở đây giữ CẢ
    target chưa resolve được, vì một file đã bị đổi tên hay dời đi vẫn là thứ người dùng
    cần thấy - biết nó từng tồn tại còn hơn nó biến mất không dấu vết.
    """
    out = []
    for m in _MD_LINK_RE.finditer(text or ""):
        raw = _md_link_target(m)
        if not raw:
            continue
        out.append({"raw": raw, "nhan": (m.group(2) or "").strip(), "hinh": m.group(1) == "!"})
    return out


def strip_attached_media(text: str, attached_paths: list, vault_root: str) -> str:
    """Bỏ ![alt](local-path) khỏi text nếu đúng file đó đã được xếp hàng gửi riêng.

    Không đụng link thường, URL web hoặc ảnh chưa attach được. Nhờ vậy Telegram không hiện
    nguyên `![...](99 - Attachments/...)` bên cạnh ảnh thật.
    """
    attached = set()
    for path in attached_paths or []:
        try:
            attached.add(os.path.normcase(os.path.normpath(os.path.abspath(str(path)))))
        except Exception:
            pass
    if not attached:
        return text or ""

    def repl(match):
        if match.group(1) != "!":
            return match.group(0)
        cand = _vault_markdown_candidate(_md_link_target(match), vault_root)
        if cand and os.path.normcase(os.path.normpath(cand)) in attached:
            return ""
        return match.group(0)

    cleaned = _MD_LINK_RE.sub(repl, text or "")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# Ứng viên đường dẫn moi từ payload một tool call. Token = cụm không chứa khoảng trắng và
# ký tự bao thường gặp trong JSON/shell; "trông giống đường dẫn" = có dấu phân cách thư mục
# VÀ kết thúc bằng phần mở rộng. Cố tình chặt ở đây chứ không chặt ở tầng trên, vì tầng trên
# (collect_turn_files) đã lọc bằng "tệp có thật" + "vừa đổi trong lượt này".
_TOOL_TOKEN_RE = re.compile(r"""[^\s"'`,;{}()\[\]<>|]+""")
_TOOL_PATH_RE = re.compile(r"[\\/].*\.[A-Za-z0-9]{1,8}$")


def candidate_paths_from_tool(item, _depth: int = 0) -> list:
    """Mọi chuỗi trông giống đường dẫn tệp trong payload của một tool call.

    Vì sao cần: Codex CLI KHÔNG phát ra trường `file_path` có cấu trúc như Claude - tuỳ loại
    item mà đường dẫn nằm trong `changes[].path`, trong `arguments` (chuỗi JSON), hay lẫn
    trong `command` của một lệnh shell. Thay vì đoán đúng một khuôn (schema của Codex còn
    đổi), hàm này đi hết payload và THU RỘNG mọi thứ trông giống đường dẫn.

    Thu rộng là an toàn: `collect_turn_files` phía sau chỉ giữ tệp CÓ THẬT và VỪA ĐỔI trong
    lượt này, nên ứng viên thừa lặng lẽ rơi, còn thiếu thì mất file của user.
    """
    out = []
    if _depth > 6:
        return out
    if isinstance(item, dict):
        for v in item.values():
            out += candidate_paths_from_tool(v, _depth + 1)
    elif isinstance(item, (list, tuple)):
        for v in item:
            out += candidate_paths_from_tool(v, _depth + 1)
    elif isinstance(item, str):
        s = item.strip()
        if s[:1] in ("{", "["):
            # `arguments` thường là chuỗi JSON: giải mã trước, kẻo dấu \ bị nhân đôi.
            try:
                return candidate_paths_from_tool(json.loads(s), _depth + 1)
            except Exception:
                pass
        for tok in _TOOL_TOKEN_RE.findall(s):
            tok = tok.rstrip(".,;:!?…")
            if _TOOL_PATH_RE.search(tok):
                out.append(tok)
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def collect_turn_files(reply_text: str, written_paths: list, t0: float,
                       cwd: str = None, exclude: set = None, vault_root: str = None) -> list:
    """Danh sách file đáng gửi trả về kênh chat sau 1 lượt.

    Ứng viên = file agent ghi bằng tool Write (written_paths) + đường dẫn tuyệt đối
    nhắc trong câu trả lời cuối + đường dẫn TƯƠNG ĐỐI trong vault nhúng dạng markdown
    (![](attachments/x.png) - ảnh Javis tạo) khi có vault_root. Chỉ giữ file THẬT SỰ
    vừa thay đổi trong lượt (mtime >= t0) - nhắc tới file cũ sẽ không spam gửi lại; muốn
    gửi file cũ thì agent gọi endpoint /telegram/send-file. exclude = set path (normcase)
    đã gửi trong lượt qua endpoint, tránh gửi trùng.
    """
    cands = []
    for p in (written_paths or []):
        try:
            pp = Path(str(p))
            if not pp.is_absolute() and cwd:
                pp = Path(cwd) / pp
            cands.append(str(pp))
        except Exception:
            continue
    cands += extract_paths(reply_text)
    # Ảnh/tệp Javis tạo trong lượt thường được NHÚNG dạng path tương đối trong vault
    # (![](attachments/x.png)); resolve về gốc vault để tự đính kèm về ĐÚNG phiên chat.
    cands += resolve_vault_relative(reply_text, vault_root)

    seen = set(exclude or ())
    out = []
    for c in cands:
        try:
            rp = os.path.normpath(os.path.abspath(c))
            key = os.path.normcase(rp)
            if key in seen:
                continue
            p = Path(rp)
            if not p.is_file():
                continue
            if any(part in _EXCLUDE_PARTS for part in p.parts):
                continue
            st = p.stat()
            if not (0 < st.st_size <= MAX_FILE_MB * 1024 * 1024):
                continue
            if st.st_mtime < t0 - 2:   # chỉ file vừa tạo/sửa trong lượt này
                continue
            seen.add(key)
            out.append(rp)
            if len(out) >= MAX_FILES_PER_TURN:
                break
        except Exception:
            continue
    return out


# ============================================================
# Hạ khối điều khiển xuống chữ cho kênh không phải web
# ============================================================
# Javis nhúng khối điều khiển dạng HTML comment ở cuối câu trả lời cho dashboard
# đọc (hiện chỉ còn JAVIS_ASK - vẽ nút lựa chọn). Kênh chữ thuần như Telegram không
# hiểu mấy khối này, mà md_to_mdv2 chỉ escape chứ không bóc, nên không lọc là người
# dùng nhìn thấy nguyên cụm "<\!\-\- JAVIS\_ASK: ...".
# Regex để CHUNG cho mọi JAVIS_*, không liệt kê từng tên: khối lạ (vd JAVIS_METRICS
# thời còn bảng số liệu, hoặc ký ức cũ trong brain còn nhắc) thì lặng lẽ rơi mất
# thay vì lọt nguyên xi ra chat.
_CTRL_RE = re.compile(r"<!--\s*JAVIS_([A-Z_]+):\s*([\s\S]*?)\s*-->")
_MAX_ASK_OPTS = 4


def _ask_to_text(payload: str) -> str:
    """JSON của khối JAVIS_ASK -> câu hỏi + danh sách đánh số. JSON hỏng -> chuỗi rỗng.

    Người dùng Telegram nhắn lại "1" là xong: Javis đọc "1" trong ngữ cảnh câu hỏi
    vừa hỏi thì tự hiểu, không cần lưu state.
    """
    try:
        o = json.loads(payload)
    except Exception:
        return ""
    if not isinstance(o, dict):
        return ""
    q = str(o.get("question") or "").strip()
    opts = [x for x in (o.get("options") or [])
            if isinstance(x, dict) and str(x.get("label") or "").strip()]
    if not q or not opts:
        return ""
    lines = [q]
    for i, x in enumerate(opts[:_MAX_ASK_OPTS], 1):
        lines.append(f"{i}. {str(x['label']).strip()}")
    return "\n".join(lines)


def strip_control_blocks(text: str) -> str:
    """Bóc mọi khối <!-- JAVIS_*: ... --> khỏi text.

    JAVIS_ASK -> thay bằng câu hỏi + danh sách đánh số. Khối khác -> bỏ hẳn.
    Khối sai cú pháp cũng bị bỏ: một khối hỏng KHÔNG được phép nuốt mất câu trả lời.
    """
    def _sub(m):
        if m.group(1) == "ASK":
            t = _ask_to_text(m.group(2))
            return ("\n\n" + t) if t else ""
        if m.group(1) == "CARD":
            # 0.201.0: a chart, number tiles or buttons the dashboard draws; text channels get the plain version.
            import chat_cards
            t = chat_cards.card_to_text(m.group(2))
            return ("\n\n" + t) if t else ""
        return ""

    out = _CTRL_RE.sub(_sub, text or "")
    return re.sub(r"\n{3,}", "\n\n", out).strip()
