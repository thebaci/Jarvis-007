"""Plugin bundled: tool javis_voice_note - a short spoken message attached to the answer (0.202.0).

Idea from OpenMausBot's voice notes. The audio is made by server/voice_note.py (Edge TTS) and saved in
the brain's attachments/voice/; the answer embeds it as a markdown link, which the dashboard draws as
an audio player and Telegram sends as an audio file. min_mode=safe: it writes a file.
"""
from __future__ import annotations

import voice_note


def register(ctx):
    async def _note(args, cctx):
        args = args or {}
        text = str(args.get("text") or "").strip()
        if not text:
            return "ERROR: missing 'text' (the sentence to read out as a voice note)."
        res = await voice_note.make(cctx.vault_root, text, voice=str(args.get("voice") or ""))
        if not res.get("ok"):
            return "ERROR: " + str(res.get("error") or "could not create the voice note")
        rel = res["rel_path"]
        return (f"Voice note recorded ({res['chars']} characters, voice {res['voice']}), saved at {rel}. "
                f"EMBED it in your answer right away using exactly this line: [🔊 Tin thoại]({rel}) "
                "and write the same content out as text right below it so people who cannot listen can still read it.")

    ctx.register_tool(
        name="javis_voice_note",
        description=("Record a short VOICE NOTE (at most 1000 characters) as an mp3 file and embed it in the answer. "
                     "Use it when the user wants to LISTEN instead of read (\"read it to me\", \"send a voice note\", a "
                     "morning report to hear while driving). Parameters: text (the sentence to read, spoken style, no markdown), "
                     "voice (optional, an Edge voice name such as vi-VN-NamMinhNeural; left empty it is chosen by "
                     "language). After calling, embed the returned link in the answer."),
        handler=_note, min_mode="safe",
        schema={"type": "object", "properties": {
            "text": {"type": "string", "description": "The sentence to read aloud (spoken style, at most 1000 characters)"},
            "voice": {"type": "string", "description": "Edge voice name, leave empty to pick automatically"},
        }, "required": ["text"]},
    )
