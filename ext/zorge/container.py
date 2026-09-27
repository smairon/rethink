from ext.zorge.provider import Provider
from ext.zorge.registry import DependencyRegistry


class Container:
    def __init__(
        self, dependency_registry: DependencyRegistry, root_scope: str = "container"
    ):
        self._dependency_registry = dependency_registry
        self._root_scope = root_scope

    def provider(self) -> Provider:
        return Provider(
            scope=self._root_scope, dependency_registry=self._dependency_registry
        )
