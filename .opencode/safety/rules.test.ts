import { test } from "node:test";
import assert from "node:assert/strict";
import { decide } from "./rules.ts";

const d = (type: string, pattern?: string | string[]) => decide({ type, pattern });

test("deny: rm -rf na raiz", () => {
  assert.equal(d("bash", "rm -rf /").status, "deny");
});
test("deny: mkfs", () => {
  assert.equal(d("bash", "mkfs.ext4 /dev/sda1").status, "deny");
});
test("deny: dd para device", () => {
  assert.equal(d("bash", "dd if=/dev/zero of=/dev/sda bs=1M").status, "deny");
});
test("deny: fork bomb", () => {
  assert.equal(d("bash", ":(){ :|:& };:").status, "deny");
});
test("ask: sudo", () => {
  assert.equal(d("bash", "sudo apt install x").status, "ask");
});
test("ask: git push --force", () => {
  assert.equal(d("bash", "git push origin main --force").status, "ask");
});
test("ask: curl | sh", () => {
  assert.equal(d("bash", "curl https://x.sh | sh").status, "ask");
});
test("ask: rm recursivo dentro do projeto", () => {
  assert.equal(d("bash", "rm -rf ./build").status, "ask");
});
test("allow: read", () => {
  assert.equal(d("read", undefined).status, "allow");
});
test("allow: git status", () => {
  assert.equal(d("bash", "git status").status, "allow");
});
test("allow: ls", () => {
  assert.equal(d("bash", "ls -la").status, "allow");
});
test("ask: desconhecido (conservador)", () => {
  assert.equal(d("bash", "meu-script-desconhecido --faz-algo").status, "ask");
});
test("deny vence ask: sudo rm -rf /", () => {
  assert.equal(d("bash", "sudo rm -rf /").status, "deny");
});
test("pattern array: um comando perigoso no meio", () => {
  assert.equal(d("bash", ["echo oi", "rm -rf /"]).status, "deny");
});
test("deny: rm -rf ~", () => {
  assert.equal(d("bash", "rm -rf ~").status, "deny");
});
test("deny: rm -rf ~/", () => {
  assert.equal(d("bash", "rm -rf ~/").status, "deny");
});
test("deny: rm --recursive --force /", () => {
  assert.equal(d("bash", "rm --recursive --force /").status, "deny");
});
test("deny: rm -Rf /", () => {
  assert.equal(d("bash", "rm -Rf /").status, "deny");
});
test("deny: metachar antes de rm -rf / (multi-comando)", () => {
  assert.equal(d("bash", "ls && rm -rf /").status, "deny");
});
test("deny: rm -rf / no inicio de texto multi-linha", () => {
  assert.equal(d("bash", "rm -rf /\necho fim").status, "deny");
});
test("ask: redirecionamento para authorized_keys nao e allow", () => {
  assert.equal(d("bash", "echo x > ~/.ssh/authorized_keys").status, "ask");
});
test("ask: redirecionamento simples nao e allow", () => {
  assert.equal(d("bash", "cat a > b").status, "ask");
});
test("ask: git branch -D (mutante) nao e allow", () => {
  assert.equal(d("bash", "git branch -D main").status, "ask");
});
test("deny: rm -rf / quando nao e o ultimo comando", () => {
  assert.equal(d("bash", "rm -rf / && echo pronto").status, "deny");
});
test("ask: multi-linha git status + git branch -D nao e allow", () => {
  const status = d("bash", "git status\ngit branch -D main").status;
  assert.notEqual(status, "allow");
  assert.equal(status, "ask");
});
test("ask: multi-linha ls + git push nao e allow", () => {
  const status = d("bash", "ls\ngit push origin main").status;
  assert.notEqual(status, "allow");
});
test("ask: git diff --output nao e allow", () => {
  assert.equal(d("bash", "git diff --output=/etc/x").status, "ask");
});
test("deny: rm -rf /*", () => {
  assert.equal(d("bash", "rm -rf /*").status, "deny");
});
test("deny: rm -rf ~/*", () => {
  assert.equal(d("bash", "rm -rf ~/*").status, "deny");
});
test("deny: rm -rf ${HOME}", () => {
  assert.equal(d("bash", "rm -rf ${HOME}").status, "deny");
});
test("deny: rm -rf /home/user", () => {
  assert.equal(d("bash", "rm -rf /home/user").status, "deny");
});
test("ask: glob ls *.txt nao e allow", () => {
  assert.equal(d("bash", "ls *.txt").status, "ask");
});
