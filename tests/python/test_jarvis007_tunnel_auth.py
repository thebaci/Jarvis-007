"""Jarvis 007: a tunnel on the same machine must not inherit the localhost login exemption.

cloudflared and Tailscale Serve connect to Javis from 127.0.0.1. The reminder endpoints were
exempt for any loopback client, so with a tunnel running anyone holding the URL could list or
create reminders without signing in. Only a direct local caller (no forwarding headers) is exempt.
"""
import os
import sys
import tempfile

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="j007-tunnel-")
from _paths import SERVER  # noqa: E402,F401

import config as cfgmod  # noqa: E402

cfg = cfgmod.read_settings()
h, s = cfgmod.hash_password("pw-123456")
cfg["auth"]["password_hash"], cfg["auth"]["salt"] = h, s
cfgmod.write_settings(cfg)

import main  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

errors = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        errors.append(name)


c = TestClient(main.app, client=("127.0.0.1", 50000))
check("direct local caller (the agent) still reaches /reminders", c.get("/reminders").status_code == 200)
for label, hdr in [
    ("cloudflared", {"cf-connecting-ip": "203.0.113.9", "x-forwarded-for": "203.0.113.9"}),
    ("Tailscale Serve", {"x-forwarded-for": "100.64.0.5", "x-forwarded-proto": "https", "tailscale-user-login": "a@b"}),
    ("generic proxy", {"x-real-ip": "198.51.100.7"}),
]:
    check(f"/reminders through {label} needs login", c.get("/reminders", headers=hdr).status_code == 401)
    check(f"POST /reminders/cancel through {label} needs login",
          c.post("/reminders/cancel", headers=hdr, json={"id": "x"}).status_code == 401)

if errors:
    print(f"FAIL - test_jarvis007_tunnel_auth: {len(errors)} errors: {errors}")
    sys.exit(1)
print("test_jarvis007_tunnel_auth: all green")
