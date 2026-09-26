import json

import jsonschema
from mcp.server.mcpserver import MCPServer

from config import load_config
from ollama_client import OllamaClient, OllamaError

mcp = MCPServer("delegate_local")

_client: OllamaClient | None = None


def _get_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient(load_config())
    return _client


@mcp.tool()
def delegate_local(prompt: str, json_schema: dict | None = None) -> str:
    """Executa uma sub-tarefa no modelo LOCAL (GPU) para economizar cota da nuvem.

    Use para trabalho VOLUMOSO, repetitivo ou mecanico: gerar saidas longas,
    boilerplate, ou extrair/estruturar texto em JSON. NAO use para raciocinio
    profundo, planejamento/arquitetura, nem tarefas triviais.

    Args:
        prompt: instrucao AUTO-CONTIDA (o modelo local nao ve o historico).
        json_schema: JSON Schema opcional; se enviado, a resposta sera JSON
            validado conforme o schema.
    """
    if not prompt or not prompt.strip():
        raise ValueError("prompt vazio")
    if json_schema is not None:
        try:
            json.dumps(json_schema)
        except (TypeError, ValueError) as exc:
            raise ValueError("json_schema nao e serializavel em JSON") from exc
        try:
            jsonschema.Draft7Validator.check_schema(json_schema)
        except jsonschema.exceptions.SchemaError as exc:
            raise ValueError(f"json_schema invalido: {exc.message}") from exc
    try:
        return _get_client().chat(prompt, json_schema)
    except OllamaError as exc:
        raise RuntimeError(str(exc)) from exc


if __name__ == "__main__":
    mcp.run()
