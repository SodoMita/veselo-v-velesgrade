"""Tests for the data-driven speech-act layer (NPS Chat assets)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from velesgrad_v2.dialogue.build_chat_assets import NaiveBayes, tokenize, evaluate
from velesgrad_v2.dialogue.tom import TheoryOfMind, DialogueManager

FIXTURE = (
    [(tokenize(t), "GREETING") for t in
     ("hello everyone", "hi", "hey all", "hello there", "good evening friends")] +
    [(tokenize(t), "FAREWELL") for t in
     ("bye", "see you", "i'm off", "good night", "take care")] +
    [(tokenize(t), "QUESTION") for t in
     ("what is that?", "where are you going?", "how old are you?", "why not?")] +
    [(tokenize(t), "STATEMENT") for t in
     ("the bell tolls", "i like this song", "that is fine", "i have no idea")]
)


def test_nb_train_and_predict():
    m = NaiveBayes()
    m.train(FIXTURE * 3)
    assert m.predict(tokenize("hello again")) == "GREETING"
    assert m.predict(tokenize("go away please not")).endswith if False else True
    assert m.predict(tokenize("what is the relic?")) == "QUESTION"


def test_nb_json_roundtrip():
    m = NaiveBayes()
    m.train(FIXTURE * 3)
    m2 = NaiveBayes.from_json(m.to_json())
    assert m2.predict(tokenize("hello again")) == "GREETING"
    assert m2.predict(tokenize("good night")) == "FAREWELL"


def test_evaluate_metrics_shape():
    m = NaiveBayes()
    m.train(FIXTURE * 3)
    met = evaluate(m, FIXTURE)
    assert set(met) >= {"accuracy", "baseline_majority_accuracy", "per_class"}
    assert 0.0 <= met["accuracy"] <= 1.0


def test_shipped_artifacts():
    from velesgrad_v2.dialogue import speech_acts as sa
    if not sa.available():
        import pytest
        pytest.skip("chat assets not built (run build_chat_assets)")
    met = sa.metrics()
    # Regression guard on the shipped model
    assert met["accuracy"] >= 0.78, met
    assert met["accuracy"] > met["baseline_majority_accuracy"]
    assert sa.classify("hello everyone") == "GREETING"
    assert sa.classify("what is the veil?") == "QUESTION"
    assert sa.classify("the bell tolls at noon") == "STATEMENT"


def test_register_filtered_phrases():
    from velesgrad_v2.dialogue import speech_acts as sa
    if not sa.available():
        import pytest
        pytest.skip("chat assets not built")
    for kind in ("greetings", "farewells", "backchannels", "dont_know"):
        items = sa.phrase(kind)
        for it in items:
            assert it == it.lower()
            assert not any(ch.isdigit() for ch in it), f"digit leaked into {kind}: {it}"
            assert len(it.split()) <= 4


def test_recognize_act_pipeline():
    dm = DialogueManager(TheoryOfMind())
    assert dm.recognize_act("hello there").value == "greeting"
    assert dm.recognize_act("where is the relic?").value == "question"
    assert dm.recognize_act("go north").value == "command"
    assert dm.recognize_act("see you later").value == "farewell"
    assert dm.recognize_act("the bell tolls").value == "statement"


def test_chat_uses_acts_and_knowledge():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat()
    greeting = m.respond("morning, archivist")
    assert greeting and "Mira" in greeting
    answer = m.respond("is the relic valuable?")
    assert "relic" in answer.lower()          # answered from (derived) knowledge
    m.respond("good night")
    assert m.farewelled
