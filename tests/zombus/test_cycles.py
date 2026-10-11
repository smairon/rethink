import pytest

from ext.zombus.codex.errors import CycleError
from ext.zombus.codex.types import Message
from ext.zombus.registry.actor import HandlerRegistry
from ext.zombus.runtime.graph import MessageGraph


class A(Message): ...


class B(Message): ...


class C(Message): ...


def test_self_loop():
    reg = HandlerRegistry()

    @reg.register
    def h(message: A) -> A: ...

    with pytest.raises(CycleError) as ei:
        MessageGraph(reg)
    assert ei.value.path == [A, A]


def test_long_cycle():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: A) -> B: ...

    @reg.register
    def h2(message: B) -> C: ...

    @reg.register
    def h3(message: C) -> A: ...

    with pytest.raises(CycleError) as ei:
        MessageGraph(reg)
    assert ei.value.path == [A, B, C, A]


def test_double_cycle():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: A) -> B: ...

    @reg.register
    def h2(message: B) -> A: ...

    @reg.register
    def h3(message: C) -> C: ...

    with pytest.raises(CycleError) as ei:
        MessageGraph(reg)
    # First cycle found is deterministic
    assert ei.value.path[0] is ei.value.path[-1]
    assert len(ei.value.path) >= 2


def test_determinism():
    paths = []
    for _ in range(5):
        reg = HandlerRegistry()

        @reg.register
        def h1(message: A) -> B: ...

        @reg.register
        def h2(message: B) -> C: ...

        @reg.register
        def h3(message: C) -> A: ...

        with pytest.raises(CycleError) as ei:
            MessageGraph(reg)
        paths.append([t.__name__ for t in ei.value.path])

    assert all(p == paths[0] for p in paths)
