from ext.zombus.codex.types import Message
from ext.zombus.registry.actor import HandlerRegistry
from ext.zombus.runtime.graph import MessageGraph


class CreateMessage(Message): ...


class UserCreated(Message): ...


class EventWrited(Message): ...


class EventRegistered(Message): ...


class WriteConnectionContract:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _param(graph, msg, handler_name, param_name):
    node = next(n for n in graph.nodes if n.message is msg)
    h = next(h for h in node.handlers if h.func.__name__ == handler_name)
    return next(p for p in h.parameters if p.name == param_name)


def test_example_from_spec():
    reg = HandlerRegistry()

    @reg.register
    def user_creation(message: CreateMessage) -> UserCreated: ...

    @reg.register
    def user_writing(message: UserCreated, conn: WriteConnectionContract) -> None: ...

    @reg.register
    def event_writing(
        message: UserCreated, conn: WriteConnectionContract
    ) -> EventWrited: ...

    @reg.register
    def event_registering(
        message: EventWrited, conn: WriteConnectionContract
    ) -> EventRegistered: ...

    @reg.register
    def event_responsing(message: EventRegistered) -> None: ...

    g = MessageGraph(reg)

    p1 = _param(g, UserCreated, "user_writing", "conn")
    assert p1.kind == "uow" and p1.begin and not p1.end

    p2 = _param(g, UserCreated, "event_writing", "conn")
    assert p2.kind == "uow" and p2.begin and not p2.end

    p3 = _param(g, EventWrited, "event_registering", "conn")
    assert p3.kind == "uow" and not p3.begin and p3.end


def test_uow_single_occurrence_no_flags():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: CreateMessage, conn: WriteConnectionContract) -> UserCreated: ...

    @reg.register
    def h2(message: UserCreated) -> None: ...

    g = MessageGraph(reg)
    p = _param(g, CreateMessage, "h1", "conn")
    assert p.kind == "uow"
    assert not p.begin and not p.end


def test_uow_parallel_branches():
    class Start(Message): ...

    class A(Message): ...

    class B(Message): ...

    class End(Message): ...

    reg = HandlerRegistry()

    @reg.register
    def h1(message: Start) -> A | B: ...

    @reg.register
    def h2(message: A, conn: WriteConnectionContract) -> End: ...

    @reg.register
    def h3(message: B, conn: WriteConnectionContract) -> End: ...

    @reg.register
    def h4(message: End) -> None: ...

    g = MessageGraph(reg)

    pa = _param(g, A, "h2", "conn")
    pb = _param(g, B, "h3", "conn")
    for p in (pa, pb):
        assert p.kind == "uow"
        # flags dropped because begin and end both True
        assert not p.begin and not p.end


def test_uow_counted_once_per_node():
    class X(Message): ...

    class Y(Message): ...

    reg = HandlerRegistry()

    @reg.register
    def h1(message: CreateMessage, conn: WriteConnectionContract) -> X: ...

    @reg.register
    def h2(message: CreateMessage, conn: WriteConnectionContract) -> Y: ...

    @reg.register
    def h3(message: X) -> None: ...

    @reg.register
    def h4(message: Y) -> None: ...

    g = MessageGraph(reg)
    p1 = _param(g, CreateMessage, "h1", "conn")
    p2 = _param(g, CreateMessage, "h2", "conn")
    assert p1 == p2  # same begin/end computed once per node


def test_non_cm_protocol_is_other():
    from typing import Protocol

    class Svc(Protocol):
        def go(self) -> None: ...

    class Start(Message): ...

    class End(Message): ...

    reg = HandlerRegistry()

    @reg.register
    def h1(message: Start, svc: Svc) -> End: ...

    @reg.register
    def h2(message: End) -> None: ...

    g = MessageGraph(reg)
    p = _param(g, Start, "h1", "svc")
    assert p.kind == "other"
    assert not p.begin and not p.end
