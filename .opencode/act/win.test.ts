import { test } from "node:test";
import assert from "node:assert/strict";
import { buildWinListScript, parseWinList, buildBackgroundTypeScript, buildBackgroundKeyScript, parseActResult } from "./win.ts";

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

test("background type so confirma via UIA (nao usa caption do top-level)", () => {
  const s = buildBackgroundTypeScript({ text: "oi", window: "Notepad" });
  assert.match(s, /\$uiaRead/);
  assert.match(s, /if \(\$uiaRead -and \$text -and \$got\.Contains\(\$text\)\)/);
  assert.doesNotMatch(s, /GetWindowTextW\(\$h, \$sb, 8192\)/);
});

test("background type escapa aspas simples do texto", () => {
  const s = buildBackgroundTypeScript({ text: "it's" });
  assert.ok(s.includes("it''s"));
});

test("background key usa PostMessage WM_KEYDOWN/UP e nao rouba foco", () => {
  const s = buildBackgroundKeyScript({ keys: "^s", window: "Notepad" });
  assert.match(s, /0x0100/);
  assert.match(s, /0x0101/);
  assert.match(s, /PostMessageW/);
  assert.match(s, /Resolve-JarvisTarget/);
  assert.doesNotMatch(s, /SetForegroundWindow|SetCursorPos|mouse_event/);
});

test("background key escapa aspas simples em keys", () => {
  const s = buildBackgroundKeyScript({ keys: "it's" });
  assert.ok(s.includes("it''s"));
});

test("background key normaliza letras para VK maiusculo", () => {
  const s = buildBackgroundKeyScript({ keys: "^s" });
  assert.match(s, /IsLetter/);
  assert.match(s, /ToUpper/);
});

test("parseActResult le marcadores", () => {
  assert.deepEqual(parseActResult("ruido\nJARVIS_RESULT=confirmed|digitado"), {
    status: "confirmed", detail: "digitado",
  });
  assert.equal(parseActResult("JARVIS_RESULT=unconfirmed|sem confirmacao").status, "unconfirmed");
  assert.equal(parseActResult("JARVIS_RESULT=ambiguous|[]").status, "ambiguous");
  assert.equal(parseActResult("nada").status, "error");
});
