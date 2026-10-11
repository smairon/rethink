from .internal.metrics import NOOP_METRICS, Metrics
from .provider import Provider
from .registry import DependencyRegistry


class Container:
    def __init__(
        self,
        dependency_registry: DependencyRegistry,
        root_scope: str = "container",
        metrics: Metrics = NOOP_METRICS,
    ) -> None:
        self._dependency_registry = dependency_registry
        self._root_scope = root_scope
        self._metrics = metrics

    def provider(self) -> Provider:
        return Provider(
            scope=self._root_scope,
            dependency_registry=self._dependency_registry,
            metrics=self._metrics,
        )
