"""Jarvis 007: product name from one setting, Vietnam-only channels hidden by default."""
import os
import sys
import tempfile

os.environ["JAVIS_UPSTREAM_DEFAULTS"] = "0"
os.environ["JAVIS_REQUIRE_LOGIN"] = "0"
os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="j007-brand-")
from _paths import DASHBOARD  # noqa: E402

import config  # noqa: E402
import main  # noqa: E402
import mcp_catalog  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

errors = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        errors.append(name)


c = TestClient(main.app, base_url="http://127.0.0.1:7777")

check("default brand is Jarvis 007", config.brand_name() == "Jarvis 007")
h = c.get("/").text
check("page title uses the brand", "<title>Jarvis 007</title>" in h)
check("home-screen title uses the brand", 'name="apple-mobile-web-app-title" content="Jarvis 007"' in h)
check("brand handed to i18n before it loads", 0 <= h.find("window.JAVIS_BRAND") < h.find("i18n/index.js"))
check("manifest link points at the branded manifest", "/app-manifest.json?v=" in h)
m = c.get("/app-manifest.json")
check("branded manifest served without login", m.status_code == 200 and m.json().get("name") == "Jarvis 007")

cfg = config.read_settings()
cfg.setdefault("branding", {})["name"] = "<b>Friday</b>"
config.write_settings(cfg)
h = c.get("/").text
check("custom brand name is HTML-escaped in the shell", "&lt;b&gt;Friday&lt;/b&gt;" in h and "<b>Friday</b></span>" not in h)
check("custom brand name is script-safe", '"\\u003cb>Friday\\u003c/b>"' in h)

ids = {x["id"] for x in mcp_catalog.public_catalog()}
check("Zalo hidden from the connection store", "zalo" not in ids)
check("Botcake hidden from the connection store", "botcake" not in ids)
check("page tells the dashboard to hide the Zalo channel tab", "window.JAVIS_HIDE_VN=true" in h)
js = (DASHBOARD / "console.js").read_text(encoding="utf-8")
check("Admin channels filter drops Zalo when hidden", 'window.JAVIS_HIDE_VN && c.key === "zalo"' in js)

cfg = config.read_settings()
cfg.setdefault("regional", {})["vn_channels"] = True
config.write_settings(cfg)
ids = {x["id"] for x in mcp_catalog.public_catalog()}
check("regional.vn_channels=true brings Zalo back", "zalo" in ids and "botcake" in ids)
check("and the Zalo tab", "JAVIS_HIDE_VN" not in c.get("/").text)

if errors:
    print(f"FAIL - test_jarvis007_brand_channels: {len(errors)} errors: {errors}")
    sys.exit(1)
print("test_jarvis007_brand_channels: all green")
