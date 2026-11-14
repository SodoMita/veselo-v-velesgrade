"""Tests for dialogue/wordparts.py: symbols via Unicode names, affixes, parts of unknown words."""
from velesgrad_v2.dialogue.wordparts import answer, decompose, symbol_name

LEX = {"valuable", "value", "known", "unknown", "veil", "relic", "kind", "keep", "keeper", "stolen"}


def test_symbol_names_come_from_unicode():
    assert symbol_name("@") == "commercial at"
    assert symbol_name("&") == "ampersand"
    assert answer("what is @?", LEX) == "According to the Unicode database, '@' is called commercial at."
    assert answer("what does % mean?", LEX) == "According to the Unicode database, '%' is called percent sign."


def test_letters_keep_case():
    assert answer("what is the letter Q?", LEX) == "According to the Unicode database, 'Q' is the capital letter Q."
    assert answer("what is the letter q?", LEX) == "According to the Unicode database, 'q' is the letter Q."


def test_digits():
    assert answer("what is the digit 7?", LEX) == "According to the Unicode database, '7' is called digit seven."


def test_affixes_prefix_and_suffix():
    assert answer("what does the prefix un- mean?", LEX).startswith("According to Wiktionary, the prefix 'un-' means not")
    ness = answer("what does -ness mean?", LEX)
    assert ness.startswith("According to Wiktionary, the suffix '-ness' means") and "state of being" in ness
    assert "unknown" in answer("what is the prefix un-?", LEX)
    assert answer("what is the prefix xyz?", LEX) == "I do not know the prefix 'xyz'."


def test_decompose_unknown_word_into_known_parts():
    d = decompose("unrelicable", LEX)          # not in the dictionary, so it must be split
    assert d["prefix"] == "un" and d["root"] == "relic" and d["suffix"] == "able"
    text = answer("what does unrelicable mean?", LEX)
    assert "'un-'" in text and "'relic'" in text


def test_unknown_word_with_known_suffix_is_partly_explained():
    text = answer("what does gleamness mean?", LEX)     # 'gleam' is in the dictionary
    assert "-ness" in text and "do not know" in text and "gleam" in text
    assert "do not know" in answer("what does zorbite mean?", LEX)


def test_meaning_question_uses_dictionary():
    text = answer("what does veil mean?", LEX)
    assert text.startswith("According to Wiktionary, 'veil' means") and "veil" in text


def test_define_without_question_mark():
    assert answer("define veil", LEX).startswith("According to Wiktionary, 'veil' means")


def test_affix_glosses_come_from_wiktionary():
    from velesgrad_v2.dialogue.wordparts import affix_table
    t = affix_table()
    if not t:
        import pytest
        pytest.skip("Wiktionary affix data not present")
    assert t["un"]["kind"] == "prefix" and "not" in t["un"]["gloss"]
    assert "agent noun" in t["er"]["gloss"]
    assert "informal" not in t["ness"]["gloss"].lower()


def test_plain_question_is_not_handled_here():
    assert answer("what is the veil?", LEX) is None
    assert answer("who stole the relic?", LEX) is None


def test_suffix_split_beats_prefix_split():
    # 'relicness' is relic + -ness, not re- + licness
    d = decompose("relicness", LEX)
    assert d and d["suffix"] == "ness" and d["root"] == "relic" and d["prefix"] is None


def test_wiktionary_headword_is_still_split_when_mira_lacks_it():
    # 'stolenness' is a Wiktionary headword but not one Mira knows: the split still applies
    d = decompose("stolenness", LEX)
    assert d and d["root"] == "stolen" and d["suffix"] == "ness"
