import typing
from collections.abc import Generator

from ext.zorge.entity import Dependency, Instance
from ext.zorge.internal.types import CallableKind, ContractType, ScopeType


class DependencyRegistry:
    def __init__(self):
        self._dependencies = {}

    def register(
        self,
        entity: type[typing.Any],
        scope: ScopeType,
        contract: type[typing.Any] | None = None,
    ):
        contract = contract if contract else type(entity)
        self._dependencies[contract] = Dependency(
            entity=entity, contract=contract, scope=scope
        )

    def get(self, contract: type[typing.Any]) -> Dependency | None:
        return self._dependencies.get(contract)


class InstanceRegistry:
    def __init__(self, scope: str, parent: typing.Self | None = None):
        self._scope = scope
        self._registry = {}
        self._parent = parent if parent else None

    @property
    def scope(self) -> str:
        return self._scope

    @property
    def parent(self) -> InstanceRegistry | None:
        return self._parent

    def register(
        self, entity: object, contract: ContractType, callable_kind: CallableKind
    ):
        self._registry[contract] = Instance(entity=entity, callable_kind=callable_kind)

    def __getitem__(self, contract: ContractType) -> Instance | None:
        return self._registry.get(contract)

    def __iter__(self) -> Generator[tuple[ContractType, Instance]]:
        yield from self._registry.items()

    def close(self) -> None:
        self._registry = None
        self._parent = None
