import assert from "node:assert/strict";
import { test } from "node:test";
import { extractCause, formatToolError, redact, truncate } from "./tool-error.ts";

// truncate: corta em ~400 chars com sufixo explicito.
test("truncate: texto curto passa intacto", () => {
  assert.equal(truncate("ok"), "ok");
});

test("truncate: corta em 400 e adiciona (truncado)", () => {
  const out = truncate("a".repeat(600));
  assert.equal(out, "a".repeat(400) + " (truncado)");
});

// redact: padroes de token viram [REDACTADO].
test("redact: sk-", () => {
  assert.equal(redact("chave sk-abc123XYZ fim"), "chave [REDACTADO] fim");
});

test("redact: ghp_", () => {
  assert.equal(redact("token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!"), "token [REDACTADO]!");
});

test("redact: AKIA", () => {
  assert.equal(redact("AKIAIOSFODNN7EXAMPLE"), "[REDACTADO]");
});

test("redact: Bearer preserva o esquema", () => {
  assert.equal(
    redact("Authorization: Bearer eyJhbGciOi.abc-123"),
    "Authorization: Bearer [REDACTADO]",
  );
});

test("redact: -EncodedCommand nao vaza base64", () => {
  const out = redact("powershell -EncodedCommand SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAKQA=");
  assert.ok(!out.includes("SQBFAFgA"), "nao deve conter o base64");
  assert.ok(out.includes("[REDACTADO]"));
});

test("redact: varios segredos na mesma linha", () => {
  const out = redact("sk-abc123456789 e ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789");
  assert.ok(!out.includes("sk-abc123456789"));
  assert.ok(!out.includes("ghp_ABCDEF"));
  assert.equal(out, "[REDACTADO] e [REDACTADO]");
});

// extractCause: causa real do erro, nunca so "exit code 1" cru.
test("extractCause: exitCode + stderr", () => {
  const err = { exitCode: 1, stderr: "npm ERR! missing script\n", stdout: "" };
  assert.equal(extractCause(err), "exit code 1: npm ERR! missing script");
});

test("extractCause: stderr com ANSI e limpo", () => {
  const err = { exitCode: 2, stderr: "\u001b[31mError: boom\u001b[0m\n" };
  assert.equal(extractCause(err), "exit code 2: Error: boom");
});

test("extractCause: exitCode sem stderr", () => {
  assert.equal(extractCause({ exitCode: 127 }), "exit code 127");
});

test("extractCause: stderr como Buffer (ShellError do Bun) e decodificado", () => {
  const err = { exitCode: 1, stderr: Buffer.from("boom do powershell\n"), stdout: Buffer.alloc(0) };
  assert.equal(extractCause(err), "exit code 1: boom do powershell");
});

test("extractCause: usa stdout quando stderr vazio", () => {
  const err = { exitCode: 1, stderr: "", stdout: "saida util" };
  assert.equal(extractCause(err), "exit code 1: saida util");
});

test("extractCause: Error simples usa a message", () => {
  assert.equal(extractCause(new Error("falhou feio")), "falhou feio");
});

test("extractCause: string crua", () => {
  assert.equal(extractCause("deu ruim"), "deu ruim");
});

test("extractCause: colapsa whitespace", () => {
  assert.equal(extractCause(new Error("linha1\n\n   linha2")), "linha1 linha2");
});

test("extractCause: redige segredo vazado na causa", () => {
  const out = extractCause(new Error("api key sk-abc123456789 invalida"));
  assert.ok(!out.includes("sk-abc123456789"), "segredo nao pode vazar");
  assert.ok(out.includes("[REDACTADO]"));
});

test("extractCause: trunca stderr gigante", () => {
  const out = extractCause({ exitCode: 1, stderr: "x".repeat(1000) });
  assert.ok(out.endsWith("(truncado)"));
  assert.ok(out.length <= 400 + " (truncado)".length);
});

test("extractCause: fallback para erro desconhecido", () => {
  assert.equal(extractCause(undefined), "erro desconhecido");
});

// CLIXML (#26): o stderr do PowerShell 5.1 pode vir como "#< CLIXML ... <S S=\"Error\">".
// Sem decodificar, o markup e os escapes escondem a mensagem real e os
// fragmentos de progresso consomem o orcamento do truncamento.
const CLIXML_ERRO_REAL =
  "#< CLIXML\n" +
  '<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04">' +
  '<S S="Error">O termo &apos;keybd_event&apos; n</S>' +
  '<S S="Error">&#xE3;o &#xE9; reconhecido como nome de cmdlet, fun&#xE7;&#xE3;o, ' +
  "arquivo de script ou programa oper&#xE1;vel. Verifique a grafia do nome ou, " +
  "se um caminho tiver sido inclu&#xED;do, verifique se o caminho est&#xE1; correto " +
  "e tente novamente.</S>" +
  '<S S="Error">_x000D__x000A_Em linha:1 caractere:1_x000D__x000A_+ keybd_event(0x11, 0, 0, 0)_x000D__x000A_</S>' +
  '<S S="Progress">Preparando m&#xF3;dulos para primeiro uso...</S>' +
  "</Objs>";

test("extractCause: CLIXML extrai a mensagem real dos fragmentos Error (#26)", () => {
  const out = extractCause({ exitCode: 1, stderr: CLIXML_ERRO_REAL });
  assert.match(out, /O termo 'keybd_event' não é reconhecido como nome de cmdlet/);
  assert.match(out, /keybd_event\(0x11/);
  assert.doesNotMatch(out, /#</);
  assert.doesNotMatch(out, /_x000D_/);
  // Fragmento Progress ("Preparando modulos...") nao consome o orcamento.
  assert.doesNotMatch(out, /Preparando/);
});

test("extractCause: CLIXML desescapa _xHHHH_ e entidades HTML", () => {
  const stderr =
    '#< CLIXML\n<Objs><S S="Error">a &lt;tag&gt; &amp; b_x000D__x000A__x0009_c</S></Objs>';
  assert.equal(extractCause({ exitCode: 1, stderr }), "exit code 1: a <tag> & b c");
});

test("extractCause: CLIXML sem fragmentos Error remove o preambulo", () => {
  const stderr = '#< CLIXML\n<Objs><S S="Progress">carregando modulos</S></Objs>';
  const out = extractCause({ exitCode: 1, stderr });
  assert.match(out, /carregando modulos/);
  assert.doesNotMatch(out, /#</);
});

// formatToolError: formato unico dos plugins.
test("formatToolError: formato base sem action", () => {
  const msg = formatToolError({ tool: "act", step: "run" }, { exitCode: 1, stderr: "not found" });
  assert.equal(msg, "erro em act (etapa: run): exit code 1: not found");
});

test("formatToolError: inclui action no fim", () => {
  const msg = formatToolError(
    { tool: "act", step: "run", action: "confira o PATH" },
    { exitCode: 1, stderr: "not found" },
  );
  assert.equal(msg, "erro em act (etapa: run): exit code 1: not found — confira o PATH");
});

test("formatToolError: detail curto no prefixo", () => {
  const msg = formatToolError(
    { tool: "winfs", step: "write", detail: "/mnt/c/x.txt" },
    new Error("EACCES"),
  );
  assert.equal(msg, "erro em winfs (etapa: write; /mnt/c/x.txt): EACCES");
});

test("formatToolError: aceita causa como string", () => {
  assert.equal(
    formatToolError({ tool: "visao", step: "captura" }, "timeout"),
    "erro em visao (etapa: captura): timeout",
  );
});

test("formatToolError: detail e action tambem sao redigidos", () => {
  const msg = formatToolError(
    {
      tool: "act",
      step: "run",
      detail: "curl -H 'Bearer abc.def' ",
      action: "use sk-abc123456789?",
    },
    new Error("x"),
  );
  assert.ok(!msg.includes("Bearer abc.def"));
  assert.ok(!msg.includes("sk-abc123456789"));
});
