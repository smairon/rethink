from collections import defaultdict
from collections.abc import Callable, Generator, Sequence
from functools import cached_property
from typing import Self

from ext.zombus import codex
from ext.zombus.internal.reflection import ParameterDescriptor, parse_callable_signature

type ActorCallableType = Callable[
    [codex.Message | Sequence[codex.Message], ...],
    codex.Message | Sequence[codex.Message] | None,
]


class ActorDescriptor:
    def __init__(self, actor: ActorCallableType, priority: int) -> None:
        self._actor = actor
        self._priority = priority

    @property
    def priority(self) -> int:
        return self._priority

    @cached_property
    def dependency_parameters(self) -> list[ParameterDescriptor]:
        return [
            v
            for v in self._parameters.values()
            if not issubclass(v.parameter_type, codex.Message)
        ]

    @cached_property
    def message_parameter(self) -> ParameterDescriptor | None:
        for v in self._parameters.values():
            if issubclass(v.parameter_type, codex.Message):
                return v
        return None

    @cached_property
    def _parameters(self) -> dict[str, ParameterDescriptor]:
        return parse_callable_signature(self._actor)


class ActorRegistry:
    def __init__(self, priority: int):
        self._priority = {priority}
        self._registry: dict[type, list[ActorDescriptor]] = defaultdict(list)

    @property
    def priority(self) -> list[int]:
        return sorted(self._priority)

    def register(self, *actors: ActorCallableType) -> Self:
        self._update_registry(actors)
        return self

    def _update_registry(self, actors: Sequence[ActorCallableType]):
        for actor in actors:
            descriptor = ActorDescriptor(actor, max(self._priority))
            if descriptor.message_parameter is None:
                raise RuntimeError(f"Message parameter is required for actor {actor}")
            self._registry[descriptor.message_parameter.parameter_type].append(
                descriptor
            )

    def __iter__(self) -> Generator[ActorDescriptor]:
        for descriptors in self._registry.values():
            yield from descriptors

    def __add__(self, other: ActorRegistry) -> ActorRegistry:
        for descriptor in other:
            self._registry[descriptor.message_parameter.parameter_type].append(
                descriptor
            )
            self._priority.add(descriptor.priority)
        return self
