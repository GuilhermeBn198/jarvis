import { test } from "node:test";
import assert from "node:assert/strict";
import { buildWinListScript, parseWinList, buildBackgroundTypeScript, parseActResult } from "./win.ts";

test("win_list script usa EnumWindows e nao rouba foco", () => {
  const s = buildWinListScript();
  assert.match(s, /EnumWindows/);
  assert.match(s, /GetWindowTextW/);
  assert.doesNotMatch(s, /SetForegroundWindow|SetCursorPos|mouse_event/);
});

test("parseWinList extrai JSON-lines e ignora ruido", () => {
  const out = [
    "PS> lixo",
    '{"hwnd":111,"title":"Sem título - Notepad","process":"notepad"}',
    '{"hwnd":222,"title":"Chrome","process":"chrome"}',
  ].join("\n");
  assert.deepEqual(parseWinList(out), [
    { hwnd: 111, title: "Sem título - Notepad", process: "notepad" },
    { hwnd: 222, title: "Chrome", process: "chrome" },
  ]);
});

test("parseWinList devolve vazio para saida sem json", () => {
  assert.deepEqual(parseWinList("erro qualquer"), []);
});

test("background type usa UIA ValuePattern e fallback PostMessage", () => {
  const s = buildBackgroundTypeScript({ text: "oi", window: "Notepad" });
  assert.match(s, /ValuePattern/);
  assert.match(s, /PostMessageW/);
  assert.match(s, /Resolve-JarvisTarget/);
  assert.doesNotMatch(s, /SetForegroundWindow|SetCursorPos|mouse_event/);
});

test("background type escapa aspas simples do texto", () => {
  const s = buildBackgroundTypeScript({ text: "it's" });
  assert.ok(s.includes("it''s"));
});

test("parseActResult le marcadores", () => {
  assert.deepEqual(parseActResult("ruido\nJARVIS_RESULT=confirmed|digitado"), {
    status: "confirmed", detail: "digitado",
  });
  assert.equal(parseActResult("JARVIS_RESULT=unconfirmed|sem confirmacao").status, "unconfirmed");
  assert.equal(parseActResult("JARVIS_RESULT=ambiguous|[]").status, "ambiguous");
  assert.equal(parseActResult("nada").status, "error");
});
