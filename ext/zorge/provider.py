from ext.zorge.entity import Dependency, Instance
from ext.zorge.internal.types import CallableKind, ContractType, NoValue
from ext.zorge.registry import DependencyRegistry, InstanceRegistry


class Provider:
    def __init__(
        self,
        scope: str,
        dependency_registry: DependencyRegistry,
        parent_instance_registry: InstanceRegistry | None = None,
    ):
        self._dependency_registry = dependency_registry
        self._instance_registry = InstanceRegistry(
            scope=scope, parent=parent_instance_registry
        )

    def resolve(self, contract: ContractType) -> Instance | NoValue:
        dependency = self._dependency_registry.get(contract)
        if not dependency:
            return NoValue
        instance = self._find_cached_instance(dependency)
        if not instance:
            args = {}
            for parameter in dependency.parameters:
                value = self.resolve(parameter.type_annotation)
                if value is NoValue and parameter.default is not NoValue:
                    args[parameter.name] = parameter.default
                if value is NoValue and parameter.allows_none:
                    args[parameter.name] = None
                if value is NoValue:
                    raise ValueError(f"Cannot resolve: {contract.__name__}")
                args[parameter.name] = value
            return dependency.make_instance(**args)
        return NoValue

    def nested(self, scope: str) -> Provider:
        return Provider(
            scope=scope,
            dependency_registry=self._dependency_registry,
            parent_instance_registry=self._instance_registry,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        for contract, instance in self._instance_registry:
            if (dependency := self._dependency_registry.get(contract)) is not None:
                if dependency.context_manager_kind is CallableKind.Async:
                    await instance.__aexit__(exc_type, exc_val, exc_tb)
                elif dependency.context_manager_kind is CallableKind.Sync:
                    instance.__exit__(exc_type, exc_val, exc_tb)

        # Helping GC
        self._instance_registry.close()
        self._instance_registry = None
        self._dependency_registry = None

    def _find_cached_instance(
        self,
        dependency: Dependency,
    ) -> Instance | None:
        """Return the first node matching ``predicate`` from start to root."""
        current_node: InstanceRegistry | None = self._instance_registry
        while current_node is not None:
            if current_node.scope == dependency.scope:
                for contract, instance in current_node:
                    if contract == dependency.contract:
                        return instance
            current_node = current_node.parent
        return None
