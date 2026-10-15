import { test } from "node:test";
import assert from "node:assert/strict";
import { WinFsTools } from "./winfs-tools.ts";
import { isAllowedWrite, normalizeWinPath } from "../act/winfs.ts";

test("plugin exporta apenas a factory", () => {
  assert.equal(typeof WinFsTools, "function");
});

test("politica: escrita so na allowlist e em /mnt", () => {
  const allow = ["C:\\Users\\me\\proj"];
  assert.equal(isAllowedWrite(normalizeWinPath("/mnt/c/Users/me/proj/x.md"), allow), true);
  assert.equal(isAllowedWrite(normalizeWinPath("/mnt/c/Users/me/fora/x.md"), allow), false);
});

test("win_read promete e descreve leitura WSL/Windows + listagem de pastas", async () => {
  const tools = await WinFsTools({} as never);
  const winRead = (tools.tool as Record<string, { description: string }>).win_read;
  assert.match(winRead.description, /WSL/);
  assert.match(winRead.description, /Windows/);
  assert.match(winRead.description, /lista/i);
});

type WinWrite = {
  execute: (args: Record<string, unknown>) => Promise<string>;
};

async function comAllowlist<T>(raw: string | undefined, fn: () => Promise<T>): Promise<T> {
  const anterior = process.env.JARVIS_WIN_ALLOW_WRITE;
  if (raw === undefined) delete process.env.JARVIS_WIN_ALLOW_WRITE;
  else process.env.JARVIS_WIN_ALLOW_WRITE = raw;
  try {
    return await fn();
  } finally {
    if (anterior === undefined) delete process.env.JARVIS_WIN_ALLOW_WRITE;
    else process.env.JARVIS_WIN_ALLOW_WRITE = anterior;
  }
}

async function winWrite(): Promise<WinWrite> {
  const tools = await WinFsTools({} as never);
  return (tools.tool as Record<string, WinWrite>).win_write;
}

test("win_write recusa sem confirm=true e nao toca na allowlist", async () => {
  await comAllowlist("", async () => {
    const out = await (await winWrite()).execute({
      path: "/mnt/c/Users/Public/x.txt",
      content: "x",
    });
    assert.match(out, /recusado/);
    assert.match(out, /confirm=true/);
    assert.ok(!out.includes("local.conf"));
  });
});

test("win_write com allowlist vazia ensina a configurar (local.conf, pkill do serve, aviso)", async () => {
  await comAllowlist("", async () => {
    const out = await (await winWrite()).execute({
      path: "/mnt/c/Users/Public/x.txt",
      content: "x",
      confirm: true,
    });
    assert.match(out, /JARVIS_WIN_ALLOW_WRITE/);
    assert.match(out, /local\.conf/);
    assert.match(out, /pkill -f '\[o\]pencode serve'/);
    assert.match(out, /reinicie/i);
    assert.match(out, /drive inteiro/i);
    assert.match(out, /;/);
  });
});

test("win_write fora da allowlist lista os diretorios e como ajustar", async () => {
  await comAllowlist("C:\\Users\\me\\Notas", async () => {
    const out = await (await winWrite()).execute({
      path: "/mnt/c/Users/Public/x.txt",
      content: "x",
      confirm: true,
    });
    assert.match(out, /recusado/);
    assert.match(out, /fora da allowlist/);
    assert.match(out, /\/mnt\/c\/Users\/me\/Notas/);
    assert.match(out, /local\.conf/);
  });
});

// --- #26: falha de subprocesso vira mensagem com etapa, alvo e stderr --------

// Shell que falha como o do Bun: a promessa rejeita com {exitCode, stderr, stdout}.
function shellFailing(exitCode: number, stderr: string) {
  return (() => Promise.reject({ exitCode, stderr, stdout: "" })) as never;
}

type ExecTool = { execute: (a: Record<string, unknown>) => Promise<string> };

test("win_read: falha do powershell vira erro com causa redigida e caminho", async () => {
  const tools = await WinFsTools({
    $: shellFailing(1, "Get-Item negado (chave sk-abc123456789)"),
  } as never);
  const winRead = (tools.tool as Record<string, ExecTool>).win_read;
  const out = await winRead.execute({ path: "/mnt/c/Users/me/x.txt" });
  assert.equal(
    out,
    "erro em win_read (etapa: ler arquivo; /mnt/c/Users/me/x.txt): exit code 1: Get-Item negado (chave [REDACTADO])",
  );
  assert.ok(!out.includes("sk-abc123456789"), "segredo nao pode vazar");
});

test("win_write: falha do powershell vira erro com causa e sem vazar segredo", async () => {
  await comAllowlist("C:\\Users\\me\\Notas", async () => {
    const tools = await WinFsTools({
      $: shellFailing(1, "denied: token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 invalido"),
    } as never);
    const winWriteTool = (tools.tool as Record<string, ExecTool>).win_write;
    const out = await winWriteTool.execute({
      path: "/mnt/c/Users/me/Notas/a.txt",
      content: "x",
      confirm: true,
    });
    assert.equal(
      out,
      "erro em win_write (etapa: escrever arquivo; /mnt/c/Users/me/Notas/a.txt): exit code 1: denied: token [REDACTADO] invalido",
    );
    assert.ok(!out.includes("ghp_ABCDEF"), "token nao pode vazar");
  });
});
