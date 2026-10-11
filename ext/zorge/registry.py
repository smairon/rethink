import inspect
import logging
from collections.abc import Generator

from .entity import Dependency, Instance
from .internal.types import CallableKind, ContractType, EntityType, ScopeType

logger = logging.getLogger(__name__)


class DependencyRegistry:
    def __init__(self) -> None:
        self._dependencies: dict[ContractType, Dependency] = {}

    def register(
        self,
        entity: EntityType,
        scope: ScopeType,
        contract: ContractType | None = None,
    ) -> None:
        if contract is None:
            contract = entity if inspect.isclass(entity) else type(entity)

        existing = self._dependencies.get(contract)
        if existing is not None:
            logger.warning(
                "Overwriting dependency contract=%s (old entity=%r scope=%s, "
                "new entity=%r scope=%s)",
                contract.__name__,
                existing.entity,
                existing.scope,
                entity,
                scope,
            )

        self._dependencies[contract] = Dependency(
            entity=entity, contract=contract, scope=scope
        )
        logger.debug(
            "Registered contract=%s -> entity=%r scope=%s",
            contract.__name__,
            entity,
            scope,
        )

    def get(self, contract: ContractType) -> Dependency | None:
        dep = self._dependencies.get(contract)
        if dep is None:
            logger.debug("Lookup miss: contract=%s", contract.__name__)
        return dep


class InstanceRegistry:
    def __init__(self, scope: str, parent: InstanceRegistry | None = None) -> None:
        self._scope = scope
        self._registry: dict[ContractType, Instance] = {}
        self._parent = parent
        logger.debug(
            "InstanceRegistry created scope=%s parent_scope=%s",
            scope,
            parent.scope if parent else None,
        )

    @property
    def scope(self) -> str:
        return self._scope

    @property
    def parent(self) -> InstanceRegistry | None:
        return self._parent

    def register_instance(self, instance: Instance, contract: ContractType) -> None:
        self._registry[contract] = instance
        logger.debug(
            "Cached instance contract=%s scope=%s entity_id=%s",
            contract.__name__,
            self._scope,
            id(instance.entity),
        )

    def register(
        self,
        entity: object,
        contract: ContractType,
        callable_kind: CallableKind,
    ) -> Instance:
        instance = Instance(entity=entity, callable_kind=callable_kind)
        self.register_instance(instance=instance, contract=contract)
        return instance

    def __getitem__(self, contract: ContractType) -> Instance | None:
        return self._registry.get(contract)

    def __iter__(self) -> Generator[tuple[ContractType, Instance]]:
        yield from self._registry.items()

    def close(self) -> None:
        logger.debug(
            "Closing InstanceRegistry scope=%s entries=%d",
            self._scope,
            len(self._registry),
        )
        self._registry.clear()
        self._parent = None
