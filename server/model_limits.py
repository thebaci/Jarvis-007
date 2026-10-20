"""model_limits.py - Bộ hạn mức GỢI Ý theo provider/model, để khai quota profile cho canary.

Vì sao module này tồn tại: cả adaptive runtime dựng ra để cứu model bị siết TPM, nhưng nó
fail-closed khi không biết hạn mức - `quota_profiles` mặc định rỗng nên mọi task rơi về
legacy. Nghĩa là cỗ máy cứu Groq, khi gặp đúng Groq, không làm gì cả vì không ai bảo nó
Groq bị giới hạn bao nhiêu. Trước module này, cách duy nhất để khai là gõ tay JSON lồng ba
tầng vào settings.json.

RANH GIỚI RÕ RÀNG, đọc trước khi thêm mục:

- Đây là GỢI Ý, không phải sự thật. Hạn mức thật phụ thuộc gói cước của TỪNG tài khoản và
  nhà cung cấp đổi lúc nào cũng được. Mọi mục đều mang `verify: True` và giao diện phải nói
  rõ là con số cần đối chiếu, không được trình bày như thể đã biết chắc.
- KHÔNG hardcode vào `_DEFAULT` của config. Thiết kế cố ý bắt người vận hành khai một cách
  có ý thức; module này chỉ rút ngắn thao tác khai, không khai hộ.
- Thà THIẾU còn hơn SAI. Không có mục cho provider nào thì trả rỗng, người vận hành tự
  điền. Một con số bịa cao hơn thực tế còn tệ hơn không có số, vì nó làm admission cho qua
  đúng cái request lẽ ra phải chặn.

Hình dạng mỗi mục phải khớp thứ `CanaryPolicy.from_settings` đọc được (xem
`fast_path_runtime.QuotaRule`). Sai một tên trường là rule bị bỏ qua trong IM LẶNG và
`quota_profiles` tuy có phần tử vẫn sinh ra 0 rule. Có test khoá chuyện đó.
"""
from __future__ import annotations

import fnmatch

# Nguồn: tài liệu hạn mức công khai của từng nhà cung cấp, ghi lại kèm ngày tra để lần sau
# còn biết con số cũ tới mức nào.
#
# reserved_output_tokens: chỗ chừa cho câu trả lời. Đặt rộng tay vì tính thiếu thì request
# vượt hạn mức đúng lúc model trả lời dài, mà đó lại là lúc khó tái hiện nhất.
KNOWN_LIMITS: tuple[dict, ...] = (
    {
        "id": "groq-free-llama-3.3-70b",
        "provider": "groq",
        "model_pattern": "llama-3.3-70b*",
        "rolling_tpm": 12000,
        "context_window": 131072,
        "reserved_output_tokens": 2000,
        "window_seconds": 60,
        "note": "Groq free on_demand tier. This very limit blocked Jarvis 007 at 21,446 tokens.",
        "source": "Groq public rate limit documentation, checked on 2026-08-02",
        "verify": True,
    },
    {
        "id": "groq-free-qwen3-32b",
        "provider": "groq",
        "model_pattern": "qwen3-32b*",
        "rolling_tpm": 6000,
        "context_window": 131072,
        "reserved_output_tokens": 2000,
        "window_seconds": 60,
        "note": "A smaller model does NOT mean a wider limit - TPM and the context window are "
                "two different limits.",
        "source": "Groq public rate limit documentation, checked on 2026-08-02",
        "verify": True,
    },
    {
        "id": "groq-free-gpt-oss-120b",
        "provider": "groq",
        "model_pattern": "*gpt-oss-120b*",
        "rolling_tpm": 8000,
        "context_window": 131072,
        "reserved_output_tokens": 2000,
        "window_seconds": 60,
        "source": "Groq public rate limit documentation, checked on 2026-08-02",
        "verify": True,
    },
)


def suggest_profiles(provider: str, model: str = "") -> list[dict]:
    """Các mục gợi ý khớp provider (và model nếu có nêu). Rỗng nghĩa là chưa biết.

    Rỗng KHÔNG phải lỗi: nó có nghĩa là người vận hành phải tự khai, và đó là trạng thái
    đúng cho mọi provider chưa được tra hạn mức."""
    prov = (provider or "").strip().lower()
    if not prov:
        return []
    out = []
    for item in KNOWN_LIMITS:
        if item["provider"] != prov:
            continue
        if model and not fnmatch.fnmatch(str(model).strip().lower(),
                                         item["model_pattern"].lower()):
            continue
        out.append(dict(item))
    return out


def as_quota_profile(item: dict) -> dict:
    """Rút mục gợi ý về đúng các trường `CanaryPolicy.from_settings` đọc.

    Bỏ `note`/`source`/`verify` vì chúng là ghi chú cho người, không phải cấu hình. Giữ lại
    thì chúng đi thẳng vào settings.json và lần sau ai đọc sẽ tưởng là trường có ý nghĩa."""
    return {
        "id": item["id"],
        "provider": item["provider"],
        "model_pattern": item["model_pattern"],
        "rolling_tpm": int(item["rolling_tpm"]),
        "context_window": int(item["context_window"]),
        "reserved_output_tokens": int(item["reserved_output_tokens"]),
        "window_seconds": int(item.get("window_seconds") or 60),
    }


def known_providers() -> list[str]:
    return sorted({item["provider"] for item in KNOWN_LIMITS})


def fits_within(provider: str, model: str, needed_tokens: int) -> bool | None:
    """Provider/model này có chứa nổi `needed_tokens` trong một cửa sổ TPM không?

    Trả None nghĩa là CHƯA BIẾT (không có mục nào khớp). None khác False: chưa biết thì
    không được kết luận là chặn, cũng không được kết luận là qua."""
    matches = suggest_profiles(provider, model)
    if not matches:
        return None
    # Khớp nhiều mục thì lấy mục rộng rãi nhất - hạn mức thật của tài khoản chỉ có thể
    # cao hơn hoặc bằng con số công khai của gói thấp nhất.
    return max(int(m["rolling_tpm"]) for m in matches) >= max(0, int(needed_tokens or 0))


def blocked_hint(provider: str, model: str, needed_tokens: int,
                 configured_providers=()) -> str:
    """Câu giải thích cho người dùng khi request bị chặn vì hạn mức, kèm lối ra.

    Chỉ nêu provider mà người dùng ĐÃ cấu hình và ta CHƯA biết là bị siết. Không quảng cáo
    provider họ không có, và không hứa provider khác chắc chắn chạy được - ta chỉ biết là
    chưa có bằng chứng nó bị chặn."""
    matches = suggest_profiles(provider, model)
    limit = max((int(m["rolling_tpm"]) for m in matches), default=0)
    parts = []
    if limit:
        parts.append(f"This turn needs about {int(needed_tokens):,} tokens, "
                     f"while {provider} limits you to {limit:,} tokens per minute.")
    else:
        parts.append(f"This turn needs about {int(needed_tokens):,} tokens, "
                     f"which exceeds the limit declared for {provider}.")
    others = [p for p in (configured_providers or ())
              if str(p).strip().lower() != (provider or "").strip().lower()
              and fits_within(str(p), "", needed_tokens) is not False]
    if others:
        parts.append("You can switch to " + ", ".join(sorted(set(others)))
                     + " (not known to be throttled at this level).")
    parts.append("Or shorten the request, or wait for the one-minute window to pass.")
    return " ".join(parts)


# Nhãn người-đọc-được cho các engine chạy bằng gói thuê bao.
SUBSCRIPTION_LABEL = {
    "claude-code": "Claude plan (Claude Code)",
    "codex": "ChatGPT plan (Codex)",
    "antigravity-cli": "Google plan (Antigravity CLI)",
    "grok-cli": "xAI plan (SuperGrok / X Premium+)",
}


def subscription_blocked_hint(limit, configured_providers=(), now=None) -> str:
    """Câu giải thích khi GÓI THUÊ BAO hết lượt, kèm lối ra.

    Khác hẳn `blocked_hint` ở trên: đây KHÔNG phải chuyện prompt quá to. Cửa sổ thuê bao đếm
    lượt dùng theo giờ, nên rút gọn câu hỏi không giúp gì cả - nói "rút gọn yêu cầu" ở đây là
    chỉ sai đường. Hai lối ra thật chỉ có: chờ tới mốc reset, hoặc đổi sang bộ não khác.

    Không biết mốc reset thì NÓI LÀ KHÔNG BIẾT. Bịa một con giờ ra cho tròn câu là thứ khiến
    người dùng ngồi đợi nhầm.
    """
    import time as _time

    engine = getattr(limit, "engine", "") or ""
    label = SUBSCRIPTION_LABEL.get(engine, "the subscription plan in use")
    scope = getattr(limit, "scope", "") or ""
    parts = [f"The {label} has run out of usage" + (f" in the {scope} window." if scope else ".")]

    reset = float(getattr(limit, "reset_epoch", 0) or 0)
    ts = _time.time() if now is None else float(now)
    if reset > ts:
        con = int(reset - ts)
        gio, phut = con // 3600, (con % 3600) // 60
        khi_nao = _time.strftime("%H:%M", _time.localtime(reset))
        cho = f"{gio} h {phut} min" if gio else f"{phut} min"
        parts.append(f"It will be usable again in about {cho} (around {khi_nao}).")
    elif getattr(limit, "reset_text", ""):
        parts.append(f"The provider says: {limit.reset_text}.")
    else:
        parts.append("The provider does not say when it resets, so Jarvis 007 does not know either.")

    others = sorted({str(p) for p in (configured_providers or ()) if str(p).strip()})
    if others:
        parts.append("While waiting, switch temporarily to " + ", ".join(others)
                     + " on the Models page - the conversation stays as it is.")
    else:
        parts.append("No other brain is connected to run in the meantime; add an API key on the Models page "
                     "and work can continue at times like this.")
    parts.append("Shortening the question does NOT help here - this limit counts usage per hour, "
                 "not length.")
    return " ".join(parts)
