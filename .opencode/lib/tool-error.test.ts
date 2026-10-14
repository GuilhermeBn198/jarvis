import { test } from "node:test";
import assert from "node:assert/strict";
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
  assert.equal(
    redact("token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!"),
    "token [REDACTADO]!",
  );
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
    { tool: "act", step: "run", detail: "curl -H 'Bearer abc.def' ", action: "use sk-abc123456789?" },
    new Error("x"),
  );
  assert.ok(!msg.includes("Bearer abc.def"));
  assert.ok(!msg.includes("sk-abc123456789"));
});
