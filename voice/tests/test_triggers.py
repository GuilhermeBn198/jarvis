from triggers import normalize


def test_normalize_remove_acentos_caixa_e_pontuacao():
    assert normalize("Olha, o JÁrvis!") == "olha o jarvis"


def test_normalize_colapsa_espacos_e_apara():
    assert normalize("  hey   jarvis  ") == "hey jarvis"


def test_normalize_de_string_vazia():
    assert normalize("") == ""
    assert normalize(None) == ""
