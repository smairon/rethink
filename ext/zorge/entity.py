import inspect
import logging
import types
import typing
from functools import cached_property, partial

from .internal.types import (
    CallableKind,
    ContractType,
    EntityKind,
    EntityType,
    InstanceType,
    Parameter,
    ScopeType,
)

logger = logging.getLogger(__name__)


class Dependency:
    def __init__(
        self,
        entity: EntityType,
        contract: ContractType,
        scope: ScopeType,
    ) -> None:
        self._entity = entity
        self._scope = scope
        self._contract = contract

    @property
    def entity(self) -> EntityType:
        return self._entity

    @property
    def scope(self) -> ScopeType:
        return self._scope

    @property
    def contract(self) -> ContractType:
        return self._contract

    @cached_property
    def kind(self) -> EntityKind:
        if inspect.isclass(self._entity):
            return EntityKind.Class
        if inspect.ismethod(self._entity) or inspect.isfunction(self._entity):
            return EntityKind.Function
        return EntityKind.Instance

    def make_instance(self, **parameters: typing.Any) -> Instance:
        if self.kind == EntityKind.Class:
            instance = self._entity(**parameters)
            callable_kind = self.callable_kind
        elif self.kind == EntityKind.Function:
            instance = partial(self._entity, **parameters)
            callable_kind = self.callable_kind
        else:
            instance = self._entity
            callable_kind = CallableKind.Direct

        logger.debug(
            "Made instance contract=%s kind=%s callable_kind=%s params=%s",
            self._contract.__name__,
            self.kind,
            callable_kind,
            list(parameters),
        )
        return Instance(instance, callable_kind)

    @cached_property
    def parameters(self) -> list[Parameter]:
        callable_entity = (
            self._entity.__init__ if self.kind == EntityKind.Class else self._entity
        )

        try:
            hints = typing.get_type_hints(callable_entity, include_extras=True)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to get hints for %s: %s", callable_entity, str(e))
            hints = {}

        parameters: list[Parameter] = []
        for name, parameter in inspect.signature(callable_entity).parameters.items():
            if name in {"self", "cls"} or name not in hints:
                continue

            annotation = hints[name]
            base_type, annotated_metadata = self._extract_annotated(annotation)

            parameters.append(
                Parameter(
                    name=name,
                    type_annotation=base_type,
                    default=parameter.default,
                    allows_none=self._allows_none(base_type),
                    annotated_metadata=annotated_metadata,
                )
            )
        return parameters

    @cached_property
    def callable_kind(self) -> CallableKind:
        entity = self._entity
        if inspect.isclass(entity):
            return CallableKind.Sync
        if inspect.iscoroutinefunction(entity) or inspect.isasyncgenfunction(entity):
            return CallableKind.Async
        if inspect.ismethod(entity) and inspect.iscoroutinefunction(entity.__func__):
            return CallableKind.Async
        return CallableKind.Sync

    @staticmethod
    def _extract_annotated(
        annotation: typing.Any,
    ) -> tuple[typing.Any, tuple[typing.Any, ...]]:
        if typing.get_origin(annotation) is not typing.Annotated:
            return annotation, ()
        base_type, *metadata = typing.get_args(annotation)
        return base_type, tuple(metadata)

    @staticmethod
    def _allows_none(annotation: typing.Any) -> bool:
        if annotation is type(None):
            return True
        origin = typing.get_origin(annotation)
        if origin in {typing.Union, types.UnionType}:
            return type(None) in typing.get_args(annotation)
        return False


class Instance:
    def __init__(self, entity: InstanceType, callable_kind: CallableKind) -> None:
        self._entity = entity
        self._callable_kind = callable_kind

    @property
    def entity(self) -> InstanceType:
        return self._entity

    @property
    def callable_kind(self) -> CallableKind:
        return self._callable_kind

    @property
    def is_async(self) -> bool:
        return self._callable_kind == CallableKind.Async

    @property
    def context_manager_kind(self) -> CallableKind | None:
        # Проверяем уже созданный объект, а не класс/функцию.
        if hasattr(self._entity, "__aenter__") and hasattr(self._entity, "__aexit__"):
            return CallableKind.Async
        if hasattr(self._entity, "__enter__") and hasattr(self._entity, "__exit__"):
            return CallableKind.Sync
        return None
