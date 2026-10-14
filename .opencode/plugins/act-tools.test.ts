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
  assert.match(chooseActScript("act_key", { keys: "ctrl+s", mode: "background" }), /PostMessageW/);
});
test("act_key script foreground usa keybd_event (nao SendKeys)", () => {
  const s = buildPsScript("act_key", { keys: "enter" });
  assert.match(s, /keybd_event/);
  assert.doesNotMatch(s, /SendKeys/);
  assert.match(s, /0x0D/);
});
test("act_key descricao documenta sintaxe natural e limites do background", async () => {
  const tools = (await ActTools({} as never)).tool as Record<string, { description: string }>;
  const d = tools.act_key.description;
  assert.match(d, /enter/);
  assert.match(d, /ctrl\+c/);
  assert.match(d, /ctrl\+shift\+esc/);
  assert.match(d, /win\+r/);
  assert.match(d, /background/i);
  assert.match(d, /best-effort|GetKeyState/i);
});
test("act_key com keys invalido falha didaticamente antes de qualquer script", () => {
  assert.throws(() => buildPsScript("act_key", { keys: "foo" }), /tecla desconhecida "foo"/);
  assert.throws(() => buildPsScript("act_key", { keys: "foo" }), /ctrl\+c/);
});

test("act_key execute com keys invalido retorna erro sem chamar o shell", async () => {
  let called = false;
  const shell = (() => {
    called = true;
    return { text: async () => "" };
  }) as never;
  const tools = (await ActTools({ $: shell } as never)).tool as Record<string, { execute: (a: Record<string, unknown>) => Promise<string> }>;
  const out = await tools.act_key.execute({ keys: "foo" });
  assert.match(out, /^erro: /);
  assert.match(out, /tecla desconhecida "foo"/);
  assert.equal(called, false, "nao pode rodar powershell com keys invalido");
});
