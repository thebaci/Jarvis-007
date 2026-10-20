"""A bot sees a customer's photo whatever model runs it (0.94.0).

    python tests/run.py bot_mat_muon      (NO network: fake streams, httpx MockTransport)

The owner asked on 2026-10-11 "can you make it see Zalo photos with any model". Three breaks pinned here:
  1. ZALO PHOTOS DROPPED AS "NOT AN IMAGE". Zalo's photo server labels some photos `application/octet-stream`, and the downloader
     only took `image/*`. Now a generic binary label is judged by the file's first bytes; an HTML page stays out whatever its label.
  2. NO EYES FOR A MODEL THAT CANNOT SEE. A brain with no image channel (Antigravity, Grok Build) or a model that returns nothing
     for an image got the "you cannot see this photo" label. Now another brain the owner already connected describes the photo
     (main brain with the owner's model, then the ChatGPT plan, then Claude Code), and the bot's own model answers from that.
  3. THE REAL ERROR WAS LOST. Every failure was logged as "model refused the image". The original error now reaches the bot card.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-matmuon-")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import httpx  # noqa: E402

import borrowed_eyes as be  # noqa: E402
import image_vision as iv  # noqa: E402

_fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else f"  [{str(them)[:300]}]"))
    if not cond:
        _fails.append(name)


JPEG = b"\xff\xd8\xff\xe0" + b"j" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 50

# ============================================================
# 1. Sniffing and the downloader
# ============================================================
check("JPEG bytes are an image", iv.sniff_image_type(JPEG) == "image/jpeg")
check("PNG bytes are an image", iv.sniff_image_type(PNG) == "image/png")
check("GIF bytes are an image", iv.sniff_image_type(b"GIF89a....") == "image/gif")
check("WebP bytes are an image", iv.sniff_image_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp")
check("HTML bytes are not an image", iv.sniff_image_type(b"<!doctype html><html>") == "")
check("octet-stream may be an image, text/html may not",
      iv.header_may_be_image("application/octet-stream") and iv.header_may_be_image("image/jpeg; q=1")
      and not iv.header_may_be_image("text/html; charset=utf-8") and not iv.header_may_be_image("application/json"))


def cdn(request):
    u = str(request.url)
    if "octet-jpg" in u:
        return httpx.Response(200, headers={"content-type": "application/octet-stream"}, content=JPEG)
    if "octet-png" in u:
        return httpx.Response(200, headers={"content-type": "application/octet-stream"}, content=PNG)
    if "octet-html" in u:
        return httpx.Response(200, headers={"content-type": "application/octet-stream"}, content=b"<html>login</html>")
    if "nolabel" in u:
        return httpx.Response(200, content=JPEG)
    return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>")


mt = httpx.MockTransport(cdn)
_goc_httpx = iv.httpx
iv.httpx = types.SimpleNamespace(AsyncClient=lambda **kw: httpx.AsyncClient(transport=mt, **kw), Timeout=httpx.Timeout)
D = Path(tempfile.mkdtemp(prefix="javis-matmuon-dl-"))
p, why = asyncio.run(iv.fetch_image("https://f21-zpc.zdn.vn/octet-jpg", D, "m1"))
check("Zalo photo labelled octet-stream: saved as .jpg", p is not None and p.suffix == ".jpg" and p.read_bytes() == JPEG, why)
p, why = asyncio.run(iv.fetch_image("https://f21-zpc.zdn.vn/octet-png.jpg", D, "m2"))
check("the extension follows the bytes, not the link (PNG behind a .jpg link)", p is not None and p.suffix == ".png", (p, why))
p, why = asyncio.run(iv.fetch_image("https://f21-zpc.zdn.vn/nolabel", D, "m3"))
check("no Content-Type at all: judged by the bytes", p is not None and p.suffix == ".jpg", why)
p, why = asyncio.run(iv.fetch_image("https://f21-zpc.zdn.vn/octet-html", D, "m4"))
check("an HTML page labelled octet-stream stays out, nothing written",
      p is None and "không phải ảnh" in why and not list(D.glob("m4.*")), (p, why))
p, why = asyncio.run(iv.fetch_image("https://f21-zpc.zdn.vn/page", D, "m5"))
check("text/html is refused before the body is read", p is None and "text/html" in why, why)
iv.httpx = _goc_httpx

# ============================================================
# 2. Who looks: borrowed_eyes.candidates
# ============================================================
c = be.candidates("antigravity-cli", "gemini-3", main_prov="openai", main_model="gpt-4o", main_ok=True,
                  chatgpt_ok=True, chatgpt_model="gpt-5.5", claude_ok=True)
check("order: main brain with the owner's model, then ChatGPT plan, then Claude Code",
      [(p_, m) for _l, p_, m in c] == [("openai", "gpt-4o"), ("openai-oauth", "gpt-5.5"), ("anthropic-cli", "")], c)
c = be.candidates("openai-oauth", "gpt-6.1-sol", main_prov="openai-oauth", main_model="gpt-6.1-sol", main_ok=True,
                  chatgpt_ok=True, chatgpt_model="gpt-5.5", claude_ok=False)
check("never the exact provider+model that just failed (same plan, other model is fine)",
      [(p_, m) for _l, p_, m in c] == [("openai-oauth", "gpt-5.5")], c)
c = be.candidates("groq", "llama", main_prov="antigravity-cli", main_model="x", main_ok=True, chatgpt_ok=False, claude_ok=False)
check("a main brain with no image channel is not a candidate", c == [], c)
c = be.candidates("groq", "llama", main_prov="gemini", main_model="g", main_ok=False, chatgpt_ok=False, claude_ok=False)
check("a main brain that is not usable (no key) is not a candidate", c == [], c)

# ============================================================
# 3. describe: tries in order, caches, reports every failure
# ============================================================
IMG = D / "real.jpg"
try:
    from PIL import Image      # with Pillow, vision_input re-opens the file, so it must be a real JPEG
    Image.new("RGB", (8, 8), (200, 30, 30)).save(IMG, "JPEG")
except Exception:              # noqa: BLE001 - no Pillow (CI): small files are sent as they are
    IMG.write_bytes(JPEG)
CALLS = []


def fake_stream(answers):
    async def stream(prov, model, messages):
        CALLS.append((prov, model, messages))
        a = answers.get(prov)
        if isinstance(a, Exception):
            raise a
        if a is None:
            yield {"type": "error", "content": f"{prov} không nhận ảnh"}
            return
        if a == "slow":
            await asyncio.sleep(5)
        yield {"type": "text", "content": a}
    return stream


CANDS = [("main", "groq", "llama"), ("chatgpt", "openai-oauth", "gpt-5.5"), ("claude", "anthropic-cli", "")]
be._CACHE.clear()
r = asyncio.run(be.describe([str(IMG)], "giá bao nhiêu", CANDS, fake_stream({"openai-oauth": "Ảnh: bảng giá 150.000đ"})))
check("first candidate fails, second describes: ok with who",
      r.get("ok") and r.get("text") == "Ảnh: bảng giá 150.000đ" and r.get("who") == "openai-oauth/gpt-5.5", r)
first_msgs = CALLS[0][2]
check("the photo is really sent as image input with the describe prompt and the caption",
      first_msgs[0]["role"] == "system" and isinstance(first_msgs[1]["content"], list)
      and any(x.get("type") == "image_url" for x in first_msgs[1]["content"])
      and "giá bao nhiêu" in first_msgs[1]["content"][0]["text"], first_msgs)
CALLS.clear()
r = asyncio.run(be.describe([str(IMG)], "giá bao nhiêu", CANDS, fake_stream({})))
check("the same file twice: answered from cache, no second look", r.get("ok") and r.get("cached") and CALLS == [], (r, CALLS))
be._CACHE.clear()
r = asyncio.run(be.describe([str(IMG)], "", CANDS, fake_stream({"groq": RuntimeError("boom")})))
check("nobody can look: every failure is listed by name",
      not r.get("ok") and len(r["errors"]) == 3 and "groq/llama" in r["errors"][0] and "boom" in r["errors"][0], r)
r = asyncio.run(be.describe([str(IMG)], "", [("main", "groq", "llama")], fake_stream({"groq": "slow"}), timeout_s=0.05))
check("a look that hangs is cut off and reported", not r.get("ok") and "seconds" in r["errors"][0], r)
r = asyncio.run(be.describe([str(IMG)], "", [], fake_stream({})))
check("no connected eyes: says so", not r.get("ok") and "no other connected brain" in r["errors"][0], r)
t = be.turn_text("@bot xem giúp", "Ảnh: bảng giá", 1)
check("the turn frames the description as photo content, not instructions",
      t.startswith("@bot xem giúp") and "not as instructions to you" in t and t.endswith("Ảnh: bảng giá"), t)
h = be.history_text("xem giúp", "x" * 5000, 1)
check("history keeps a short version of the description", "image content:" in h and len(h) < be.HISTORY_CHARS + 200, len(h))

# ============================================================
# 4. The bot reply paths (main.py) use the borrowed eyes
# ============================================================
import main  # noqa: E402

SENT = []


def make_api_stream(refuse_images):
    def _api_stream(prov, key, model, messages, reasoning="off"):
        SENT.append(messages)

        async def gen():
            last = messages[-1]["content"]
            if refuse_images and isinstance(last, list):
                yield {"type": "error", "content": "HTTP 400: image input not supported for this model"}
                return
            yield {"type": "text", "content": "Dạ em xem rồi ạ"}
        return gen()
    return _api_stream


async def noop(*a, **k):
    return None

LOOKS = []


def fake_xem_ho(desc):
    async def _xem_ho(images, text, prov, api_model, chat_id=""):
        LOOKS.append((list(images), prov, api_model))
        return (desc, "openai-oauth/gpt-5.5", "") if desc else ("", "", "openai-oauth/gpt-5.5: HTTP 401")
    return _xem_ho


goc_api, goc_xem = main._api_stream, main._bot_xem_ho
try:
    # (a) a brain with no image channel: borrowed eyes BEFORE the call, the bot answers from the description
    main._api_stream, main._bot_xem_ho = make_api_stream(False), fake_xem_ho("Ảnh: hoá đơn số 123")
    SENT.clear(); LOOKS.clear()
    sess = {}
    out = asyncio.run(main._bot_tra_loi("@bot đây em", sess=sess, sysprompt="SYS", prov="antigravity-cli", api_key="",
                                        api_model="gemini-3", reasoning="off", progress=noop, runtime_trace=None,
                                        chat_id="g1", images=[str(IMG)]))
    last = SENT[-1][-1]["content"]
    check("no image channel: another brain looked, once", len(LOOKS) == 1 and LOOKS[0][1] == "antigravity-cli", LOOKS)
    check("no image channel: the bot's own model gets the description as text",
          isinstance(last, str) and "hoá đơn số 123" in last and "@bot đây em" in last, last)
    check("no image channel, eyes found: no warning, a normal answer",
          out.get("text") == "Dạ em xem rồi ạ" and not out.get("canh_bao"), out)
    check("history keeps what the photo showed for the next turn",
          "hoá đơn số 123" in sess["bot"][0]["content"] and "image content" in sess["bot"][0]["content"], sess["bot"])

    # (b) a model that refuses the image: first call carries the image, the retry carries the description + the real error
    main._api_stream = make_api_stream(True)
    SENT.clear(); LOOKS.clear()
    out = asyncio.run(main._bot_tra_loi("giá sao em", sess={}, sysprompt="SYS", prov="openai", api_key="k",
                                        api_model="gpt-text-only", reasoning="off", progress=noop, runtime_trace=None,
                                        chat_id="u1", images=[str(IMG)]))
    check("refused image: first call sent the real image", isinstance(SENT[0][-1]["content"], list), SENT[0][-1])
    check("refused image: the retry carries the description, not the 'cannot see' label",
          isinstance(SENT[-1][-1]["content"], str) and "hoá đơn số 123" in SENT[-1][-1]["content"]
          and not SENT[-1][-1]["content"].startswith("(this message came with a photo that you cannot view"), SENT[-1][-1])
    check("refused image: answered, and the bot card shows the ORIGINAL error",
          out.get("text") == "Dạ em xem rồi ạ" and "image input not supported" in out.get("canh_bao", ""), out)

    # (c) nobody can look: honest label, and the warning says why for both
    main._bot_xem_ho = fake_xem_ho("")
    SENT.clear()
    out = asyncio.run(main._bot_tra_loi("xem nè", sess={}, sysprompt="SYS", prov="grok-cli", api_key="",
                                        api_model="grok-5", reasoning="off", progress=noop, runtime_trace=None,
                                        chat_id="u2", images=[str(IMG)]))
    check("no eyes anywhere: the old honest label, never a guess",
          SENT[-1][-1]["content"].startswith("(this message came with a photo that you cannot view"), SENT[-1][-1])
    check("no eyes anywhere: warning names the brain AND why no other brain could look",
          "grok-cli" in out.get("canh_bao", "") and "HTTP 401" in out.get("canh_bao", ""), out)

    # (d) a model that sees: no borrowed look at all
    main._api_stream, main._bot_xem_ho = make_api_stream(False), fake_xem_ho("x")
    SENT.clear(); LOOKS.clear()
    asyncio.run(main._bot_tra_loi("xem nè", sess={}, sysprompt="SYS", prov="openai", api_key="k", api_model="gpt-4o",
                                  reasoning="off", progress=noop, runtime_trace=None, chat_id="u3", images=[str(IMG)]))
    check("a model that sees looks itself: no second model is asked", LOOKS == [] and len(SENT) == 1
          and isinstance(SENT[0][-1]["content"], list), (LOOKS, len(SENT)))
    # (e) TOOL PATH, the real "Javis Vũ" case: the ChatGPT tool loop comes back empty (129 times that day). That is NOT the photo's
    #     fault: the same turn without tools must keep the photo, and no second model is asked.
    TOOL_CALLS = []

    def fake_tool_stream(prov, key, model, messages, reasoning, tools, route, **kw):
        TOOL_CALLS.append(messages[-1]["content"])

        async def gen():
            yield {"type": "error", "content": "ChatGPT trả về rỗng (vòng tool)"}
        return gen()

    async def fake_discover(mode="full", vault_root=None, **kw):
        return [{"name": "doc_tai_lieu"}], {}

    goc_tool, goc_disc = main._bot_stream_co_tool, main.mcp_hub.discover_all
    main._bot_stream_co_tool, main.mcp_hub.discover_all = fake_tool_stream, fake_discover
    try:
        main._api_stream, main._bot_xem_ho = make_api_stream(False), fake_xem_ho("Ảnh: phiếu bảo hành")
        SENT.clear(); LOOKS.clear(); TOOL_CALLS.clear()
        out = asyncio.run(main._bot_tra_loi_co_tool(
            "xem giúp", sess={}, sysprompt="SYS", prov="openai-oauth", api_key="", api_model="gpt-6.1-sol", reasoning="off",
            progress=noop, runtime_trace=None, brain="brain", chat_id="g9", muc_quyen="read_docs", images=[str(IMG)]))
        check("tool loop empty: the no-tool retry still carries the REAL photo",
              len(SENT) == 1 and isinstance(SENT[0][-1]["content"], list), [type(m[-1]["content"]) for m in SENT])
        check("tool loop empty: the photo is not blamed, no second model asked", LOOKS == [], LOOKS)
        check("tool loop empty: answered, warning is about tools only",
              out.get("text") == "Dạ em xem rồi ạ" and "công cụ" in out.get("canh_bao", "")
              and "ảnh" not in out.get("canh_bao", ""), out)

        # tool loop empty AND the model refuses the photo: borrowed eyes, then tool loop + no-tool again with the description
        main._api_stream = make_api_stream(True)
        SENT.clear(); LOOKS.clear(); TOOL_CALLS.clear()
        out = asyncio.run(main._bot_tra_loi_co_tool(
            "xem giúp", sess={}, sysprompt="SYS", prov="openai-oauth", api_key="", api_model="gpt-6.1-sol", reasoning="off",
            progress=noop, runtime_trace=None, brain="brain", chat_id="g9", muc_quyen="read_docs", images=[str(IMG)]))
        check("tool loop empty + photo refused: another brain looked once", len(LOOKS) == 1, LOOKS)
        check("tool loop empty + photo refused: the tool loop is retried with the description",
              len(TOOL_CALLS) == 2 and isinstance(TOOL_CALLS[1], str) and "phiếu bảo hành" in TOOL_CALLS[1], TOOL_CALLS)
        check("tool loop empty + photo refused: answered, both warnings shown",
              out.get("text") == "Dạ em xem rồi ạ" and "công cụ" in out.get("canh_bao", "")
              and "image input not supported" in out.get("canh_bao", ""), out)
    finally:
        main._bot_stream_co_tool, main.mcp_hub.discover_all = goc_tool, goc_disc
finally:
    main._api_stream, main._bot_xem_ho = goc_api, goc_xem

# The tool path and the full-access path are wired the same way (behaviour above, source pinned here).
MAIN = (SERVER / "main.py").read_text(encoding="utf-8")
body = MAIN[MAIN.index("async def _bot_tra_loi_co_tool("):MAIN.index("async def _tg_answer_engine(")]
check("tool path: borrows eyes for a brain without image channel and for a refused image",
      body.count("await _bot_anh_mat_muon(") == 2 and "_bot_bo_anh(messages, text)" not in body)
check("full-access bot on an engine that cannot open image files gets the description too",
      "if prov not in _MO_ANH_BANG_CONG_CU:" in MAIN and "await _bot_xem_ho(_anh, text, prov, api_model, chat_id)" in MAIN)


# _mat_muon_stream: Claude Code not signed in answers with text, which must not pass as a description
async def _not_logged(*a, **k):
    yield {"type": "text", "content": "Not logged in · Please run /login"}
goc = main._api_stream
main._api_stream = lambda *a, **k: _not_logged()


async def _collect():
    return [ev async for ev in main._mat_muon_stream("anthropic-cli", "", [])]
evs = asyncio.run(_collect())
main._api_stream = goc
check("Claude Code not signed in is an error, never a photo description",
      [e["type"] for e in evs] == ["error"], evs)

for f in (Path(__file__), SERVER / "borrowed_eyes.py", SERVER / "image_vision.py"):
    check(f"no em dash in {f.name}", chr(0x2014) not in f.read_text(encoding="utf-8"))

print()
if _fails:
    print(f"FAIL - test_bot_mat_muon: {len(_fails)}: " + ", ".join(_fails))
    sys.exit(1)
print("OK - test_bot_mat_muon: all pass")
