import dataclasses

import pytest

from ext.zombus.registry.actor import HandlerDescriptor, ParameterDescriptor


def test_parameter_descriptor_immutable():
    p = ParameterDescriptor(name="x", annotation=int, kind="other")
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.name = "y"  # type: ignore[misc]


def test_handler_descriptor_replace():
    from ext.zombus.codex.types import Message

    class M(Message): ...

    p = ParameterDescriptor(name="x", annotation=int, kind="other")
    h = HandlerDescriptor(
        func=lambda: None,
        message_type=M,
        return_types=frozenset(),
        parameters=(p,),
        is_async=False,
    )
    p2 = dataclasses.replace(p, begin=True)
    h2 = dataclasses.replace(h, parameters=(p2,))
    assert h.parameters[0].begin is False
    assert h2.parameters[0].begin is True
