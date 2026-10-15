import assert from "node:assert/strict";
import { test } from "node:test";
import { buildForegroundKeyScript, encodeKeyChords, MOD_VK, parseKeys } from "./keys.ts";

test("parseKeys: teclas nomeadas viram VK (case-insensitive)", () => {
  const ks = parseKeys("ENTER esc Tab backspace DELETE space");
  assert.deepEqual(
    ks.map((k) => [k.name, k.vk, k.extended]),
    [
      ["enter", 0x0d, false],
      ["esc", 0x1b, false],
      ["tab", 0x09, false],
      ["backspace", 0x08, false],
      ["delete", 0x2e, true],
      ["space", 0x20, false],
    ],
  );
});

test("parseKeys: setas/home/end/pgup/pgdn sao estendidas", () => {
  const ks = parseKeys("up down left right home end pgup pgdn");
  assert.deepEqual(
    ks.map((k) => [k.vk, k.extended]),
    [
      [0x26, true],
      [0x28, true],
      [0x25, true],
      [0x27, true],
      [0x24, true],
      [0x23, true],
      [0x21, true],
      [0x22, true],
    ],
  );
});

test("parseKeys: f1..f24 mapeiam para 0x70..0x87", () => {
  assert.equal(parseKeys("f1")[0].vk, 0x70);
  assert.equal(parseKeys("f24")[0].vk, 0x87);
  assert.throws(() => parseKeys("f25"), /desconhecid/i);
});

test("parseKeys: letras e digitos viram VK maiusculo", () => {
  assert.equal(parseKeys("a")[0].vk, 0x41);
  assert.equal(parseKeys("Z")[0].vk, 0x5a);
  assert.equal(parseKeys("7")[0].vk, 0x37);
});

test("parseKeys: plus e a tecla + (VK_OEM_PLUS)", () => {
  const k = parseKeys("plus")[0];
  assert.equal(k.vk, 0xbb);
  assert.equal(k.name, "plus");
});

test("parseKeys: combos com modificadores (ctrl/shift/alt/win)", () => {
  const ks = parseKeys("ctrl+c");
  assert.deepEqual(ks[0].mods, ["ctrl"]);
  assert.equal(ks[0].vk, 0x43);
  assert.deepEqual(parseKeys("ctrl+shift+esc")[0].mods, ["ctrl", "shift"]);
  assert.deepEqual(parseKeys("alt+f4")[0].mods, ["alt"]);
  assert.deepEqual(parseKeys("win+r")[0].mods, ["win"]);
  assert.deepEqual(parseKeys("ctrl+plus")[0].mods, ["ctrl"]);
  assert.equal(parseKeys("ctrl+plus")[0].vk, 0xbb);
});

test("parseKeys: acordes separados por espaco ou virgula", () => {
  const ks = parseKeys("ctrl+s , enter");
  assert.equal(ks.length, 2);
  assert.deepEqual(ks[0].mods, ["ctrl"]);
  assert.equal(ks[0].vk, 0x53);
  assert.equal(ks[1].vk, 0x0d);
  assert.equal(parseKeys("a,b").length, 2);
  assert.equal(parseKeys("a b").length, 2);
});

test("parseKeys: aliases comuns", () => {
  assert.equal(parseKeys("escape")[0].vk, 0x1b);
  assert.equal(parseKeys("return")[0].vk, 0x0d);
  assert.equal(parseKeys("control+a")[0].mods[0], "ctrl");
  assert.equal(parseKeys("super+r")[0].mods[0], "win");
});

test("parseKeys: token desconhecido falha com erro didatico (exemplos)", () => {
  assert.throws(() => parseKeys("foo"), /desconhecid/i);
  assert.throws(() => parseKeys("foo"), /ctrl\+c/);
  assert.throws(() => parseKeys("ctrl+foo"), /desconhecid/i);
  assert.throws(() => parseKeys(""), /informe/i);
  assert.throws(() => parseKeys("ctrl"), /ctrl\+/i);
});

test("buildForegroundKeyScript: keybd_event, nao SendKeys", () => {
  const s = buildForegroundKeyScript("ctrl+c");
  assert.match(s, /keybd_event/);
  assert.doesNotMatch(s, /SendKeys/);
  // Sem roubo de foco: keybd_event age na janela em foco, nao a forcamos.
  assert.doesNotMatch(s, /SetForegroundWindow|SetCursorPos/);
});

test("buildForegroundKeyScript: mods down, tecla, mods up (ordem)", () => {
  const s = buildForegroundKeyScript("ctrl+shift+esc");
  const iCtrl = s.indexOf(`keybd_event(0x11`);
  const iShift = s.indexOf(`keybd_event(0x10`);
  const iEscDown = s.indexOf("keybd_event(0x1B, 0, 0, 0)");
  const iEscUp = s.indexOf("keybd_event(0x1B, 0, 2, 0)");
  assert.ok(iCtrl >= 0 && iShift >= 0 && iEscDown >= 0 && iEscUp >= 0);
  assert.ok(iCtrl < iShift, "ctrl down antes de shift down");
  assert.ok(iShift < iEscDown, "shift down antes da tecla");
  assert.ok(iEscDown < iEscUp, "down antes de up");
  // Mods sobem em ordem reversa: shift up antes de ctrl up.
  const iShiftUp = s.indexOf(`keybd_event(0x10, 0, 2, 0)`);
  const iCtrlUp = s.indexOf(`keybd_event(0x11, 0, 2, 0)`);
  assert.ok(iEscUp < iShiftUp && iShiftUp < iCtrlUp, "mods up em ordem reversa");
});

test("buildForegroundKeyScript: letra manda down+up (onlyDown e mitigacao so do BG)", () => {
  // Em FG (keybd_event) down+up e digitacao normal; a duplicacao medida em
  // RichEdit foi no caminho BG (PostMessage), que segue com down-only.
  const s = buildForegroundKeyScript("b");
  assert.match(s, /keybd_event\(0x42, 0, 0, 0\)/);
  assert.match(s, /keybd_event\(0x42, 0, 2, 0\)/);
});

test("encodeKeyChords: onlyDown viaja no payload do background", () => {
  const payload = JSON.parse(encodeKeyChords(parseKeys("b enter"))) as Array<{ onlyDown: boolean }>;
  assert.equal(payload[0].onlyDown, true);
  assert.equal(payload[1].onlyDown, false);
});

test("buildForegroundKeyScript: tecla especial manda down+up", () => {
  const s = buildForegroundKeyScript("enter");
  assert.match(s, /keybd_event\(0x0D, 0, 0, 0\)/);
  assert.match(s, /keybd_event\(0x0D, 0, 2, 0\)/);
});

test("buildForegroundKeyScript: acorde multiplo gera multiplas sequencias", () => {
  const s = buildForegroundKeyScript("a b");
  assert.equal(s.match(/keybd_event\(0x41, 0, 0, 0\)/g).length, 1);
  assert.equal(s.match(/keybd_event\(0x42, 0, 0, 0\)/g).length, 1);
  assert.ok(s.indexOf("keybd_event(0x41, 0, 0, 0)") < s.indexOf("keybd_event(0x42, 0, 0, 0)"));
});
test("buildForegroundKeyScript: sem SetForegroundWindow e sem vazamento de aspas", () => {
  const s = buildForegroundKeyScript("plus");
  assert.match(s, /keybd_event\(0xBB, 0, 0, 0\)/);
  assert.doesNotMatch(s, /SetForegroundWindow|SetCursorPos/);
  // Token com aspas nem chega ao script: falha no parser (antes de executar).
  assert.throws(() => buildForegroundKeyScript("a'b"), /desconhecid/i);
});

test("MOD_VK: mapa publico dos modificadores", () => {
  assert.deepEqual(MOD_VK, { ctrl: 0x11, shift: 0x10, alt: 0x12, win: 0x5b });
});
