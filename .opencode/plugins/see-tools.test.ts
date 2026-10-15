import { test } from "node:test";
import assert from "node:assert/strict";
import { SeeTools } from "./see-tools.ts";

// Fake do Bun shell na forma do runtime: `$` aguardado devolve BunShellOutput,
// cujo .text() e SINCRONO (BunShellPromise.text() e o async, nao este).
function shellReturning(stdout: string) {
  return (() => Promise.resolve({ text: () => stdout })) as never;
}

// Shell que falha como o do Bun: a promessa rejeita com {exitCode, stderr, stdout}.
function shellFailing(exitCode: number, stderr: string) {
  return (() => Promise.reject({ exitCode, stderr, stdout: "" })) as never;
}

async function seeTool(shell: unknown) {
  const tools = (await SeeTools({ $: shell } as never)).tool as Record<
    string,
    { execute: (a: Record<string, unknown>) => Promise<string> }
  >;
  return tools.see_screen;
}

test("plugin exporta apenas a factory", () => {
  assert.equal(typeof SeeTools, "function");
});

test("see_screen devolve a descricao do launcher no sucesso", async () => {
  const out = await (await seeTool(shellReturning("uma tela com um editor"))).execute({ prompt: "o que ha na tela?" });
  assert.equal(out, "uma tela com um editor");
});

// --- #26: falha do launcher vira mensagem com etapa, comando e stderr --------

test("see_screen: falha do launcher vira erro com etapa, comando e causa", async () => {
  const out = await (
    await seeTool(shellFailing(1, "VISION_MODEL nao respondeu: timeout de 30s"))
  ).execute({});
  assert.equal(
    out,
    "erro em see_screen (etapa: capturar e descrever tela; ./jarvis --see-text): exit code 1: VISION_MODEL nao respondeu: timeout de 30s",
  );
});

test("see_screen: segredo no stderr nao vaza e a causa e truncada", async () => {
  const out = await (
    await seeTool(shellFailing(1, "api key sk-abc123456789 rejeitada\n" + "x".repeat(1000)))
  ).execute({ prompt: "descreva" });
  assert.ok(!out.includes("sk-abc123456789"), "segredo nao pode vazar");
  assert.match(out, /\[REDACTADO\]/);
  assert.match(out, /\(truncado\)/);
});
