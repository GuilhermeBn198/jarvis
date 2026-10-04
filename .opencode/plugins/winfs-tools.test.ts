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
