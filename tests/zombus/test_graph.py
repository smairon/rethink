import pytest

from ext.zombus.aux.introspection import fqn
from ext.zombus.codex.errors import NoHandlerError
from ext.zombus.codex.types import Message
from ext.zombus.registry import HandlerRegistry
from ext.zombus.runtime.graph import MessageGraph, Node


class A(Message): ...


class B(Message): ...


class C(Message): ...


def test_empty_registry():
    graph = MessageGraph(HandlerRegistry())
    assert graph.nodes == ()
    assert graph.edges == ()


def test_linear_graph():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: A) -> B: ...

    @reg.register
    def h2(message: B) -> C: ...

    @reg.register
    def h3(message: C) -> None: ...

    g = MessageGraph(reg)
    assert {n.message for n in g.nodes} == {A, B, C}
    assert {(e.source, e.target) for e in g.edges} == {(A, B), (B, C)}


def test_none_terminal():
    reg = HandlerRegistry()

    @reg.register
    def h(message: A) -> None: ...

    g = MessageGraph(reg)
    assert len(g.nodes) == 1
    assert g.edges == ()


def test_branching_and_merge():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: A) -> B | C: ...

    @reg.register
    def h2(message: B) -> C: ...

    @reg.register
    def h3(message: C) -> None: ...

    g = MessageGraph(reg)
    assert {(e.source, e.target) for e in g.edges} == {(A, B), (A, C), (B, C)}


def test_multiple_handlers_one_node_preserves_order():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: A) -> B: ...

    @reg.register
    def h2(message: A) -> C: ...

    @reg.register
    def h3(message: B) -> None: ...

    @reg.register
    def h4(message: C) -> None: ...

    g = MessageGraph(reg)
    node_a = next(n for n in g.nodes if n.message is A)
    assert [h.func for h in node_a.handlers] == [h1, h2]


def test_duplicate_edges_collapsed():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: A) -> B: ...

    @reg.register
    def h2(message: A) -> B: ...

    @reg.register
    def h3(message: B) -> None: ...

    g = MessageGraph(reg)
    assert len(g.edges) == 1


def test_nodes_sorted_by_fqn():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: B) -> A: ...

    @reg.register
    def h2(message: A) -> None: ...

    g = MessageGraph(reg)
    names = [fqn(n.message) for n in g.nodes]
    assert names == sorted(names)


def test_edges_sorted_by_fqn():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: A) -> B | C: ...

    @reg.register
    def h2(message: B) -> None: ...

    @reg.register
    def h3(message: C) -> None: ...

    g = MessageGraph(reg)
    pairs = [(fqn(e.source), fqn(e.target)) for e in g.edges]
    assert pairs == sorted(pairs)


def test_no_handler_error():
    reg = HandlerRegistry()

    @reg.register
    def h(message: A) -> B: ...

    # B is a return type but has no handler -> NoHandlerError
    with pytest.raises(NoHandlerError):
        MessageGraph(reg)


def test_node_and_edge_are_dataclasses():
    reg = HandlerRegistry()

    @reg.register
    def h(message: A) -> None: ...

    g = MessageGraph(reg)
    assert isinstance(g.nodes[0], Node)
    assert isinstance(g.edges, tuple)
