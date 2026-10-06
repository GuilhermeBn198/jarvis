from triggers import normalize


def test_normalize_remove_acentos_caixa_e_pontuacao():
    assert normalize("Olha, o JÁrvis!") == "olha o jarvis"


def test_normalize_colapsa_espacos_e_apara():
    assert normalize("  hey   jarvis  ") == "hey jarvis"


def test_normalize_de_string_vazia():
    assert normalize("") == ""
    assert normalize(None) == ""


from triggers import Target, Trigger, Registry, match

REG = Registry(
    triggers=(
        Trigger("chat", ("jarvis",), Target("agent", "chat")),
        Trigger("vision", ("olha", "olha isso"), Target("action", "vision")),
        Trigger("mute", ("silencia",), Target("action", "mute"), strip=False),
    ),
    default=Target("agent", "chat"),
    fuzzy=1,
)


def test_match_exato_remove_a_frase():
    m = match("jarvis, que horas sao", REG)
    assert m is not None
    assert m.name == "chat"
    assert m.target == Target("agent", "chat")
    assert m.text == "que horas sao"


def test_match_fuzzy_tolera_erro_do_whisper():
    assert match("jarves que horas sao", REG).name == "chat"
    assert match("já vis, tudo bem", REG).name == "chat"


def test_frase_curta_nao_casa_fora_do_orcamento():
    # "olha" (4) tem orcamento 1; "olho" (d=1) casa, mas "joia" nao.
    assert match("olho isso", REG).name == "vision"
    assert match("joia isso", REG) is None


def test_fronteira_de_palavra_evita_casar_no_meio():
    assert match("jarviscoisa", REG) is None


def test_frase_mais_longa_vence():
    m = match("olha isso agora", REG)
    assert m.phrase == "olha isso"
    assert m.text == "agora"


def test_strip_false_preserva_o_texto():
    m = match("silencia", REG)
    assert m.name == "mute"
    assert m.text == "silencia"


def test_texto_vazio_retorna_none():
    assert match("", REG) is None
    assert match("   ", REG) is None


import json
from triggers import load_registry, DEFAULT_REGISTRY

BASE = {
    "version": 1, "fuzzy": 1,
    "default": {"kind": "agent", "agent": "chat"},
    "triggers": [
        {"name": "chat", "phrases": ["jarvis"], "target": {"kind": "agent", "agent": "chat"}},
        {"name": "vision", "phrases": ["olha"], "target": {"kind": "action", "action": "vision"}},
    ],
}


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_load_registry_le_base(tmp_path):
    reg = load_registry(_write(tmp_path, "b.json", BASE), use_cache=False)
    assert [t.name for t in reg.triggers] == ["chat", "vision"]
    assert reg.default == Target("agent", "chat")


def test_load_registry_merge_por_name(tmp_path):
    base = _write(tmp_path, "b.json", BASE)
    override = _write(tmp_path, "u.json", {
        "triggers": [
            {"name": "act", "phrases": ["faz"], "target": {"kind": "agent", "agent": "act"}},
            {"name": "vision", "phrases": ["veja"], "target": {"kind": "action", "action": "vision"}},
        ]
    })
    reg = load_registry(base, override, use_cache=False)
    by = {t.name: t for t in reg.triggers}
    assert by["act"].phrases == ("faz",)          # adicionado
    assert by["vision"].phrases == ("veja",)      # sobrescrito
    assert by["chat"].phrases == ("jarvis",)      # base preservada


def test_load_registry_arquivo_invalido_usa_fallback(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{ nao json", encoding="utf-8")
    reg = load_registry(str(bad), use_cache=False)
    assert reg is DEFAULT_REGISTRY
    err = capsys.readouterr().err
    assert "[triggers]" in err and "bad.json" in err


def test_load_registry_json_valido_tipo_ruim_nao_derruba(tmp_path, capsys):
    bad = _write(tmp_path, "bad.json", {
        "fuzzy": "abc",
        "triggers": [
            "nao-e-dict",
            {"name": "ok", "phrases": ["oi"], "target": {"kind": "agent", "agent": "chat"}},
        ],
    })
    reg = load_registry(bad, use_cache=False)
    assert isinstance(reg, Registry)
    assert [t.name for t in reg.triggers] == ["ok"]
    assert "descartado" in capsys.readouterr().err


def test_load_registry_gatilho_invalido_e_descartado(tmp_path, capsys):
    base = _write(tmp_path, "b.json", {
        "triggers": [
            {"name": "ok", "phrases": ["oi"], "target": {"kind": "agent", "agent": "chat"}},
            {"name": "ruim", "phrases": ["x"], "target": {"kind": "nope", "agent": "chat"}},
            {"name": "sem_frase", "phrases": [], "target": {"kind": "agent", "agent": "chat"}},
        ]
    })
    reg = load_registry(base, use_cache=False)
    assert [t.name for t in reg.triggers] == ["ok"]
    assert "descartado" in capsys.readouterr().err
