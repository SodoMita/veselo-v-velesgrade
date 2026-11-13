"""Tests for dialogue/morph.py: inflection, lexicon-checked analysis, coinage."""
from velesgrad_v2.dialogue.morph import inflect, analyze, derive, coin_compound

LEX = {"guard", "hold", "veil", "stop", "keep", "archive", "relic", "plan", "city",
       "steal", "study", "keeper", "glass", "bell", "valuable", "lie", "visit"}


def test_inflect_regular():
    assert inflect("guard", "past") == "guarded"
    assert inflect("stop", "past") == "stopped"       # consonant doubling
    assert inflect("visit", "past") == "visited"      # no doubling after two consonants
    assert inflect("study", "s") == "studies"
    assert inflect("glass", "s") == "glasses"


def test_inflect_irregular():
    assert inflect("keep", "past") == "kept"
    assert inflect("steal", "pp") == "stolen"
    assert inflect("hold", "s") == "holds"
    assert inflect("lie", "ing") == "lying"


def test_analyze_recovers_only_known_roots():
    assert ("guard", "past") in analyze("guarded", LEX)
    assert ("guard", "ing") in analyze("guarding", LEX)
    assert ("hold", "s") in analyze("holds", LEX)
    assert ("stop", "past") in analyze("stopped", LEX)
    assert ("keep", "irregular") in analyze("kept", LEX)
    assert ("steal", "irregular") in analyze("stole", LEX)
    assert ("lie", "ing") in analyze("lying", LEX)


def test_analyze_never_invents_a_root():
    assert analyze("vei", LEX) == []                  # 'veil' minus 'l' is not a word we know
    assert analyze("unknownword", LEX) == []


def test_derive_marks_coinages():
    d = derive("archive", "agent", LEX)
    assert d["word"] == "archiver" and d["coined"] is True and d["exists"] is False
    assert derive("keep", "agent", LEX)["exists"] is True   # 'keeper' already known
    c = coin_compound("keeper", "relic")
    assert c["word"] == "relic-keeper" and c["coined"] is True
