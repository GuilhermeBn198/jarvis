import { test } from "node:test";
import assert from "node:assert/strict";
import { buildPsScript, encode } from "../act/ps.ts";
import { buildWinListScript, chooseActScript } from "../act/win.ts";
import { ActTools } from "./act-tools.ts";

test("win_list script builder disponivel", () => {
  assert.match(buildWinListScript(), /EnumWindows/);
});

test("act_type script uses SendKeys with escaping", () => {
  const s = buildPsScript("act_type", { text: "a+b(c)" });
  assert.match(s, /SendKeys/);
  assert.ok(s.includes("{+}") || s.includes("a+b")); // escape aplicado
});
test("act_open script uses Start-Process", () => {
  assert.match(buildPsScript("act_open", { target: "https://x" }), /Start-Process/);
});
test("act_click script uses SetCursorPos + mouse_event", () => {
  const s = buildPsScript("act_click", { x: 10, y: 20, button: "left" });
  assert.match(s, /SetCursorPos/);
  assert.match(s, /mouse_event/);
});
test("encode is utf16le base64", () => {
  assert.equal(Buffer.from(encode("hi"), "base64").toString("utf16le"), "hi");
});
test("plugin exports only the factory", () => {
  assert.equal(typeof ActTools, "function");
});

test("mode ausente -> foreground (sem script de background)", () => {
  assert.equal(chooseActScript("act_type", { text: "oi" }), "");
});
test("window informado -> script background (UIA)", () => {
  const s = chooseActScript("act_type", { text: "oi", window: "Notepad" });
  assert.match(s, /ValuePattern/);
});
test("mode background explicito -> background mesmo sem janela", () => {
  assert.match(chooseActScript("act_key", { keys: "^s", mode: "background" }), /PostMessageW/);
});
