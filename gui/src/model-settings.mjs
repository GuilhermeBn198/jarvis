export async function getModelCatalog(base, current = "") {
  const response = await fetch(`${base}/models`);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "catálogo Ollama indisponível");
  return {
    models: Array.isArray(data.models) ? data.models : [],
    selected: current || data.selected || "",
  };
}

export async function selectModel(base, model) {
  const response = await fetch(`${base}/model`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "falha ao selecionar modelo");
  return data;
}

export async function saveSettingsRequest(base, settings, model = "") {
  const response = await fetch(`${base}/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "falha ao salvar configurações");

  if (!model) return { settingsSaved: true, modelError: "" };
  try {
    await selectModel(base, model);
    return { settingsSaved: true, modelError: "" };
  } catch (error) {
    return { settingsSaved: true, modelError: error.message };
  }
}
