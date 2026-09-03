from __future__ import annotations

from app.memory.long_term import LongTermMemory
from app.memory.short_term import ShortTermMemory


def test_short_term_memory_caps_length():
    mem = ShortTermMemory(max_messages=3)
    for i in range(5):
        mem.add_user(f"msg{i}")
    assert len(mem) == 3
    contents = [m.content for m in mem.history()]
    assert contents == ["msg2", "msg3", "msg4"]


def test_short_term_memory_roles():
    mem = ShortTermMemory(max_messages=10)
    mem.add_user("hi")
    mem.add_assistant("hello")
    history = mem.history()
    assert history[0].role == "user"
    assert history[1].role == "assistant"


def test_long_term_memory_persists_across_instances(tmp_path):
    path = tmp_path / "long_term.json"
    mem1 = LongTermMemory(store_path=path)
    mem1.remember("preferred_browser", "Chrome")

    mem2 = LongTermMemory(store_path=path)
    assert mem2.recall("preferred_browser") == "Chrome"


def test_long_term_memory_forget(tmp_path):
    path = tmp_path / "long_term.json"
    mem = LongTermMemory(store_path=path)
    mem.remember("name", "Shubh")
    assert mem.forget("name") is True
    assert mem.recall("name") is None
    assert mem.forget("name") is False


def test_long_term_memory_all(tmp_path):
    path = tmp_path / "long_term.json"
    mem = LongTermMemory(store_path=path)
    mem.remember("a", "1")
    mem.remember("b", "2")
    assert mem.all() == {"a": "1", "b": "2"}
