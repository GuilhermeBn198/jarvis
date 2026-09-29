from stream import CODE_OMIT, SentenceChunker


def test_emits_complete_sentence():
    c = SentenceChunker(min_chars=5)
    assert c.feed("Olá, tudo bem? ") == ["Olá, tudo bem?"]


def test_does_not_split_decimal():
    c = SentenceChunker(min_chars=5)
    assert c.feed("O valor é 3.14 hoje. ") == ["O valor é 3.14 hoje."]


def test_does_not_split_abbreviation():
    c = SentenceChunker(min_chars=5)
    assert c.feed("Fale com o Sr. Silva agora. ") == ["Fale com o Sr. Silva agora."]


def test_short_sentence_merges_with_next():
    c = SentenceChunker(min_chars=20)
    assert c.feed("Oi. ") == []
    assert c.feed("Tudo bem com você? ") == ["Oi. Tudo bem com você?"]


def test_partial_without_terminator_waits_for_flush():
    c = SentenceChunker(min_chars=5)
    assert c.feed("sem ponto final") == []
    assert c.flush() == ["sem ponto final"]


def test_code_fence_is_held_and_replaced_by_placeholder():
    c = SentenceChunker(min_chars=1)
    out = c.feed("Veja:\n```\nprint(1)\n```\nFim. ")
    assert out == ["Veja:", CODE_OMIT, "Fim."]


def test_code_fence_split_across_deltas():
    c = SentenceChunker(min_chars=5)
    assert c.feed("```py") == []
    assert c.feed("codigo```") == [CODE_OMIT]


def test_flush_inside_open_fence_emits_placeholder_once():
    c = SentenceChunker(min_chars=5)
    assert c.feed("texto ```") == ["texto"]
    assert c.flush() == [CODE_OMIT]
    assert c.flush() == []


def test_flush_emits_pending_below_min():
    c = SentenceChunker(min_chars=50)
    assert c.feed("Oi. ") == []
    assert c.flush() == ["Oi."]


def test_two_fences_emit_two_placeholders():
    c = SentenceChunker(min_chars=1)
    out = c.feed("A. ```c1``` B. ```c2``` C. ")
    assert out.count(CODE_OMIT) == 2


def test_pending_before_fence_keeps_order():
    c = SentenceChunker(min_chars=15)
    out = c.feed("Veja: ```\ncode\n```\nFim. ")
    assert out == ["Veja:", CODE_OMIT]
    assert c.flush() == ["Fim."]


def test_open_fence_flush_keeps_partial_fence():
    c = SentenceChunker(min_chars=1)
    assert c.feed("```") == []
    assert c.feed("codigo") == []
    assert c.flush() == [CODE_OMIT]
    assert c.feed("```fim. ") == ["fim."]
