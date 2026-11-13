import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from velesgrad_v2.dialogue.tom import TheoryOfMind, DialogueManager, SpeechAct


def test_no_repeat_spam():
    tom = TheoryOfMind()
    dm = DialogueManager(tom)
    tom.learn("Bob", "the relic was stolen")
    u = dm.speak("Alice", "Bob", ["the relic was stolen"], turn=1)
    assert u is None


def test_novel_facts_spoken():
    tom = TheoryOfMind()
    dm = DialogueManager(tom)
    u = dm.speak("Alice", "Bob", ["new fact"], turn=1)
    assert u is not None
    assert u.text == "new fact"


def test_common_ground():
    tom = TheoryOfMind()
    dm = DialogueManager(tom)
    dm.speak("Alice", "Bob", ["secret X"], turn=1)
    assert tom.knows("Bob", "secret X")
    assert tom.is_common_ground("Alice", "Bob", "secret X")


def test_conversation_memory():
    tom = TheoryOfMind()
    dm = DialogueManager(tom)
    dm.speak("A", "B", ["fact1"], 1)
    assert dm.memory.has_heard("B", "fact1")
    assert not dm.memory.has_heard("A", "fact1")


def test_speech_act_recognition():
    tom = TheoryOfMind()
    dm = DialogueManager(tom)
    assert dm.recognize_act("hello there") == SpeechAct.GREETING
    assert dm.recognize_act("where is the relic?") == SpeechAct.QUESTION
    assert dm.recognize_act("go north") == SpeechAct.COMMAND
    assert dm.recognize_act("the bell tolls") == SpeechAct.STATEMENT


def test_novel_for_filter():
    tom = TheoryOfMind()
    tom.learn("Bob", "A")
    tom.learn("Bob", "B")
    novel = tom.novel_for("Alice", "Bob", ["A", "B", "C"])
    assert novel == ["C"]


def test_turn_taking():
    tom = TheoryOfMind()
    dm = DialogueManager(tom)
    assert dm.can_take_turn("Alice")
    dm.speak("Alice", "Bob", ["fact"], 1)
    assert dm.can_take_turn("Bob")
    assert not dm.can_take_turn("Alice")
