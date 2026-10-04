import { test } from "node:test";
import assert from "node:assert/strict";
import {
  parseAllowlist,
  normalizeWinPath,
  isUnder,
  isAllowedWrite,
  buildReadScript,
  buildWriteScript,
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
