import inspect
import types
import typing
from functools import cached_property, partial

from internal.types import (
    CallableKind,
    ContractType,
    EntityKind,
    EntityType,
    InstanceType,
    Parameter,
    ScopeType,
)


class Dependency:
    def __init__(
        self,
        entity: EntityType,
        contract: ContractType,
        scope: ScopeType,
    ):
        self._entity = entity
        self._scope = scope
        self._contract = contract

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
        elif inspect.ismethod(self._entity) or inspect.isfunction(self._entity):
            return EntityKind.Function
        else:
            return EntityKind.Instance

    def make_instance(self, **parameters: typing.Any) -> InstanceType:
        if self.kind == EntityKind.Class:
            instance = self._entity(**parameters)
            callable_kind = self.callable_kind
        elif self.kind == EntityKind.Function:
            instance = partial(self._entity, **parameters)
            callable_kind = self.callable_kind
        else:
            instance = self._entity
            callable_kind = CallableKind.Direct
        return Instance(instance, callable_kind)

    @cached_property
    def parameters(self) -> list[Parameter]:
        callable_entity = (
            self._entity.__init__ if self.kind == EntityKind.Class else self._entity
        )

        hints = typing.get_type_hints(callable_entity, include_extras=True)
        parameters = []
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
        # 1. Проверка на coroutine function (async def)
        if inspect.iscoroutinefunction(self._entity):
            return CallableKind.Async

        # 2. Проверка на async генератор
        if inspect.isasyncgenfunction(self._entity):
            return CallableKind.Async

        # 3. Проверка на объекты с __call__, которые могут быть async
        # Некоторые объекты могут реализовывать __call__ как async
        if callable(self._entity):
            call_method = self._entity.__call__
            if inspect.iscoroutinefunction(call_method):
                return CallableKind.Async

        # 4. Проверка на классы (их вызов создает экземпляр, это sync)
        if inspect.isclass(self._entity):
            return CallableKind.Sync

        # 5. Проверка на встроенные функции (built-in)
        # Встроенные функции всегда sync
        if inspect.isbuiltin(self._entity):
            return CallableKind.Sync

        # 6. Проверка на метод (привязанный или непривязанный)
        if inspect.ismethod(self._entity) or inspect.ismethoddescriptor(self._entity):
            # Проверяем, не является ли метод async
            if hasattr(self._entity, "__func__") and inspect.iscoroutinefunction(
                self._entity.__func__
            ):
                return CallableKind.Async
            # Если это метод класса, проверяем его
            if hasattr(self._entity, "__self__"):
                # Проверяем класс, к которому привязан метод
                cls = getattr(self._entity, "__self__", None)
                if cls and hasattr(cls, self._entity.__name__):
                    method = getattr(cls, self._entity.__name__)
                    if inspect.iscoroutinefunction(method):
                        return CallableKind.Async

        # 7. Все остальное считаем sync
        return CallableKind.Sync

    @cached_property
    def context_manager_kind(self) -> CallableKind | None:
        # Быстрая проверка через ABC (для стандартных классов)
        if isinstance(self._entity, typing.AsyncContextManager):
            return CallableKind.Async
        if isinstance(self._entity, typing.ContextManager):
            return CallableKind.Sync
        # Резервная проверка по методам (для кастомных)
        if hasattr(self._entity, "__aenter__") and hasattr(self._entity, "__aexit__"):
            return CallableKind.Async
        if hasattr(self._entity, "__enter__") and hasattr(self._entity, "__exit__"):
            return CallableKind.Sync
        return None

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
        return annotation is type(None) or (
            typing.get_origin(annotation) in {typing.Union, types.UnionType}
            and type(None) in typing.get_args(annotation)
        )


class Instance:
    def __init__(self, entity: InstanceType, callable_kind: CallableKind):
        self._entity = entity
        self._callable_kind = callable_kind

    @property
    def is_async(self) -> bool:
        return self._callable_kind == CallableKind.Async
