"""Tests for dialogue/book_knowledge.py and the irregular-past fix in realizer."""
import pytest

from velesgrad_v2.dialogue.book_knowledge import (
    strip_gutenberg, split_sentences, clean_term, is_human_fact,
    load_facts, HUMAN_TERMS, BOOKS,
)
from velesgrad_v2.dialogue.realizer import _conjugate


def test_strip_gutenberg_keeps_only_body():
    raw = ("Header text\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\n"
           "The body is here.\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\nLicense")
    body = strip_gutenberg(raw)
    assert "body is here" in body
    assert "Header" not in body and "License" not in body


def test_split_sentences_normalizes_quotes_and_filters():
    body = ("He said, \u201cwe walk home at dusk\u201d and then he left the room. "
            "Too short. " + "word " * 40 + "End of a long one with more than twenty five words in it here okay.")
    out = split_sentences(body)
    assert out, "expected at least one sentence"
    assert all("\u201c" not in s and "\u201d" not in s for s in out)
    assert all(5 <= len(s.split()) <= 25 for s in out)


def test_clean_term_strips_lg_tags_and_drops_function_words():
    assert clean_term("marcus.m") == "marcus"
    assert clean_term("or.j-n") is None  # two-letter token
    assert clean_term("and") is None
    assert clean_term("which") is None
    assert clean_term("42") is None
    assert clean_term("wife") == "wife"


def test_human_filter():
    assert is_human_fact("wife", "cold")
    assert not is_human_fact("engine", "steel")


def test_books_are_public_domain_list():
    assert {b["id"] for b in BOOKS} == {2680, 205, 3600, 4200}


def test_facts_file_is_human_and_attributed():
    facts = load_facts()
    if not facts:
        pytest.skip("data/book_facts.json not built yet")
    sources = {b["title"] for b in BOOKS}
    for f in facts:
        assert f["source"] in sources
        assert f["sentence"]
        assert f["kind"] in ("inh", "eval")
        assert f["a"] != f["b"]
        narrators = {"pepys", "montaigne", "thoreau", "aurelius"}
        assert (f["a"] in HUMAN_TERMS or f["b"] in HUMAN_TERMS
                or f["a"] in narrators or f["b"] in narrators)


def test_irregular_past_is_not_inflected_for_singular_subject():
    assert _conjugate("lost in", "wife") == "lost in"
    assert _conjugate("went to", "pepys") == "went to"
    assert _conjugate("lie in", "relic") == "lies in"   # present still inflects


def test_mira_default_has_no_book_facts_and_books_option_adds_them():
    from velesgrad_v2.chat import MiraChat
    from velesgrad_v2.dialogue.lg_ctypes import is_available
    if not load_facts():
        pytest.skip("no facts built")
    assert MiraChat(seed=7).book_facts == 0
    m = MiraChat(seed=7, knowledge="books")
    assert m.book_facts == len(load_facts())
