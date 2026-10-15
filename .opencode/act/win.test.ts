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
  const s = buildBackgroundKeyScript({ keys: "ctrl+s", window: "Notepad" });
  assert.match(s, /0x0100/);
  assert.match(s, /0x0101/);
  assert.match(s, /PostMessageW/);
  assert.match(s, /Resolve-JarvisTarget/);
  assert.doesNotMatch(s, /SetForegroundWindow|SetCursorPos|mouse_event/);
});

test("background key consome o parser natural (nao mais SendKeys cru)", () => {
  const s = buildBackgroundKeyScript({ keys: "enter" });
  assert.doesNotMatch(s, /\$MOD =/); // parser antigo de SendKeys removido
  assert.match(s, /"vk":13/); // VK de enter vindo do parser, no JSON
  assert.throws(() => buildBackgroundKeyScript({ keys: "foo" }), /desconhecid/i);
});

test("background key monta lParam com scan code e flag extended", () => {
  const s = buildBackgroundKeyScript({ keys: "enter" });
  // lParam correto: scan code em (sc << 16); extended em (1 << 24).
  assert.match(s, /MapVirtualKey/);
  assert.match(s, /0x0001/); // MAPVK_VK_TO_VSC
  assert.match(s, /0x1000000/); // 1 << 24
  assert.match(s, /0x8000/); // bit de transicao (keyup)
  // Keydown com lParam (sc << 16); keyup com o bit de transicao.
  assert.match(s, /PostMessageW\(\$h, 0x0100, \[IntPtr\]\$vk, \[IntPtr\]\$lpDown\)/);
  assert.match(s, /PostMessageW\(\$h, 0x0101, \[IntPtr\]\$vk, \[IntPtr\]\$lpUp\)/);
});

test("background key mira o controle de edicao via UIA (I3), com fallback no topo", () => {
  const s = buildBackgroundKeyScript({ keys: "enter", hwnd: 42 });
  // Mesmo padrao do act_type bg: Document antes de Edit, handle nativo.
  assert.match(s, /Start-Job/);
  assert.match(s, /Wait-Job/);
  assert.match(s, /ControlType\]::Document/);
  assert.match(s, /NativeWindowHandle/);
  assert.match(s, /\$native/);
  // Sem roubo de foco nem SetValue.
  assert.doesNotMatch(s, /SetForegroundWindow|SetCursorPos|\.SetValue\(/);
});

test("background key: char manda so keydown; tecla especial down+up", () => {
  const s = buildBackgroundKeyScript({ keys: "b enter", hwnd: 42 });
  assert.match(s, /if \(\$c\.onlyDown\) \{ \[void\]\[W\.Win\]::PostMessageW\(\$h, 0x0100, \[IntPtr\]\$vk, \[IntPtr\]\$lpDown\) \}/);
  assert.match(s, /"onlyDown":true/);
  assert.match(s, /"onlyDown":false/);
});

test("background key avisa que win+r nao funciona em background", () => {
  const s = buildBackgroundKeyScript({ keys: "win+r", hwnd: 42 });
  assert.match(s, /JARVIS_RESULT=unconfirmed\|' \+ \$alvo/);
  assert.match(s, /win\+r nao funciona em background/);
});

test("background key: detalhe e so o alvo (a tool compoe a mensagem sem repetir)", () => {
  const s = buildBackgroundKeyScript({ keys: "enter", hwnd: 42 });
  assert.doesNotMatch(s, /teclas enviadas para/);
});

test("background key escapa aspas simples em keys", () => {
  const s = buildBackgroundKeyScript({ keys: "plus" });
  // O payload vai num here-string 'single-quoted': JSON sem risco de interpolacao.
  assert.match(s, /@'\n\[/);
  assert.match(s, /"vk":187/);
  assert.throws(() => buildBackgroundKeyScript({ keys: "it's" }), /desconhecid/i);
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
  assert.equal(chooseActScript("act_key", { keys: "ctrl+s", mode: "foreground", window: "Notepad" }), "");
});

test("hwnd sozinho entra em background", () => {
  assert.match(chooseActScript("act_type", { text: "oi", hwnd: 123 }), /0x0102/);
});
