"""Đo các điểm nóng chặn event loop. Chạy TRƯỚC và SAU giai đoạn 1.

    cd server && python bench_hotpath.py                  # brain mặc định
    cd server && python bench_hotpath.py "D:\\path\\brain" # brain cụ thể

Đây là thước đo của docs/superpowers/specs/2026-07-28-tai-cau-truc-server-design.md.
Mục tiêu nghiệm thu giai đoạn 1: build_system_prompt < 40ms, GET /brains < 10ms,
import main < 1400ms.

Lưu ý: KHÔNG phải test, không có pass/fail, nên tên file cố tình không bắt đầu bằng
test_ để vòng lặp CI không nhặt. Chạy tay khi cần số.

Chạy trên dữ liệu THẬT (không override JAVIS_STATE_DIR) thì số mới có nghĩa. Toàn bộ là
thao tác đọc, trừ build_system_prompt có gọi system_sync mirror skill sang .claude/skills -
đó đúng là việc app vẫn làm mỗi lượt chat, không phải tác dụng phụ do bench gây ra.
"""
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REPEAT = 5


def bench(label, fn, repeat=REPEAT):
    """Chạy 1 lần cho nóng cache OS rồi đo `repeat` lần, in trung vị."""
    try:
        fn()
    except Exception as e:
        print(f"  {label:<42} ERROR: {type(e).__name__}: {e}")
        return None
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        try:
            fn()
        except Exception as e:
            print(f"  {label:<42} ERROR: {type(e).__name__}: {e}")
            return None
        times.append((time.perf_counter() - t0) * 1000)
    med = statistics.median(times)
    print(f"  {label:<42} {med:8.1f} ms   (min {min(times):.1f} / max {max(times):.1f})")
    return med


def bench_import_main():
    """Đo riêng bằng tiến trình con, vì trong tiến trình này main đã nạp rồi.

    Trừ đi thời gian khởi động interpreter trần để ra chi phí import thật.
    """
    def run(code):
        t0 = time.perf_counter()
        subprocess.run([sys.executable, "-c", code], cwd=os.path.dirname(os.path.abspath(__file__)),
                       capture_output=True)
        return (time.perf_counter() - t0) * 1000

    base = statistics.median([run("pass") for _ in range(3)])
    full = statistics.median([run("import main") for _ in range(3)])
    print(f"  {'import main (minus interpreter start-up)':<42} {full - base:8.1f} ms"
          f"   (bare interpreter {base:.0f} ms)")
    return full - base


def main_():
    brain = sys.argv[1] if len(sys.argv) > 1 else "brain"

    print("Loading main...", flush=True)
    t0 = time.perf_counter()
    import main  # noqa: E402
    import plugins_host  # noqa: E402
    import skill_router  # noqa: E402
    import usage_index  # noqa: E402
    print(f"  (load time in this process: {(time.perf_counter() - t0) * 1000:.0f} ms)\n")

    root = main._brain_root(brain)
    print(f"Brain: {root}")
    try:
        n_md = sum(1 for _ in Path(root).rglob("*.md"))
        n_skill = len(skill_router.list_skills(root))
        print(f"Size: {n_md} .md files, {n_skill} skills\n")
    except Exception as e:
        print(f"Size: could not be counted ({e})\n")

    print("== System prompt hot path (runs every chat turn, every task, every reminder, every loop tick) ==")
    total = bench("build_system_prompt()", lambda: main.build_system_prompt(brain))
    bench("  skill_router.list_skills()", lambda: skill_router.list_skills(root))
    bench("  plugins_host.describe()", lambda: plugins_host.describe(str(root)))
    bench("  _gather_capabilities()", lambda: main._gather_capabilities(root))
    bench("  _javis_capability_summary()", lambda: main._javis_capability_summary(brain))
    bench("  _skill_router_block()", lambda: main._skill_router_block(brain, root))

    print("\n== Endpoints the dashboard calls at boot ==")
    # Đo LÕI THUẦN chứ không đo route handler: handler chỉ là vỏ `await to_thread(lõi)`, nên
    # gọi nó ở đây vừa cộng thêm chi phí dựng event loop + nhảy thread vào con số, vừa lặp lại
    # đúng lối gọi handler-như-hàm-thường mà 0.9.243 đã đi bịt (xem test handler_khong_goi_truc_tiep).
    bench("GET /brains (_list_brains_sync)", lambda: main._list_brains_sync())

    print("\n== Usage queries (since 0.9.238 they run in to_thread, no longer blocking the loop) ==")
    bench("usage_index.summary()", lambda: usage_index.summary())
    bench("usage_index.insights()", lambda: usage_index.insights())

    print("\n== Start-up cost ==")
    bench_import_main()

    print("\n== Comparison with the phase 1 baseline (brain of 623 md / 30 skills) ==")
    print("  The numbers below are the CPU/disk time of each function. For functions moved to")
    print("  to_thread this number is NO longer the time the event loop is blocked - that part")
    print("  is measured separately by heartbeat latency in test_brains_dem and test_kanban_snapshot.")
    print(f"  build_system_prompt   baseline 150.8 ms -> now {total:.1f} ms   (target < 60)"
          if total is not None else "  build_system_prompt: could not be measured")
    print("  GET /brains           baseline 136.1 ms  (now runs in a thread)")
    print("  import main           baseline 2,263 ms  (target < 1,400)")


if __name__ == "__main__":
    main_()
