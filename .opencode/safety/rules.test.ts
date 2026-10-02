import { test } from "node:test";
import assert from "node:assert/strict";
import { decide } from "./rules.ts";
import { actionFromToolCall } from "./hook.ts";

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
test("deny: redirecionamento para authorized_keys (credencial)", () => {
  assert.equal(d("bash", "echo x > ~/.ssh/authorized_keys").status, "deny");
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

test("deny: cat ~/.ssh/id_rsa", () => {
  assert.equal(d("bash", "cat ~/.ssh/id_rsa").status, "deny");
});
test("deny: cat .env", () => {
  assert.equal(d("bash", "cat .env").status, "deny");
});
test("deny: cat .env.local", () => {
  assert.equal(d("bash", "cat .env.local").status, "deny");
});
test("deny: cat ~/.aws/credentials", () => {
  assert.equal(d("bash", "cat ~/.aws/credentials").status, "deny");
});
test("deny: cat /etc/shadow", () => {
  assert.equal(d("bash", "cat /etc/shadow").status, "deny");
});
test("deny: read de ~/.ssh/id_rsa (path-aware)", () => {
  assert.equal(d("read", "~/.ssh/id_rsa").status, "deny");
});
test("allow: cat README.md nao casa credencial", () => {
  assert.equal(d("bash", "cat README.md").status, "allow");
});
test("allow: cat environment.md nao casa credencial", () => {
  assert.equal(d("bash", "cat environment.md").status, "allow");
});

test("act_open destrutivo -> deny", () => {
  const a = actionFromToolCall("act_open", { target: "cmd /c rm -rf /" });
  assert.equal(decide({ ...a }).status, "deny");
});
test("act_type benigno -> allow", () => {
  const a = actionFromToolCall("act_type", { text: "ola mundo" });
  assert.equal(decide({ ...a }).status, "allow");
});
test("act_click -> allow", () => {
  const a = actionFromToolCall("act_click", { x: 1, y: 2 });
  assert.equal(decide({ ...a }).status, "allow");
});

test("deny: act_type format drive (Windows)", () => {
  const a = actionFromToolCall("act_type", { text: "format C:" });
  assert.equal(decide({ ...a }).status, "deny");
});
test("deny: act_open diskpart", () => {
  const a = actionFromToolCall("act_open", { target: "diskpart" });
  assert.equal(decide({ ...a }).status, "deny");
});
test("deny: act_type vssadmin delete (Windows)", () => {
  const a = actionFromToolCall("act_type", { text: "vssadmin delete shadows /all" });
  assert.equal(decide({ ...a }).status, "deny");
});
test("deny: act_type del /s (Windows)", () => {
  const a = actionFromToolCall("act_type", { text: "del /s C:\\temp" });
  assert.equal(decide({ ...a }).status, "deny");
});
test("deny: act_open rd /s (Windows)", () => {
  const a = actionFromToolCall("act_open", { target: "rd /s /q C:\\temp" });
  assert.equal(decide({ ...a }).status, "deny");
});
test("deny: act_type Remove-Item -Recurse (PowerShell)", () => {
  const a = actionFromToolCall("act_type", { text: "Remove-Item C:\\x -Recurse" });
  assert.equal(decide({ ...a }).status, "deny");
});
test("deny: act_type Remove-Item -Force (PowerShell)", () => {
  const a = actionFromToolCall("act_type", { text: "Remove-Item C:\\x -Force" });
  assert.equal(decide({ ...a }).status, "deny");
});
test("deny: credencial com barra invertida do Windows", () => {
  const a = actionFromToolCall("act_open", { target: "C:\\Users\\x\\.ssh\\id_rsa" });
  assert.equal(decide({ ...a }).status, "deny");
});
test("allow: act_type benigno nao casa regra Windows", () => {
  const a = actionFromToolCall("act_type", { text: "ola mundo" });
  assert.equal(decide({ ...a }).status, "allow");
});

test("win_list -> allow (leitura)", () => {
  const a = actionFromToolCall("win_list", {});
  assert.equal(decide({ ...a }).status, "allow");
});
