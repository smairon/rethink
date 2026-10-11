# message_graph/descriptors.py
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class ParameterDescriptor:
    name: str
    annotation: type
    kind: Literal["message", "uow", "other"]
    begin: bool = False
    end: bool = False


@dataclass(frozen=True, slots=True)
class HandlerDescriptor:
    func: Callable[..., Any]
    message_type: type
    return_types: frozenset[type]
    parameters: tuple[ParameterDescriptor, ...]
    is_async: bool