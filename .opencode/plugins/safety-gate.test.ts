import { test } from "node:test";
import assert from "node:assert/strict";
import { askHook } from "./safety-gate.ts";

async function run(type: string, pattern?: string) {
  const output: { status: "allow" | "ask" | "deny" } = { status: "allow" };
  await askHook({ type, pattern }, output);
  return output.status;
}

test("wiring: bash destrutivo -> deny", async () => {
  assert.equal(await run("bash", "rm -rf /"), "deny");
});
test("wiring: read -> allow", async () => {
  assert.equal(await run("read"), "allow");
});
test("wiring: desconhecido -> ask", async () => {
  assert.equal(await run("bash", "coisa-desconhecida"), "ask");
});
