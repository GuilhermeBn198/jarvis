import { test } from "node:test";
import assert from "node:assert/strict";
import { chmod, mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  LIST_CAP,
  LIST_SENTINEL,
  buildReadScript,
  buildWriteScript,
  formatListing,
  formatReadError,
  isAllowedWrite,
  isUnder,
  normalizeWinPath,
  parseAllowlist,
  parseListLines,
  parseReadOutput,
  readWindowsPath,
  readWslPath,
  routeRead,
  toWindowsPath,
} from "./winfs.ts";

test("normalizeWinPath converte C:\\ e /mnt/c e tira barra final", () => {
  assert.equal(normalizeWinPath("C:\\Users\\bguil\\jarvis-gui"), "/mnt/c/Users/bguil/jarvis-gui");
  assert.equal(normalizeWinPath("/mnt/c/Users/bguil/"), "/mnt/c/Users/bguil");
  assert.equal(normalizeWinPath("D:\\x"), "/mnt/d/x");
});

test("parseAllowlist aceita ; e : sem quebrar letra de drive", () => {
  assert.deepEqual(
    parseAllowlist("C:\\Users\\me\\proj; /mnt/c/Users/me/out"),
    ["/mnt/c/Users/me/proj", "/mnt/c/Users/me/out"],
  );
  assert.deepEqual(parseAllowlist(""), []);
});

test("isUnder e prefixo de diretorio, nao de string", () => {
  assert.equal(isUnder("/mnt/c/Users/me/proj/a.txt", "/mnt/c/Users/me/proj"), true);
  assert.equal(isUnder("/mnt/c/Users/me/projX/a", "/mnt/c/Users/me/proj"), false);
});

test("isAllowedWrite exige /mnt e allowlist", () => {
  const allow = ["C:\\Users\\me\\proj"];
  assert.equal(isAllowedWrite("/mnt/c/Users/me/proj/x.md", allow), true);
  assert.equal(isAllowedWrite("/mnt/c/Users/me/outra/x.md", allow), false);
  assert.equal(isAllowedWrite("/home/me/x.md", allow), false);
  assert.equal(isAllowedWrite("/mnt/c/Users/me/proj/x.md", []), false);
});

test("buildReadScript usa LiteralPath (nao interpreta curingas)", () => {
  const s = buildReadScript("C:\\Users\\me\\a.txt");
  assert.match(s, /Get-Content -LiteralPath/);
});

test("buildWriteScript: Set-Content vs Add-Content e escapa aspas", () => {
  assert.match(buildWriteScript("C:\\x\\a.txt", "oi", false), /Set-Content -LiteralPath/);
  assert.match(buildWriteScript("C:\\x\\a.txt", "oi", true), /Add-Content -LiteralPath/);
  assert.ok(buildWriteScript("C:\\x\\a.txt", "it's", false).includes("it''s"));
});

test("routeRead roteia pela forma do caminho (WSL vs Windows)", () => {
  assert.equal(routeRead("/mnt/c/Users/me"), "windows");
  assert.equal(routeRead("/mnt/c"), "windows");
  assert.equal(routeRead("C:\\Users\\me"), "windows");
  assert.equal(routeRead("/home/me/x"), "wsl");
  assert.equal(routeRead("/tmp"), "wsl");
  assert.equal(routeRead("/mnt/wsl"), "wsl"); // /mnt/<letra> exige UMA letra
  assert.equal(routeRead("relativo/x.txt"), "invalid");
  assert.equal(routeRead("//server/share"), "invalid");
  assert.equal(routeRead(""), "invalid");
});

test("toWindowsPath converte /mnt/<letra>, inclusive drive puro e caixa alta", () => {
  assert.equal(toWindowsPath("/mnt/c/Users/me/a.txt"), "C:\\Users\\me\\a.txt");
  assert.equal(toWindowsPath("/mnt/C/x"), "C:\\x");
  assert.equal(toWindowsPath("/mnt/c"), "C:\\");
  assert.equal(toWindowsPath("/home/me"), "/home/me");
});

test("buildReadScript combina stat/read/list com sentinelas e exit 0", () => {
  const s = buildReadScript("C:\\Users\\o'brien\\a.txt");
  assert.ok(s.includes(`Get-Item -LiteralPath 'C:\\Users\\o''brien\\a.txt'`));
  assert.ok(s.includes(`Get-ChildItem -LiteralPath 'C:\\Users\\o''brien\\a.txt'`));
  assert.match(s, /PSIsContainer/);
  assert.match(s, /ConvertTo-Json -Compress/);
  assert.ok(s.includes(`JARVIS-ERR:not_found`));
  assert.ok(s.includes(`JARVIS-ERR:denied`));
  assert.ok(s.includes(LIST_SENTINEL));
  assert.ok(s.indexOf("Get-ChildItem") < s.indexOf(LIST_SENTINEL));
  assert.match(s, /Get-Content -LiteralPath/);
  assert.ok(s.includes("exit 0"));
  assert.ok(s.includes("$ProgressPreference"));
});

test("parseReadOutput reconhece JARVIS-ERR e formatReadError mapeia claro", () => {
  const r = parseReadOutput("JARVIS-ERR:not_found:item not found\n");
  assert.deepEqual(r, { kind: "error", code: "not_found", message: "item not found" });
  assert.equal(
    formatReadError("/mnt/c/x", "not_found", "item not found"),
    "erro ao ler /mnt/c/x: caminho não existe",
  );
  assert.equal(formatReadError("/home/me/x", "denied"), "erro ao ler /home/me/x: sem permissão");
  assert.equal(formatReadError("/x", "error", "read failed"), "erro ao ler /x: read failed");
  assert.equal(formatReadError("/x", "error"), "erro ao ler /x: error");
});

test("parseReadOutput tolera BOM antes da sentinela", () => {
  const r = parseReadOutput("\uFEFFJARVIS-ERR:denied:access denied\r\n");
  assert.deepEqual(r, { kind: "error", code: "denied", message: "access denied" });
});

test("parseReadOutput: sem sentinela e sem marcador devolve conteudo cru", () => {
  const texto = '{"name":"x"} nao e marcador\nlinha 2';
  assert.deepEqual(parseReadOutput(texto), { kind: "content", text: texto });
});

test("parseReadOutput: marcador + JSON-lines = listagem; linha ruim ignorada", () => {
  const out = [
    LIST_SENTINEL,
    '{"name":"a.txt","type":"file","size":12}',
    "lixo",
    '{"name":"sub","type":"dir","size":0}',
    "",
  ].join("\r\n");
  const r = parseReadOutput(out);
  assert.equal(r.kind, "list");
  if (r.kind === "list") {
    assert.deepEqual(r.entries, [
      { name: "a.txt", type: "file", size: 12 },
      { name: "sub", type: "dir", size: 0 },
    ]);
  }
});

test("parseReadOutput: sentinela depois do marcador (listagem interrompida) = erro", () => {
  const out = [
    LIST_SENTINEL,
    '{"name":"a","type":"file","size":1}',
    "JARVIS-ERR:denied:access denied",
  ].join("\n");
  assert.deepEqual(parseReadOutput(out), {
    kind: "error",
    code: "denied",
    message: "access denied",
  });
});

test("parseListLines ignora lixo e normaliza campos", () => {
  const entries = parseListLines(
    ['{"name":"x","type":"outro","size":"n"}', "}", '{"sem":"name"}', '{"name":"ok"}'].join("\n"),
  );
  assert.deepEqual(entries, [
    { name: "x", type: "file", size: 0 },
    { name: "ok", type: "file", size: 0 },
  ]);
});

test("formatListing capa em 200 e avisa quantas omitiu", () => {
  const entries = Array.from({ length: 205 }, (_, i) => ({
    name: `f${i}`,
    type: "file" as const,
    size: i,
  }));
  const linhas = formatListing("/mnt/c/x", entries).split("\n");
  assert.equal(linhas[0], "listagem de /mnt/c/x (205 entradas):");
  assert.equal(linhas.length, 1 + LIST_CAP + 1);
  assert.equal(linhas[LIST_CAP], '{"name":"f199","type":"file","size":199}');
  assert.equal(linhas[linhas.length - 1], "…5 omitidas");
});

test("formatListing sem omissao nao adiciona a linha final", () => {
  const out = formatListing("/x", [{ name: "a", type: "dir", size: 0 }]);
  assert.ok(!out.includes("omitidas"));
  assert.ok(out.includes('{"name":"a","type":"dir","size":0}'));
});

test("readWslPath le arquivo UTF-8 e erro claro quando nao existe", async () => {
  const dir = await mkdtemp(join(tmpdir(), "jarvis-winfs-"));
  try {
    const file = join(dir, "ola.txt");
    await writeFile(file, "olá, wsl\n");
    assert.equal(await readWslPath(file), "olá, wsl\n");
    const missing = join(dir, "nada.txt");
    assert.equal(await readWslPath(missing), `erro ao ler ${missing}: caminho não existe`);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("readWslPath lista diretorio no shape JSON-lines, ordenado e com cap", async () => {
  const dir = await mkdtemp(join(tmpdir(), "jarvis-winfs-"));
  try {
    await writeFile(join(dir, "b.txt"), "bb");
    await writeFile(join(dir, "a.txt"), "a");
    await mkdir(join(dir, "sub"));
    const linhas = (await readWslPath(dir)).split("\n");
    assert.equal(linhas[0], `listagem de ${dir} (3 entradas):`);
    assert.equal(linhas[1], '{"name":"a.txt","type":"file","size":1}');
    assert.equal(linhas[2], '{"name":"b.txt","type":"file","size":2}');
    assert.equal(linhas[3], '{"name":"sub","type":"dir","size":0}');
    const capped = await readWslPath(dir, 2);
    assert.ok(capped.includes("…1 omitidas"), capped);
    assert.ok(capped.includes('"a.txt"'));
    assert.ok(!capped.includes('"sub"'));
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("readWslPath: diretorio sem permissao -> sem permissao", async (t) => {
  if (typeof process.getuid === "function" && process.getuid() === 0) {
    return t.skip("root ignora permissao");
  }
  const dir = await mkdtemp(join(tmpdir(), "jarvis-winfs-"));
  const fechado = join(dir, "fechado");
  try {
    await mkdir(fechado);
    await chmod(fechado, 0o000);
    assert.equal(await readWslPath(fechado), `erro ao ler ${fechado}: sem permissão`);
  } finally {
    await chmod(fechado, 0o700).catch(() => {});
    await rm(dir, { recursive: true, force: true });
  }
});

test("readWindowsPath usa o runner, converte o caminho e formata a saida", async () => {
  const scripts: string[] = [];
  const conteudo = await readWindowsPath("/mnt/c/Users/me/a.txt", async (s) => {
    scripts.push(s);
    return "conteudo\r\ndo arquivo";
  });
  assert.equal(conteudo, "conteudo\r\ndo arquivo");
  assert.ok(scripts[0].includes(`C:\\Users\\me\\a.txt`));

  const lista = await readWindowsPath(
    "/mnt/c/Windows",
    async () => [LIST_SENTINEL, '{"name":"win.ini","type":"file","size":92}'].join("\n"),
  );
  assert.deepEqual(lista.split("\n"), [
    "listagem de /mnt/c/Windows (1 entradas):",
    '{"name":"win.ini","type":"file","size":92}',
  ]);

  const erro = await readWindowsPath("/mnt/c/nope", async () => "JARVIS-ERR:not_found:item not found");
  assert.equal(erro, "erro ao ler /mnt/c/nope: caminho não existe");
});

test("readWindowsPath preserva caminhos Windows ja convertidos (C:\\...)", async () => {
  const scripts: string[] = [];
  await readWindowsPath("/mnt/d/proj/x.txt", async (s) => {
    scripts.push(s);
    return "ok";
  });
  assert.ok(scripts[0].includes(`'D:\\proj\\x.txt'`));
});
