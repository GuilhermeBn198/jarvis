import { test } from "node:test";
import assert from "node:assert/strict";
import { buildWinListScript, parseWinList, buildBackgroundTypeScript, buildBackgroundKeyScript, parseActResult, chooseActScript } from "./win.ts";

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

test("background type injeta via WM_CHAR (PostMessage) e nunca usa SetValue", () => {
  const s = buildBackgroundTypeScript({ text: "oi", window: "Notepad" });
  // Injeção primária é PostMessage WM_CHAR, que não ativa a janela.
  assert.match(s, /PostMessageW/);
  assert.match(s, /0x0102/);
  assert.match(s, /Resolve-JarvisTarget/);
  // A UIA só LÊ (localizar/verificar); SetValue rouba o foco (regressão #9).
  assert.doesNotMatch(s, /\.SetValue\(/);
  assert.doesNotMatch(s, /SetForegroundWindow|SetCursorPos|mouse_event/);
});

test("background type so confirma via UIA (nao usa caption do top-level)", () => {
  const s = buildBackgroundTypeScript({ text: "oi", window: "Notepad" });
  // Confirmacao vem do estado 'confirmed' do job UIA; nunca do caption do topo.
  assert.match(s, /\$state -eq 'confirmed'/);
  assert.doesNotMatch(s, /GetWindowTextW\(\$h, \$sb, 8192\)/);
});

test("background type procura Document antes de Edit (Notepad/WinUI)", () => {
  const s = buildBackgroundTypeScript({ text: "oi", window: "Notepad" });
  // O editor do Notepad moderno e ControlType.Document (RichEditD2DPT), nao Edit.
  assert.match(s, /ControlType\]::Document/);
  assert.match(s, /ControlType\]::Edit/);
  assert.ok(
    s.indexOf("ControlType]::Document") < s.indexOf("ControlType]::Edit"),
    "Document deve ser tentado antes de Edit",
  );
});

test("background type roda a UIA num job com timeout e trata estouro como unconfirmed", () => {
  const s = buildBackgroundTypeScript({ text: "oi", hwnd: 42 });
  // #8: janela travada nao pode bloquear a tool para sempre.
  assert.match(s, /Start-Job/);
  assert.match(s, /Wait-Job/);
  assert.match(s, /-Timeout/);
  assert.match(s, /JARVIS_RESULT=unconfirmed\|UIA timeout/);
});

test("background type suporta append (I2) e WM_CHAR no controle (I3)", () => {
  const ins = buildBackgroundTypeScript({ text: "oi", hwnd: 42 });
  const app = buildBackgroundTypeScript({ text: "oi", hwnd: 42, append: true });
  // I2: append distingue concatenar (default substitui via selecao previa).
  assert.match(app, /\$append = \$true/);
  assert.doesNotMatch(ins, /\$append = \$true/);
  assert.match(ins, /\$append = \$false/);
  // I3: injecao mira o handle nativo do controle, nao so o topo.
  assert.match(ins, /NativeWindowHandle/);
  assert.match(ins, /0x0102/);
  // Caret via EM_SETSEL: append -> fim (-1,-1); default -> seleciona tudo (0,-1).
  assert.match(app, /0x00B1/);
  assert.match(app, /\[IntPtr\]\(-1\), \[IntPtr\]\(-1\)/);
  assert.match(ins, /\[IntPtr\]::Zero, \[IntPtr\]\(-1\)/);
  assert.doesNotMatch(ins, /\.SetValue\(/);
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

test("mode foreground explicito forca foreground mesmo com window", () => {
  assert.equal(chooseActScript("act_type", { text: "oi", mode: "foreground", window: "Notepad" }), "");
  assert.equal(chooseActScript("act_key", { keys: "^s", mode: "foreground", window: "Notepad" }), "");
});

test("hwnd sozinho entra em background", () => {
  assert.match(chooseActScript("act_type", { text: "oi", hwnd: 123 }), /0x0102/);
});
