"""Jarvis 007 fork defaults: drafts-only background work, login required, English-first locale.

Runs with JAVIS_UPSTREAM_DEFAULTS=0 (set before _paths, which would otherwise switch the
upstream defaults on for the rest of the suite).
"""
import os
import sys
import tempfile

os.environ["JAVIS_UPSTREAM_DEFAULTS"] = "0"
os.environ.pop("JAVIS_REQUIRE_LOGIN", None)
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="j007-"))

from _paths import SYSTEM  # noqa: E402

import importlib.util  # noqa: E402

import config  # noqa: E402
import reminders  # noqa: E402
import self_improve  # noqa: E402
import webhook_triggers  # noqa: E402

errors = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        errors.append(name)


spec = importlib.util.spec_from_file_location("javis_schedule_plugin", SYSTEM / "plugins" / "javis-schedule" / "plugin.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

check("upstream switch is off", config.UPSTREAM_DEFAULTS is False)
check("reminders default to drafts (auto)", reminders.MUC_QUYEN_MAC_DINH == "auto")
check("a reminder saved without a level runs at auto", reminders.muc_quyen_cua({}) == "auto")
check("an explicit full reminder keeps full", reminders.muc_quyen_cua({"muc_quyen": "full"}) == "full")
check("webhooks default to drafts (auto)", webhook_triggers.DEFAULT_LEVEL == "auto")
check("loops created from chat default to auto", plugin._LOOP_MODE_MAC_DINH == "auto")
check("loop files without a mode run at auto", self_improve.LOOP_MODE_DEFAULT == "auto")

check("login required on localhost", config.require_login() is True)
os.environ["JAVIS_REQUIRE_LOGIN"] = "0"
check("JAVIS_REQUIRE_LOGIN=0 still opts out", config.require_login() is False)
os.environ.pop("JAVIS_REQUIRE_LOGIN", None)

loc = config.DEFAULTS["locale"] if hasattr(config, "DEFAULTS") else None
if loc is None:
    for v in vars(config).values():
        if isinstance(v, dict) and isinstance(v.get("locale"), dict) and "ui_lang" in v["locale"]:
            loc = v["locale"]
            break
check("default locale found", loc is not None)
if loc:
    check("interface defaults to English", loc.get("ui_lang") == "en")
    check("timezone defaults to Asia/Bangkok", loc.get("tz") == "Asia/Bangkok")
    check("currency defaults to USD", loc.get("currency") == "USD")

if errors:
    print(f"FAIL - test_jarvis007_defaults: {len(errors)} errors: {errors}")
    sys.exit(1)
print("test_jarvis007_defaults: all green")
