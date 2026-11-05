import { test } from "node:test";
import assert from "node:assert/strict";
import { ModelTools } from "./model-tools.ts";

test("select_jarvis_model prefixes Ollama tags and marks local models", async () => {
  const originalFetch = globalThis.fetch;
  let request: { url: string; init?: RequestInit } | undefined;
  globalThis.fetch = async (input, init) => {
    request = { url: String(input), init };
    return new Response(JSON.stringify({ selected: "ollama/qwen3:8b", cloud: false }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };

  try {
    const plugin = await ModelTools();
    const result = await plugin.tool.select_jarvis_model.execute({ model: "qwen3:8b" });

    assert.equal(request?.url, "http://127.0.0.1:8765/model");
    assert.equal(new Headers(request?.init?.headers).get("Origin"), "tauri://localhost");
    assert.deepEqual(JSON.parse(String(request?.init?.body)), { model: "ollama/qwen3:8b" });
    assert.match(result, /Modelo local/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("select_jarvis_model warns before using cloud models", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ selected: "ollama/qwen3:cloud", cloud: true }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });

  try {
    const plugin = await ModelTools();
    const result = await plugin.tool.select_jarvis_model.execute({ model: "ollama/qwen3:cloud" });
    assert.match(result, /cloud/);
    assert.match(result, /transcrição, prompt e contexto de tela/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
