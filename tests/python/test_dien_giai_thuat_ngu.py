"""Bong bóng hiện đúng thuật ngữ tiếng Anh; bộ não chính không giải thích chuyện nghe nhầm.

    python tests/run.py dien_giai_thuat_ngu

Vì sao file này tồn tại (0.64.72): chủ dự án 27/09 nói "tìm hiểu cho anh Workers for Platforms
của Cloudflare" và "KV của Cloudflare"; máy nghe chép "Quốc cơ ford plat form của clap Play",
"cave". Bộ não giọng viết lại đúng ở dòng JAVIS_NGHE nhưng rào voice_brain.safe_transcript_rewrite
chặn (cụm 5 tiếng vượt trần 4; "KV" quá ngắn; so mặt chữ tiếng Anh với tiếng Việt), lượt quay
về câu gốc, bộ não chính trả lời mở đầu "Em hiểu 'cave' là KV..." còn bong bóng vẫn chữ sai.
Chủ dự án: "đáng nhẽ không cần giải thích mà có một bộ định tuyến điền đúng ngữ cảnh vào khung
chat luôn". Rào vẫn phải chặn mọi chỗ sửa đổi nghĩa như trước.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-diengiai-"))

import voice_brain as vb  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


NHAN = [
    ("tìm hiểu cho anh Quốc cơ ford plat form của clap Play",
     "tìm hiểu cho anh Workers for Platforms của Cloudflare"),
    ("giải thích cho anh về cave của clap Play", "giải thích cho anh về KV của Cloudflare"),
    ("cave là gì", "KV là gì"),
    ("vẫn không nhận ra huyết áp Action luôn", "vẫn không nhận ra GitHub Actions luôn"),
    ("anh hỏi về khít half action", "anh hỏi về GitHub Actions"),
    ("xin chào David", "xin chào Javis"),
    ("xem đơn trên pan cake", "xem đơn trên Pancake"),
]
for cu, moi in NHAN:
    check(f"nhận: {cu!r} -> {moi!r}", vb.safe_transcript_rewrite(cu, moi) == moi)

CHAN = [
    ("mở trang việc", "mở trang Webhook"),          # từng LỌT ở 0.64.68: so mặt chữ được 0,67
    ("mở trang kênh", "mở trang Canva"),
    ("mở lịch", "mở Slack"),
    ("trả lời khách đi", "trở thành khách đi"),
    ("Em phải trả lời vâng", "Em phải trở thành Vân"),
    ("không gửi nữa", "có gửi nữa"),
    ("xoá hết đơn hôm nay", "delete hết đơn hôm nay"),
    ("tắt quảng cáo đi", "bật quảng cáo đi"),
    ("chuyển năm triệu", "chuyển nam triệu"),
    ("gửi email cho sếp", "gửi Zalo cho sếp"),
    ("nhắn cho Lan", "nhắn cho Lane"),
    ("đừng gửi", "don send"),
]
for cu, moi in CHAN:
    check(f"chặn: {cu!r} -> {moi!r}", vb.safe_transcript_rewrite(cu, moi) == cu)

# Trần số chữ: một câu viết lại gần hết bằng tiếng Anh vẫn bị chặn.
check("chặn: viết lại gần hết câu",
      vb.safe_transcript_rewrite("anh đi chợ mua rau về nấu cơm", "and she chose more roll voter comb") ==
      "anh đi chợ mua rau về nấu cơm")

# ---- Đường lùi: bộ não chính nhận câu gốc KÈM lời dặn, không kèm câu bị chặn ----
g = vb.GHI_CHU_CAU_NGHE
check("lời dặn: không giải thích chuyện nghe nhầm", "do NOT explain" in g and "em hiểu X là Y" in g)
check("lời dặn: việc ra ngoài vẫn hỏi xác nhận", "confirmation" in g)
check("lời dặn: không có dấu gạch dài", chr(0x2014) not in g)
src = (SERVER / "main.py").read_text(encoding="utf-8")
khoi = src[src.index("async def _giu_cau_goc():"):src.index("async def _ap_dien_giai(")]
check("main: _giu_cau_goc gửi câu GỐC kèm GHI_CHU_CAU_NGHE cho bộ não chính",
      "original_message + \"\\n\\n\" + voice_brain.GHI_CHU_CAU_NGHE" in khoi)
check("main: _giu_cau_goc KHÔNG đưa câu bộ não giọng hiểu (có thể đổi nghĩa) cho bộ não chính",
      "nghe" not in khoi.replace("câu vừa nghe", "").replace("nghe nhầm", "").replace("GHI_CHU_CAU_NGHE", ""))

if _fails:
    print("\nFAIL:", len(_fails), _fails)
    raise SystemExit(1)
print("\nOK - dien_giai_thuat_ngu")
