import { test } from "node:test";
import assert from "node:assert/strict";
import { buildWinListScript, parseWinList } from "./win.ts";

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
