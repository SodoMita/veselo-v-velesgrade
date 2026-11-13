"""Tests for dialogue/wordparts.py: symbols via Unicode names, affixes, parts of unknown words."""
from velesgrad_v2.dialogue.wordparts import answer, decompose, symbol_name

LEX = {"valuable", "value", "known", "veil", "relic", "kind", "keep", "keeper", "stolen"}


def test_symbol_names_come_from_unicode():
    assert symbol_name("@") == "commercial at"
    assert symbol_name("&") == "ampersand"
    assert answer("what is @?", LEX) == "'@' is called commercial at."
    assert answer("what does % mean?", LEX) == "'%' is called percent sign."


def test_letters_keep_case():
    assert answer("what is the letter Q?", LEX) == "'Q' is the capital letter Q."
    assert answer("what is the letter q?", LEX) == "'q' is the letter Q."


def test_digits():
    assert answer("what is the digit 7?", LEX) == "'7' is called digit seven."


def test_affixes_prefix_and_suffix():
    assert answer("what does the prefix un- mean?", LEX).startswith("The prefix 'un-' means not")
    assert answer("what does -ness mean?", LEX).startswith("The suffix '-ness' means the state")
    assert "unknown" in answer("what is the prefix un-?", LEX)
    assert answer("what is the prefix xyz?", LEX) == "I do not know the prefix 'xyz'."


def test_decompose_unknown_word_into_known_parts():
    d = decompose("unvaluable", LEX)
    assert d["prefix"] == "un" and d["root"] == "valuable"
    text = answer("what does unvaluable mean?", LEX)
    assert "'un-'" in text and "'valuable'" in text


def test_unknown_word_with_known_suffix_is_partly_explained():
    text = answer("what does gleamness mean?", LEX)
    assert "-ness" in text and "do not know" in text


def test_known_word_is_left_to_normal_path():
    assert answer("what does veil mean?", LEX) is None


def test_plain_question_is_not_handled_here():
    assert answer("what is the veil?", LEX) is None
    assert answer("who stole the relic?", LEX) is None
