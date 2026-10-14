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
