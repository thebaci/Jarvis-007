"""Plugin bundled: tạo ảnh bằng gói ChatGPT (OAuth) cho MỌI engine.

Đăng ký tool javis_generate_image, gọi image_gen.generate_chatgpt
(Codex Responses + tool image_generation) bằng chính gói ChatGPT đã đăng nhập.
Bất kỳ engine nào (Claude Code/Codex/API) khi user bảo "tạo ảnh ..." đều gọi được tool này.

- min_mode=safe: coi như thao tác GHI (tạo file + dùng quota) → chặn ở chế độ suggest.
- check_fn: chưa kết nối ChatGPT → tool báo rõ cách bật, không lỗi khó hiểu.

Tool thứ hai javis_describe_image (0.73.0) là đôi MẮT cho engine không tự xem được ảnh: hub chỉ
chuyển chữ và sáu engine API không gửi ảnh, nên ChatGPT nhìn ảnh trong brain rồi tả lại bằng chữ
(xem server/image_vision.py). Chỉ đọc nên min_mode=readonly.
"""
from __future__ import annotations

import image_gen
import image_vision
import openai_oauth


def register(ctx):
    def _check():
        try:
            if not openai_oauth.status().get("connected"):
                return ("ChatGPT is not connected (OAuth). Sign in to ChatGPT on the Models page and try again - "
                        "image generation uses your ChatGPT plan itself, no API key needed.")
        except Exception as e:
            return f"Could not check the ChatGPT connection: {e}"
        return None

    async def _gen(args, cctx):
        args = args or {}
        prompt = str(args.get("prompt") or "").strip()
        if not prompt:
            return "ERROR: missing 'prompt' (description of the image to create)."
        aspect = str(args.get("aspect_ratio") or "square")
        quality = str(args.get("quality") or "medium")
        # `images`: đường dẫn ảnh MẪU trong brain. Nhận cả chuỗi một ảnh lẫn mảng nhiều ảnh -
        # engine nào cũng có lúc gửi kiểu này kiểu kia, ép một kiểu là thỉnh thoảng lại hỏng.
        raw = args.get("images") or args.get("image") or []
        if isinstance(raw, str):
            raw = [raw]
        anh = [str(x).strip() for x in raw if str(x or "").strip()]
        res = await image_gen.generate_chatgpt(prompt, aspect, quality,
                                               vault_root=cctx.vault_root, images=anh)
        if not res.get("ok"):
            return "ERROR: " + str(res.get("error") or "image generation failed")
        rel = res["rel_path"]
        theo = f" (built from the {res.get('refs') or 0} reference image(s) you sent)" if res.get("refs") else ""
        return (f"Image created ({res['size']}, quality {res['quality']}){theo}, saved at {rel}. "
                f"EMBED it right away in your answer to the user with markdown syntax: "
                f"![{prompt[:40]}]({rel})")

    ctx.register_tool(
        name="javis_generate_image",
        description=("Create or EDIT IMAGES with the signed-in ChatGPT plan (no API key needed). Parameters: "
                     "prompt (description, required), images (list of REFERENCE image paths in the brain - "
                     "ChatGPT will SEE the real images to edit or build from, use it when the product, "
                     "label, faces or layout must be kept exactly), aspect_ratio (square|landscape|portrait), "
                     "quality (low|medium|high). When the user gives an image and says 'build it like this image', "
                     "you MUST pass that image path in images, do not describe the image in words. "
                     "After calling, EMBED the returned ![](path) in your answer."),
        handler=_gen, min_mode="safe", check_fn=_check,
        schema={"type": "object", "properties": {
            "prompt": {"type": "string", "description": "Description of the image to create (the clearer the better)"},
            "aspect_ratio": {"type": "string", "enum": ["square", "landscape", "portrait"],
                             "description": "Image aspect ratio, default square"},
            "quality": {"type": "string", "enum": ["low", "medium", "high"],
                        "description": "Quality/level of detail, default medium"},
            "images": {"type": "array", "items": {"type": "string"},
                       "description": ("Path of a REFERENCE image in the brain (e.g. attachments/bottle.jpg) for "
                                       "ChatGPT to look at and build from. Up to 4 images, each under 12MB.")}},
            "required": ["prompt"]},
    )

    async def _describe(args, cctx):
        args = args or {}
        raw = args.get("images") or args.get("image") or args.get("path") or []
        if isinstance(raw, str):
            raw = [raw]
        anh = [str(x).strip() for x in raw if str(x or "").strip()]
        if not anh:
            return "ERROR: missing 'images' (image path in the brain, e.g. attachments/abc.jpg)."
        res = await image_vision.describe_images(anh, str(args.get("question") or ""),
                                                 vault_root=cctx.vault_root)
        if not res.get("ok"):
            return "ERROR: " + str(res.get("error") or "could not view the image")
        return f"ChatGPT viewed {res['count']} image(s):\n{res['text']}"

    ctx.register_tool(
        name="javis_describe_image",
        description=("VIEW IMAGES in the brain: ChatGPT (the signed-in plan) looks at the real image and describes it in words, copying "
                     "any text/numbers in the image verbatim. Use it when you CANNOT open the image file yourself (the file-read tool only reads text, it does not show "
                     "images). Parameters: images (image paths in the brain, up to 4), question (what to look for in the image, optional)."),
        handler=_describe, min_mode="readonly", check_fn=_check,
        schema={"type": "object", "properties": {
            "images": {"type": "array", "items": {"type": "string"},
                       "description": "Image path in the brain (e.g. attachments/zalo/abc.jpg). Up to 4 images."},
            "question": {"type": "string", "description": "What to find out from the image (optional), e.g. 'total amount on the invoice'"}},
            "required": ["images"]},
    )
