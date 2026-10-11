import json
from typing import Protocol

from ext.zombus.aux.introspection import fqn
from ext.zombus.aux.serialization import JsonGraphSerializer
from ext.zombus.codex.types import Message
from ext.zombus.registry.actor import HandlerRegistry
from ext.zombus.runtime.graph import MessageGraph


class CreateUser(Message): ...


class UserCreated(Message): ...


class In(Message): ...


class Out(Message): ...


class M1(Message): ...


class M2(Message): ...


class M3(Message): ...


class ClockContract(Protocol):
    def now(self) -> int: ...


class Conn:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _build_full_graph():
    reg = HandlerRegistry()

    @reg.register
    def user_creation(message: CreateUser, conn: Conn) -> UserCreated: ...

    @reg.register
    def user_validation(message: UserCreated) -> None: ...

    return MessageGraph(reg)


def test_basic_structure():
    g = _build_full_graph()
    data = JsonGraphSerializer().serialize(g)

    assert list(data.keys()) == ["nodes", "edges"]

    node_ids = [n["id"] for n in data["nodes"]]
    assert node_ids == ["CreateUser", "UserCreated"]

    create = data["nodes"][0]
    assert create["message"] == fqn(CreateUser)
    assert len(create["handlers"]) == 1

    h = create["handlers"][0]
    assert h["name"] == "user_creation"
    assert h["module"] == __name__
    assert h["is_async"] is False
    assert h["returns"] == [fqn(UserCreated)]

    params = h["parameters"]
    assert [p["kind"] for p in params] == ["message", "uow"]
    assert params[0]["annotation"] == fqn(CreateUser)
    # message param: no begin/end
    assert "begin" not in params[0] and "end" not in params[0]
    # uow: begin+end dropped
    assert "begin" not in params[1] and "end" not in params[1]


def test_edges_reference_qualnames():
    g = _build_full_graph()
    data = JsonGraphSerializer().serialize(g)
    assert data["edges"] == [{"from": "CreateUser", "to": "UserCreated"}]


def test_return_types_sorted():
    reg = HandlerRegistry()

    @reg.register
    def h(message: M1) -> M2 | M3: ...

    @reg.register
    def h2(message: M2) -> None: ...

    @reg.register
    def h3(message: M3) -> None: ...

    g = MessageGraph(reg)
    data = JsonGraphSerializer().serialize(g)
    node = next(n for n in data["nodes"] if n["id"] == "M1")
    returns = node["handlers"][0]["returns"]
    assert returns == sorted(returns)


def test_deterministic_string_output():
    g = _build_full_graph()
    s = JsonGraphSerializer()
    assert s.serialize_to_string(g) == s.serialize_to_string(g)
    # JSON parses
    json.loads(s.serialize_to_string(g))


def test_false_uow_flags_omitted():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: In, conn: Conn) -> Out: ...

    @reg.register
    def h2(message: Out, conn: Conn) -> None: ...

    g = MessageGraph(reg)
    data = JsonGraphSerializer().serialize(g)

    node_in = next(n for n in data["nodes"] if n["id"] == "In")
    conn_param = next(
        p for p in node_in["handlers"][0]["parameters"] if p["name"] == "conn"
    )
    assert conn_param["kind"] == "uow"
    assert conn_param["begin"] is True
    assert "end" not in conn_param  # False -> omitted

    node_out = next(n for n in data["nodes"] if n["id"] == "Out")
    conn_param2 = next(
        p for p in node_out["handlers"][0]["parameters"] if p["name"] == "conn"
    )
    assert "begin" not in conn_param2  # False -> omitted
    assert conn_param2["end"] is True


def test_other_and_message_kinds_have_no_flags():
    g = _build_full_graph()
    data = JsonGraphSerializer().serialize(g)
    for node in data["nodes"]:
        for h in node["handlers"]:
            for p in h["parameters"]:
                if p["kind"] != "uow":
                    assert "begin" not in p
                    assert "end" not in p
