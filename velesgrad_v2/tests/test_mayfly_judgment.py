"""Tests for mayfly_judgment: whether Mira answers, and why."""
from velesgrad_v2.mayfly_judgment import (
    SenderState, classify, decide, FLOOD_LIMIT, REPLY_COOLDOWN, GREETING_MEMORY,
)


def fresh():
    return SenderState()


def test_classify_kinds():
    assert classify("") == "empty"
    assert classify("thanks, that helps") == "closing"
    assert classify("good evening") == "greeting"
    assert classify("what is the relic?") == "question"
    assert classify("who guards the city") == "question"
    assert classify("the market was crowded today") == "statement"


def test_closing_gets_silence():
    d = decide("thanks, Mira", fresh(), now=1000.0)
    assert d.reply is False and d.kind == "closing"


def test_question_gets_answer():
    d = decide("what is the veil?", fresh(), now=1000.0)
    assert d.reply is True and d.kind == "question"


def test_empty_gets_silence():
    assert decide("   ", fresh(), now=0.0).reply is False


def test_substantive_statement_gets_reflection_only_if_relevant():
    d = decide("my wife was ill with a cold this week", fresh(), now=0.0, relevant=True)
    assert d.reply is True and d.kind == "statement"
    d = decide("my wife was ill with a cold this week", fresh(), now=0.0, relevant=False)
    assert d.reply is False and "nothing to add" in d.reason


def test_thanks_with_a_name_and_phrase_is_a_closing():
    assert classify("thanks Mira, that was helpful") == "closing"
    assert classify("ok, what is the veil?") == "question"


def test_short_statement_gets_silence():
    d = decide("nice weather", fresh(), now=0.0)
    assert d.reply is False


def test_flooding_is_throttled_except_questions():
    st = fresh()
    st.addressed_times = [100.0] * FLOOD_LIMIT
    d = decide("my wife was ill with a cold this week", st, now=110.0)
    assert d.reply is False and "giving others the floor" in d.reason
    # a question still gets through even while flooding
    assert decide("what is the veil?", st, now=110.0).reply is True


def test_cooldown_quiets_short_remarks_right_after_a_reply():
    st = fresh()
    st.last_reply_at = 1000.0
    assert decide("ok then", st, now=1005.0).reply is False        # closing anyway
    assert decide("i see it", st, now=1005.0).reply is False       # short remark (3 words)
    # a question inside the cooldown still deserves an answer
    assert decide("why is that so?", st, now=1005.0).reply is True
    # after the cooldown a short statement is no longer suppressed by it
    assert decide("i see it", st, now=1000.0 + REPLY_COOLDOWN + 1).reply is False  # too short anyway
    assert decide("i see the market in the square now", st,
                  now=1000.0 + REPLY_COOLDOWN + 1).reply is True


def test_greeting_not_repeated_within_memory():
    st = fresh()
    st.last_greeted_at = 0.0
    assert decide("hello Mira", st, now=GREETING_MEMORY - 1).reply is False
    d = decide("hello Mira", st, now=GREETING_MEMORY + 1)
    assert d.reply is True and d.kind == "greeting"


def test_every_decision_has_a_reason():
    for text in ["", "thanks", "hi", "what?", "a long statement of several words here", "ok"]:
        d = decide(text, fresh(), now=0.0)
        assert d.reason and isinstance(d.reply, bool)
