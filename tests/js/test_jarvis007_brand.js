// Jarvis 007: the brand swap in i18n/index.js renames product text but never identifiers.
const fs = require("fs");
const path = require("path");
const src = fs.readFileSync(path.join(__dirname, "..", "..", "dashboard", "i18n", "index.js"), "utf8");
const m = src.match(/function _brand\(s\) \{[\s\S]*?\n  \}/);
const fails = [];
function check(name, cond) { console.log((cond ? "ok   " : "FAIL ") + name); if (!cond) fails.push(name); }
check("_brand() exists in i18n/index.js", !!m);
check("t() runs dictionary text through _brand()", /return _brand\(String\(val\)\)/.test(src));
const window = { JAVIS_BRAND: "Jarvis 007" };
const _brand = new Function("window", m[0] + "; return _brand;")(window);
check("Javis OS -> brand", _brand("Welcome to Javis OS") === "Welcome to Jarvis 007");
check("JAVIS OS -> brand", _brand("JAVIS OS") === "Jarvis 007");
check("Javis -> brand", _brand("Ask Javis anything") === "Ask Jarvis 007 anything");
check("possessive kept", _brand("Javis's memory") === "Jarvis 007's memory");
check("tool names untouched", _brand("use javis_task") === "use javis_task");
check("identifiers untouched", _brand("JavisI18n.setLang") === "JavisI18n.setLang");
window.JAVIS_BRAND = "";
check("no brand set -> unchanged", _brand("Ask Javis") === "Ask Javis");
if (fails.length) { console.log("FAIL " + fails.length); process.exit(1); }
console.log("test_jarvis007_brand: all green");
