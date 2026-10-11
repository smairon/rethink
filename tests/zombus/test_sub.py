import pytest

from ext.zombus.codex.errors import UnknownMessageError
from ext.zombus.codex.types import Message
from ext.zombus.registry.actor import HandlerRegistry
from ext.zombus.runtime.graph import MessageGraph


class A(Message): ...
class B(Message): ...
class C(Message): ...


class Conn:
    def __enter__(self): return self
    def __exit__(self, *args): pass


def _build_chain():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: A, conn: Conn) -> B: ...

    @reg.register
    def h2(message: B, conn: Conn) -> C: ...

    @reg.register
    def h3(message: C) -> None: ...

    return MessageGraph(reg)


def test_sub_from_root_equivalent():
    g = _build_chain()
    sub = g.sub(A)
    assert {n.message for n in sub.nodes} == {n.message for n in g.nodes}
    assert len(sub.edges) == len(g.edges)


def test_sub_truncates():
    g = _build_chain()
    sub = g.sub(B)
    assert {n.message for n in sub.nodes} == {B, C}
    assert {(e.source, e.target) for e in sub.edges} == {(B, C)}


def test_sub_recomputes_uow():
    g = _build_chain()
    # In full graph
    node_a = next(n for n in g.nodes if n.message is A)
    p_a = next(p for p in node_a.handlers[0].parameters if p.name == "conn")
    assert p_a.begin and not p_a.end

    # In sub from B: B is root, so conn should be begin+end (flags dropped)
    sub = g.sub(B)
    node_b = next(n for n in sub.nodes if n.message is B)
    p_b = next(p for p in node_b.handlers[0].parameters if p.name == "conn")
    assert not p_b.begin and not p_b.end

    # In sub, C's handler has no conn, B's end should be True? No — B.end must be True
    # because no descendant of B carries conn. Since begin and end both True -> flags dropped.
    assert p_b.kind == "uow"


def test_sub_does_not_mutate_original():
    g = _build_chain()
    _ = g.sub(B)

    node_a = next(n for n in g.nodes if n.message is A)
    p_a = next(p for p in node_a.handlers[0].parameters if p.name == "conn")
    assert p_a.begin and not p_a.end


def test_sub_unknown_message():
    g = _build_chain()

    class Unknown(Message): ...

    with pytest.raises(UnknownMessageError):
        g.sub(Unknown)