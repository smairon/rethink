from typing import Protocol

import pytest

from ext.zombus.codex.errors import (
    DuplicateHandlerError,
    HandlerRegistrationError,
)
from ext.zombus.codex.types import Message
from ext.zombus.registry import HandlerRegistry


class MsgA(Message): ...


class MsgB(Message): ...


class SomeProtocol(Protocol):
    def method(self) -> None: ...


class WriteConn:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class AsyncWriteConn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class NotAThing:
    pass


def test_sync_handler_registration():
    reg = HandlerRegistry()

    @reg.register
    def handler(message: MsgA, conn: WriteConn) -> MsgB:
        return MsgB()

    hs = reg.handlers(MsgA)
    assert len(hs) == 1
    assert hs[0].func is handler
    assert hs[0].message_type is MsgA
    assert hs[0].return_types == frozenset({MsgB})
    assert hs[0].is_async is False
    assert [p.kind for p in hs[0].parameters] == ["message", "uow"]
    assert hs[0].parameters[0].name == "message"
    assert hs[0].parameters[1].name == "conn"


def test_async_handler_registration():
    reg = HandlerRegistry()

    @reg.register
    async def handler(message: MsgA) -> MsgB:
        return MsgB()

    assert reg.handlers(MsgA)[0].is_async is True


def test_async_context_manager_uow():
    reg = HandlerRegistry()

    @reg.register
    def handler(message: MsgA, conn: AsyncWriteConn) -> MsgB:
        return MsgB()

    assert reg.handlers(MsgA)[0].parameters[1].kind == "uow"


def test_protocol_other_param():
    reg = HandlerRegistry()

    @reg.register
    def handler(message: MsgA, svc: SomeProtocol) -> MsgB:
        return MsgB()

    assert reg.handlers(MsgA)[0].parameters[1].kind == "other"


def test_no_message_param():
    reg = HandlerRegistry()
    with pytest.raises(HandlerRegistrationError):

        @reg.register
        def handler(conn: WriteConn) -> MsgB: ...


def test_two_message_params():
    reg = HandlerRegistry()
    with pytest.raises(HandlerRegistrationError):

        @reg.register
        def handler(a: MsgA, b: MsgB) -> MsgB: ...


def test_varargs_rejected():
    reg = HandlerRegistry()
    with pytest.raises(HandlerRegistrationError):

        @reg.register
        def handler(message: MsgA, *args) -> MsgB: ...


def test_kwargs_rejected():
    reg = HandlerRegistry()
    with pytest.raises(HandlerRegistrationError):

        @reg.register
        def handler(message: MsgA, **kwargs) -> MsgB: ...


def test_duplicate_uow_type():
    reg = HandlerRegistry()
    with pytest.raises(HandlerRegistrationError):

        @reg.register
        def handler(message: MsgA, c1: WriteConn, c2: WriteConn) -> MsgB: ...


def test_builtin_as_uow():
    reg = HandlerRegistry()

    class FakeBuiltin:
        __module__ = "builtins"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    with pytest.raises(HandlerRegistrationError):

        @reg.register
        def handler(message: MsgA, c: FakeBuiltin) -> MsgB: ...


def test_message_type_is_context_manager():
    class CMMessage(Message):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    reg = HandlerRegistry()
    with pytest.raises(HandlerRegistrationError):

        @reg.register
        def handler(message: CMMessage) -> MsgB: ...


def test_non_protocol_non_cm_param():
    reg = HandlerRegistry()
    with pytest.raises(HandlerRegistrationError):

        @reg.register
        def handler(message: MsgA, x: NotAThing) -> MsgB: ...


def test_non_message_in_union_return():
    class NotAMessage:
        pass

    reg = HandlerRegistry()
    with pytest.raises(HandlerRegistrationError):

        @reg.register
        def handler(message: MsgA) -> MsgB | NotAMessage: ...


def test_missing_return_annotation():
    reg = HandlerRegistry()
    with pytest.raises(HandlerRegistrationError):

        @reg.register
        def handler(message: MsgA):
            pass


def test_generator_handler():
    reg = HandlerRegistry()
    with pytest.raises(HandlerRegistrationError):

        @reg.register
        def handler(message: MsgA) -> MsgB:
            yield MsgB()


def test_async_generator_handler():
    reg = HandlerRegistry()
    with pytest.raises(HandlerRegistrationError):

        @reg.register
        async def handler(message: MsgA) -> MsgB:
            yield MsgB()


def test_unresolvable_annotation():
    reg = HandlerRegistry()

    # Annotation refers to name that is not defined anywhere.
    def handler(message: "DoesNotExist") -> MsgB:  # noqa: F821
        ...

    with pytest.raises(HandlerRegistrationError):
        reg.register(handler)


def test_duplicate_registration_identity():
    reg = HandlerRegistry()

    def handler(message: MsgA) -> MsgB:
        return MsgB()

    reg.register(handler)
    with pytest.raises(DuplicateHandlerError):
        reg.register(handler)


def test_multiple_different_handlers_same_message():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: MsgA) -> MsgB: ...

    @reg.register
    def h2(message: MsgA) -> MsgB: ...

    assert len(reg.handlers(MsgA)) == 2


def test_handlers_of_unregistered_returns_empty():
    reg = HandlerRegistry()
    assert reg.handlers(MsgA) == []


def test_messages_only_registered_keys():
    reg = HandlerRegistry()

    @reg.register
    def h(message: MsgA) -> MsgB: ...

    assert set(reg.messages()) == {MsgA}


def test_iter_preserves_registration_order():
    reg = HandlerRegistry()

    @reg.register
    def h1(message: MsgA) -> MsgB: ...

    @reg.register
    def h2(message: MsgB) -> MsgA: ...

    funcs = [d.func for d in reg]
    assert funcs == [h1, h2]


def test_return_annotation_containers():
    class M1(Message): ...

    class M2(Message): ...

    reg = HandlerRegistry()

    @reg.register
    def h_list(message: MsgA) -> list[M1 | M2]: ...

    @reg.register
    def h_tuple(message: MsgB) -> tuple[M1, ...]: ...

    assert reg.handlers(MsgA)[0].return_types == frozenset({M1, M2})
    assert reg.handlers(MsgB)[0].return_types == frozenset({M1})


def test_nested_containers_rejected():
    reg = HandlerRegistry()
    with pytest.raises(HandlerRegistrationError):

        @reg.register
        def h(message: MsgA) -> list[list[MsgB]]: ...
