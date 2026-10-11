import inspect
import logging
import time
import typing

from .entity import Instance
from .internal.metrics import NOOP_METRICS, Metrics
from .internal.types import (
    CallableKind,
    ContractType,
    NoValue,
    NoValueType,
)
from .registry import DependencyRegistry, InstanceRegistry

logger = logging.getLogger(__name__)


class Provider:
    def __init__(
        self,
        scope: str,
        dependency_registry: DependencyRegistry,
        parent_instance_registry: InstanceRegistry | None = None,
        metrics: Metrics = NOOP_METRICS,
    ) -> None:
        self._dependency_registry = dependency_registry
        self._instance_registry = InstanceRegistry(
            scope=scope, parent=parent_instance_registry
        )
        self._metrics = metrics
        self._scope_opened_at: float | None = None

    # -- public API ------------------------------------------------------

    def resolve(self, contract: ContractType) -> Instance | NoValueType:
        return self._resolve(contract, depth=0)

    def nested(self, scope: str) -> Provider:
        return Provider(
            scope=scope,
            dependency_registry=self._dependency_registry,
            parent_instance_registry=self._instance_registry,
            metrics=self._metrics,
        )

    async def __aenter__(self) -> typing.Self:
        self._scope_opened_at = time.perf_counter()
        self._metrics.scope_opened(scope=self._instance_registry.scope)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        scope = self._instance_registry.scope
        instances = list(self._instance_registry)

        try:
            for contract, instance in instances:
                kind = instance.context_manager_kind
                if kind is None:
                    continue
                try:
                    if kind is CallableKind.Async:
                        await instance.entity.__aexit__(exc_type, exc_val, exc_tb)
                    else:
                        instance.entity.__exit__(exc_type, exc_val, exc_tb)
                except Exception:
                    self._metrics.ctx_exit_error(scope=scope)
                    logger.exception(
                        "Context manager exit failed for %s", contract.__name__
                    )
                    raise
        finally:
            if instances:
                self._metrics.instance_alive(scope=scope, delta=-len(instances))
            if self._scope_opened_at is not None:
                self._metrics.scope_closed(
                    scope=scope,
                    lifetime=time.perf_counter() - self._scope_opened_at,
                    instances=len(instances),
                )
                self._scope_opened_at = None
            self._instance_registry.close()

    # -- internals -------------------------------------------------------

    def _resolve(self, contract: ContractType, *, depth: int) -> Instance | NoValueType:
        started = time.perf_counter()
        outcome = "error"
        try:
            dependency = self._dependency_registry.get(contract)
            if dependency is None:
                outcome = "not_found"
                return NoValue

            cached = self._find_cached_instance(dependency)
            if cached is not None:
                outcome = "cache_hit"
                return cached

            args: dict[str, object] = {}
            for parameter in dependency.parameters:
                value = self._resolve(parameter.type_annotation, depth=depth + 1)

                if value is NoValue:
                    if parameter.default is not inspect.Parameter.empty:
                        args[parameter.name] = parameter.default
                        continue
                    if parameter.allows_none:
                        args[parameter.name] = None
                        continue
                    raise ValueError(
                        f"Cannot resolve parameter '{parameter.name}' "
                        f"of {contract.__name__}"
                    )

                args[parameter.name] = value.entity

            build_started = time.perf_counter()
            instance = dependency.make_instance(**args)
            self._metrics.instance_created(
                scope=dependency.scope,
                duration=time.perf_counter() - build_started,
            )
            self._store_instance(dependency, instance)
            self._metrics.instance_alive(scope=dependency.scope, delta=1)
            outcome = "built"
            return instance
        finally:
            self._metrics.resolve(
                scope=self._instance_registry.scope,
                outcome=outcome,
                duration=time.perf_counter() - started,
                depth=depth,
            )

    def _store_instance(self, dependency, instance: Instance) -> None:
        target = self._find_scope_registry(dependency.scope) or self._instance_registry
        target.register_instance(instance=instance, contract=dependency.contract)

    def _find_scope_registry(self, scope: str) -> InstanceRegistry | None:
        current: InstanceRegistry | None = self._instance_registry
        while current is not None:
            if current.scope == scope:
                return current
            current = current.parent
        return None

    def _find_cached_instance(self, dependency) -> Instance | None:
        current: InstanceRegistry | None = self._instance_registry
        while current is not None:
            if current.scope == dependency.scope:
                cached = current[dependency.contract]
                if cached is not None:
                    return cached
            current = current.parent
        return None
