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
