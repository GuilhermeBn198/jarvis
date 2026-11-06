import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import * as modelSettings from "../src/model-settings.mjs";
const { getModelCatalog, selectModel } = modelSettings;

test("a persisted model missing from a successful catalog has unknown origin", async () => {
  const source = await readFile(new URL("../src/main.js", import.meta.url), "utf8");
  const handler = source.match(/document\.getElementById\("s-agent-model"\)\.addEventListener\("change", \(event\) => \{([\s\S]*?)\n\}\);/);
  assert.ok(handler, "model change handler exists");

  const output = { textContent: "" };
  const onChange = new Function("event", "document", handler[1]);
  onChange({ target: { selectedOptions: [{ dataset: { available: "false" } }] } }, {
    getElementById: () => output,
  });

  assert.match(output.textContent, /indisponível|origem desconhecida/i);
});

test("catalog loader returns Ollama tags and honors persisted selection", async (t) => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async (url) => {
    assert.equal(url, "http://127.0.0.1:8765/models");
    return { ok: true, json: async () => ({ models: [{ name: "qwen3:8b", cloud: false }, { name: "minimax-m3.1-flash:cloud", cloud: true }], selected: "ollama/qwen3:8b" }) };
  };
  const result = await getModelCatalog("http://127.0.0.1:8765");
  assert.equal(result.selected, "ollama/qwen3:8b");
  assert.deepEqual(result.models.map(({ name, cloud }) => [name, cloud]), [["qwen3:8b", false], ["minimax-m3.1-flash:cloud", true]]);
});

test("catalog errors surface without replacing a selected model", async (t) => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async () => ({ ok: false, json: async () => ({ error: "offline" }) });
  await assert.rejects(() => getModelCatalog("http://localhost", "ollama/old:cloud"), /offline/);
});

test("selection uses the validated model endpoint and reports cloud status", async (t) => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "http://127.0.0.1:8765/model");
    assert.equal(options.method, "POST");
    assert.deepEqual(JSON.parse(options.body), { model: "ollama/minimax-m3.1-flash:cloud" });
    return { ok: true, json: async () => ({ selected: "ollama/minimax-m3.1-flash:cloud", cloud: true }) };
  };
  assert.deepEqual(await selectModel("http://127.0.0.1:8765", "ollama/minimax-m3.1-flash:cloud"), { selected: "ollama/minimax-m3.1-flash:cloud", cloud: true });
});

test("settings save reports a model failure without treating saved settings as failed", async (t) => {
  assert.equal(typeof modelSettings.saveSettingsRequest, "function");
  const source = await readFile(new URL("../src/main.js", import.meta.url), "utf8");
  const saveSettings = source.match(/async function saveSettings\(restart\) \{([\s\S]*?)\n\}/)?.[1];
  assert.ok(saveSettings, "settings save handler exists");
  assert.match(saveSettings, /saveSettingsRequest\(base, body, availableModel\)/);
  assert.match(saveSettings, /Configurações salvas, mas o modelo não foi atualizado/);
  assert.match(saveSettings, /if \(restart\) await restartBrain\(\)/);
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    if (url.endsWith("/settings")) {
      return { ok: true, json: async () => ({ noise_db: -28 }) };
    }
    return { ok: false, json: async () => ({ error: "catalogo Ollama indisponível" }) };
  };

  const result = await modelSettings.saveSettingsRequest(
    "http://localhost:8765",
    { noise_db: -28 },
    "ollama/qwen3:8b",
  );

  assert.equal(requests.length, 2);
  assert.equal(requests[0].url, "http://localhost:8765/settings");
  assert.equal(requests[1].url, "http://localhost:8765/model");
  assert.equal(result.settingsSaved, true);
  assert.match(result.modelError, /catalogo Ollama indisponível/);
});
