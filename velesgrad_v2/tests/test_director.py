import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import random

from velesgrad_v2.story.director import Director, StoryThread


def test_hottest_thread_returns_none_safely():
    d = Director(rng=random.Random(0))
    d.threads = []
    t = d.hottest_thread()
    assert t is None


def test_procedural_thread_template():
    d = Director(rng=random.Random(1))
    t = d.spawn_thread(static_pool=[])
    assert "_" in t.id
    assert 0.3 <= t.tension <= 0.7


def test_attention_weighting():
    d = Director(rng=random.Random(0))
    d.threads = [StoryThread("a", tension=0.5), StoryThread("b", tension=0.4)]
    hot = d.hottest_thread({"a": 0.0, "b": 20.0})
    assert hot.id == "b"


def test_tick_drift():
    d = Director(rng=random.Random(42))
    d.threads = [StoryThread("test", tension=0.5)]
    initial = d.threads[0].tension
    for _ in range(10):
        d.tick()
    assert d.threads[0].tension != initial
    assert 0.0 <= d.threads[0].tension <= 1.0


def test_thread_expiration():
    d = Director(rng=random.Random(42))
    t = StoryThread("old", tension=0.1, age=55)
    d.threads = [t]
    d.tick()
    assert not t.active
