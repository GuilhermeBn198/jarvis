import { test } from "node:test";
import assert from "node:assert/strict";
import { actionFromToolCall, beforeToolCall } from "./hook.ts";

test("mapping: bash usa o comando como pattern", () => {
  assert.deepEqual(actionFromToolCall("bash", { command: "ls" }), {
    type: "bash",
    pattern: "ls",
  });
});

test("mapping: read usa o filePath como pattern", () => {
  assert.deepEqual(actionFromToolCall("read", { filePath: "~/.ssh/id_rsa" }), {
    type: "read",
    pattern: "~/.ssh/id_rsa",
  });
});

test("mapping: read aceita `path` como alias", () => {
  assert.deepEqual(actionFromToolCall("read", { path: "/tmp/x" }), {
    type: "read",
    pattern: "/tmp/x",
  });
});

test("mapping: tool sem padrão relevante fica só com o tipo", () => {
  assert.deepEqual(actionFromToolCall("grep", { include: "*.ts" }), { type: "grep" });
});

test("beforeToolCall: bash destrutivo -> throw (deny)", () => {
  assert.throws(() => beforeToolCall("bash", { command: "rm -rf /" }), /SafetyGate bloqueou/);
});

test("beforeToolCall: acesso a credencial -> throw (deny)", () => {
  assert.throws(() => beforeToolCall("bash", { command: "cat ~/.ssh/id_rsa" }), /SafetyGate bloqueou/);
});

test("beforeToolCall: read de credencial -> throw (deny)", () => {
  assert.throws(
    () => beforeToolCall("read", { filePath: "~/.ssh/id_rsa" }),
    /SafetyGate bloqueou/,
  );
});

test("beforeToolCall: comando de leitura -> não throw (allow)", () => {
  assert.doesNotThrow(() => beforeToolCall("bash", { command: "ls -la" }));
});

test("beforeToolCall: sudo -> não throw (ask não é bloqueado aqui)", () => {
  assert.doesNotThrow(() => beforeToolCall("bash", { command: "sudo apt update" }));
});
