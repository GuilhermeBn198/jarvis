import { test } from "node:test";
import assert from "node:assert/strict";
import { buildPsScript, buildWindowsArgs, encode } from "./ps.ts";

// Vetores de referencia gerados com o `subprocess.list2cmdline` do CPython
// (fonte de verdade independente; recon validou saida identica). Nao
// recalcular a expectativa com o proprio algoritmo — literais fixos.

test("list2cmdline: espaco forca aspas", () => {
  assert.equal(buildWindowsArgs(["a b"]), '"a b"');
});

test("list2cmdline: barra invertida literal sem aspas", () => {
  assert.equal(buildWindowsArgs(["a\\b c"]), '"a\\b c"');
  assert.equal(buildWindowsArgs(["a\\"]), "a\\");
});

test("list2cmdline: barra invertida final dobra quando o arg e cotado", () => {
  assert.equal(buildWindowsArgs(["a b\\"]), '"a b\\\\"');
});

test("list2cmdline: aspas internas sao escapadas com barra", () => {
  assert.equal(buildWindowsArgs(['a" b']), '"a\\" b"');
  assert.equal(buildWindowsArgs(["a\\\"b"]), "a\\\\\\\"b");
  assert.equal(buildWindowsArgs(["a\\\" b"]), '"a\\\\\\" b"');
  assert.equal(buildWindowsArgs(['--x="a b"']), '"--x=\\"a b\\""');
});

test("list2cmdline: por cento e literal (nao expande)", () => {
  assert.equal(buildWindowsArgs(["%PATH%"]), "%PATH%");
  assert.equal(buildWindowsArgs(["a%b% c"]), '"a%b% c"');
});

test("list2cmdline: vazio vira par de aspas; lista vazia vira string vazia", () => {
  assert.equal(buildWindowsArgs([""]), '""');
  assert.equal(buildWindowsArgs([]), "");
});

test("list2cmdline: multiplos args separados por um espaco", () => {
  assert.equal(buildWindowsArgs(["a", "b c"]), 'a "b c"');
  assert.equal(buildWindowsArgs(["C:\\Program Files\\app", "--flag"]), '"C:\\Program Files\\app" --flag');
  assert.equal(buildWindowsArgs(["C:\\path\\", "next"]), "C:\\path\\ next");
});

test("list2cmdline: tab forca aspas; apostrofo e literal", () => {
  assert.equal(buildWindowsArgs(["a\tb"]), '"a\tb"');
  assert.equal(buildWindowsArgs(["it's"]), "it's");
});

test("act_open sem args mantem o script antigo (regressao)", () => {
  assert.equal(buildPsScript("act_open", { target: "https://x" }), "Start-Process 'https://x'");
  assert.equal(buildPsScript("act_open", { target: "app", args: [] }), "Start-Process 'app'");
});

test("act_open escapa apostrofo do target no caminho antigo", () => {
  assert.equal(buildPsScript("act_open", { target: "C:\\it's\\a.bat" }), "Start-Process 'C:\\it''s\\a.bat'");
});

test("act_open com args usa FilePath + ArgumentList com a linha cotada", () => {
  const s = buildPsScript("act_open", { target: "C:\\app\\a.exe", args: ["a b", 'c"d'] });
  assert.equal(s, "Start-Process -FilePath 'C:\\app\\a.exe' -ArgumentList '\"a b\" c\\\"d'");
});

test("act_open com args escapa apostrofos (target e linha)", () => {
  const s = buildPsScript("act_open", { target: "x", args: ["it's a test"] });
  assert.equal(s, "Start-Process -FilePath 'x' -ArgumentList '\"it''s a test\"'");
});

test("act_open: barra invertida final e por cento chegam ao script", () => {
  assert.equal(
    buildPsScript("act_open", { target: "app", args: ["C:\\path\\"] }),
    "Start-Process -FilePath 'app' -ArgumentList 'C:\\path\\'",
  );
  assert.equal(
    buildPsScript("act_open", { target: "app", args: ["%TEMP%\\x y"] }),
    "Start-Process -FilePath 'app' -ArgumentList '\"%TEMP%\\x y\"'",
  );
});

// --- #20 act_type: contrato de `\`, aspas e `%` no foreground ---------------
// Testes de CARACTERIZACAO (passam desde ja): o recon nao reproduziu perda
// local — o builder preserva `\` (fora do SENDFLARE) e so escapa o que o
// SendKeys entende. Se alguem introduzir perda local (ex.: strip de `\`),
// estes testes quebram.

test("act_type fg: caminho com barras chega literal ao SendWait", () => {
  assert.equal(
    buildPsScript("act_type", { text: "C:\\Users\\Public\\x.txt" }),
    "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('C:\\Users\\Public\\x.txt')",
  );
});

test("act_type fg: `\\` fica literal e `%` vira {%} (SENDFLARE)", () => {
  assert.equal(
    buildPsScript("act_type", { text: "C:\\50%\\x" }),
    "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('C:\\50{%}\\x')",
  );
});

test("act_type fg: apostrofo dobra dentro do single-quote", () => {
  assert.equal(
    buildPsScript("act_type", { text: "C:\\it's\\x" }),
    "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('C:\\it''s\\x')",
  );
});

test("act_type fg: vetor combinado (% e apostrofo) preserva as barras", () => {
  assert.equal(
    buildPsScript("act_type", { text: "100% C:\\a'b" }),
    "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('100{%} C:\\a''b')",
  );
});

test("act_type fg: nenhuma barra some do texto", () => {
  const s = buildPsScript("act_type", { text: "C:\\Users\\Public\\x.txt" });
  assert.equal((s.match(/\\/g) ?? []).length, 3);
});

test("act_type fg: encode UTF-16LE/base64 preserva o script com barras", () => {
  const s = buildPsScript("act_type", { text: "C:\\Users\\Public\\x.txt" });
  assert.equal(Buffer.from(encode(s), "base64").toString("utf16le"), s);
});
