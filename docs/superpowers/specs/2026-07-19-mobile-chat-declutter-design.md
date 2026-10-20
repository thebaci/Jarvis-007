# Gọn khung chat trên điện thoại - Thiết kế

Ngày: 2026-07-19
Trạng thái: đã duyệt thiết kế (mockup), chuẩn bị lập kế hoạch.

## Mục tiêu

Trên điện thoại, khung chat của Jarvis 007 đang rối và ô nhập bị bé. Làm lại theo hướng "chat là chính, gọn tối đa" (đã chốt với chủ dự án): ô nhập nở to, các thứ phụ gom vào một header mảnh và một ngăn kéo.

Phạm vi: CHỈ giao diện điện thoại (màn hẹp, breakpoint 860px - đúng chỗ app đã coi là mobile). Bản máy tính (>860px) GIỮ NGUYÊN, không đụng.

## Hiện trạng (vì sao rối)

Ở màn hẹp (`console.css` @media max-width:860px), đáy màn hình xếp chồng ba hàng điều khiển + thanh trình duyệt điện thoại:
1. `.model-bar` (index.html:262): chip chọn model (`#mbOpen`) + dải `.sysbar` (HỆ THỐNG: trạng thái Claude/TTS + MCP). Một hàng.
2. `.hud-voice` (index.html:285): ô nhập `#chatInput` (textarea rows=1, flex:1) NHÉT CHUNG hàng với 5 nút - mic `.mic-big` (46px), đính kèm `#attachBtn`, loa `#ttsToggleBar`, dừng `#stopBtn`, gửi `#sendBtn`. Nút chiếm gần hết bề ngang nên ô gõ còn một mẩu -> đây là thủ phạm chính "ô nhập bé".
3. `.rail` (nav, index.html:315): ở mobile thành thanh ĐÁY 56px (`console.css:324-338`), cuộn ngang các `.rail-item` (Workflows, Plugins, Việc, Việc định kỳ, Kết nối, Kênh, Mode...).

Header trên (`.hud-top`, 46px ở mobile) cũng đông (brand + chọn brain + số liệu + đổi tông + Studio + cài đặt + loa + reset).

## Thiết kế (đã duyệt qua mockup)

Ba khối, đều là thay đổi mobile-only (thêm rule trong @media + ít JS). Tận dụng lại các thành phần sẵn có (bảng chọn model `#mbPop`, rail nav Alpine `$store.nav`), không viết mới.

### Khối 1 - Header mảnh (thay hàng model + thanh đáy)

Ở mobile, `.hud-top` rút gọn còn ba thứ, căn đều một hàng:
- Trái: nút **☰** (`#navToggle`, mobile-only) mở/đóng ngăn kéo điều hướng (Khối 2).
- Giữa: **chip model** "Jarvis 007 · <model> ▾" - bấm mở đúng `#mbPop` sẵn có (đổi model + effort + engine). Chốt cách làm: JS DỜI chính nút `#mbOpen` (và `#mbPop`) sẵn có vào header khi ở mobile, trả về `.model-bar` khi về desktop (theo dõi bằng matchMedia). Tái dùng nút gốc nên chữ model (`#mbModelTxt`) do `model-picker.js` cập nhật vẫn đúng, không phải đồng bộ bản sao.
- Phải: nút **＋** (hội thoại mới) - dùng lại handler của `#resetBtn` (reset = hội thoại mới).

Các nút cũ của `.hud-top` (brand, chọn brain, số liệu, đổi tông, Studio, cài đặt, loa, reset) ở mobile ẩn khỏi header và đưa vào ngăn kéo (Khối 2, phần "Hệ thống"). `.model-bar` cũ (nguyên hàng) ẩn ở mobile; riêng `.sysbar` (HỆ THỐNG/MCP - chỉ là thông tin trạng thái) ẩn hẳn ở mobile.

### Khối 2 - Ngăn kéo điều hướng (thay thanh đáy rail)

Ở mobile, `.rail` KHÔNG còn là thanh đáy. Thay bằng ngăn kéo trượt từ TRÁI:
- Mặc định ẩn (trượt khuất trái). Bấm ☰ -> trượt vào, kèm nền mờ (backdrop) phủ chat.
- Bấm backdrop / Esc / chọn một mục -> đóng.
- Nội dung ngăn kéo: giữ nguyên `.rail-nav` (Workflows, Plugins, Việc...) + THÊM một mục "Hệ thống" gom các nút header cũ (chọn brain, Cài đặt, Đổi tông, Studio, Reset, bật/tắt loa). Hiện lại `.rail-top`/`.rail-foot` (brand + version) trong ngăn kéo cho ra dáng menu.
- Cơ chế: một cờ trạng thái mở (body class `nav-open` hoặc `$store.nav.drawer`) do ☰ bật/tắt; CSS mobile dịch `.rail` theo cờ. Không đụng hành vi desktop (desktop vẫn là cột trái + nút collapse cũ).

### Khối 3 - Ô nhập thành viên bo tròn lớn

Ở mobile, `.hud-voice` bọc thành một viên pill bo tròn:
- Bố cục trong pill: **＋ (đính kèm, `#attachBtn`)** trái | **`#chatInput`** chiếm gần hết bề ngang | **mic (`.mic-big` thu nhỏ ~34px)** | **nút gửi tròn (`#sendBtn`)** phải. Nút dừng `#stopBtn` chỉ hiện khi đang chạy (thay chỗ nút gửi), như hiện tại.
- `#chatInput`: min-height ~40px, tự cao lên khi gõ dài (max-height cao hơn hiện tại, vd 40vh), font 16px (chống iOS zoom).
- Nút loa trong bar (`#ttsToggleBar`) ẩn ở mobile (bật/tắt loa đã có trong ngăn kéo phần Hệ thống).
- Mic + gửi LUÔN hiện (Jarvis 007 dùng giọng nói nhiều); không làm swap mic/gửi để đơn giản.

## Không làm (ngoài phạm vi)

- Không đổi giao diện máy tính (>860px).
- Không làm swap nút mic/gửi theo nội dung.
- Không đổi logic chat/engine/model - chỉ dời chỗ nút và style lại.
- Không thêm màn cài đặt mới - tái dùng các nút/menu sẵn có.

## Xử lý lỗi / rìa

- Ngăn kéo mở: khoá cuộn nền (tránh cuộn chat sau lưng), backdrop bắt chạm để đóng.
- Chip model ở header dùng chung `#mbPop`: đảm bảo popover định vị đúng dưới header (không bị cắt), đóng khi chạm ngoài.
- Xoay ngang / tablet tới 860px: bố cục vẫn một cột, pill và header co giãn theo bề ngang.
- `#chatInput` cao lên không được che khuất chat (chat area co lại theo).
- Bàn phím ảo bật lên: pill bám đáy vùng nhìn, không bị bàn phím che (dùng layout an toàn, tránh position cố định gây nhảy).

## Kiểm thử

- `node --check` các file JS đụng tới (không có khung test UI tự động trong repo).
- Smoke tay ở bề ngang mobile: resize trình duyệt về ~375px (hoặc devtools mobile), kiểm: header chỉ còn ☰/chip model/＋; ☰ mở/đóng ngăn kéo + backdrop; chip model mở bảng chọn; ô nhập to, tự cao; không còn thanh đáy rail; không còn dải HỆ THỐNG. Bản desktop (>860px) không đổi.
- Chủ dự án smoke thật trên điện thoại (bản Hostinger) sau khi lên.

## File dự kiến đụng tới

- `dashboard/index.html` - thêm nút `#navToggle` (☰) + `#newChatBtn` (＋) cho header mobile; có thể thêm backdrop ngăn kéo; bọc `.hud-voice` nếu cần lớp pill.
- `dashboard/console.css` (+ `dashboard/style.css` cho `.hud-voice`/`.voice-input`) - toàn bộ rule mobile mới: header 3 nút, rail thành ngăn kéo trượt + backdrop, model-bar ẩn/sysbar ẩn, pill ô nhập.
- `dashboard/app.js` (hoặc `console.js`) - wiring: ☰ bật/tắt cờ ngăn kéo + backdrop + Esc; ＋ gọi reset hội thoại; đảm bảo chip model mobile mở `#mbPop`; chuyển nút Hệ thống vào ngăn kéo.
- Bump `?v=` của asset dashboard để nạp bản mới (như tiền lệ các lần sửa UI).
