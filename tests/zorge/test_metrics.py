import pytest

from ext.zorge.container import Container
from ext.zorge.internal.metrics import NoopMetrics
from ext.zorge.provider import Provider


class RecordingMetrics(NoopMetrics):
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def resolve(self, *, scope, outcome, duration, depth):
        self.events.append(("resolve", scope, outcome, depth))

    def instance_created(self, *, scope, duration):
        self.events.append(("created", scope))

    def instance_alive(self, *, scope, delta):
        self.events.append(("alive", scope, delta))

    def scope_opened(self, *, scope):
        self.events.append(("opened", scope))

    def scope_closed(self, *, scope, lifetime, instances):
        self.events.append(("closed", scope, instances))

    def ctx_exit_error(self, *, scope):
        self.events.append(("ctx_err", scope))


@pytest.fixture
def metrics() -> RecordingMetrics:
    return RecordingMetrics()


@pytest.fixture
def provider(registry, metrics) -> Provider:
    return Provider(
        scope="container",
        dependency_registry=registry,
        metrics=metrics,
    )


class TestResolveMetrics:
    def test_not_found_reported(self, provider, metrics):
        class Service: ...

        provider.resolve(Service)

        assert ("resolve", "container", "not_found", 0) in metrics.events

    def test_built_and_cache_hit(self, registry, provider, metrics):
        class Service: ...

        registry.register(Service, scope="container", contract=Service)

        provider.resolve(Service)
        provider.resolve(Service)

        outcomes = [e for e in metrics.events if e[0] == "resolve"]
        assert ("resolve", "container", "built", 0) in outcomes
        assert ("resolve", "container", "cache_hit", 0) in outcomes

    def test_depth_tracked_for_nested_deps(self, registry, provider, metrics):
        class A: ...

        class B:
            def __init__(self, a: A): ...

        registry.register(A, scope="container", contract=A)
        registry.register(B, scope="container", contract=B)

        provider.resolve(B)

        depths = sorted(e[3] for e in metrics.events if e[0] == "resolve")
        # B: depth 0, A: depth 1
        assert depths == [0, 1]

    def test_instance_created_and_alive(self, registry, provider, metrics):
        class Service: ...

        registry.register(Service, scope="container", contract=Service)

        provider.resolve(Service)

        assert ("created", "container") in metrics.events
        assert ("alive", "container", 1) in metrics.events

    def test_error_reported(self, registry, provider, metrics):
        class Missing: ...

        class Service:
            def __init__(self, dep: Missing): ...

        registry.register(Service, scope="container", contract=Service)

        with pytest.raises(ValueError):
            provider.resolve(Service)

        assert ("resolve", "container", "error", 0) in metrics.events


class TestLifecycleMetrics:
    @pytest.mark.asyncio
    async def test_scope_opened_closed(self, registry, metrics):
        class Service: ...

        registry.register(Service, scope="container", contract=Service)

        container = Container(registry, metrics=metrics)
        async with container.provider():
            pass

        assert ("opened", "container") in metrics.events
        assert any(e[0] == "closed" and e[1] == "container" for e in metrics.events)

    @pytest.mark.asyncio
    async def test_ctx_exit_error_reported(self, registry, metrics):
        class Bad:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                raise RuntimeError("boom")

        registry.register(Bad, scope="container", contract=Bad)

        container = Container(registry, metrics=metrics)
        with pytest.raises(RuntimeError, match="boom"):
            async with container.provider() as provider:
                provider.resolve(Bad)

        assert ("ctx_err", "container") in metrics.events
        assert any(e[0] == "alive" and e[2] == -1 for e in metrics.events)
        assert any(e[0] == "closed" for e in metrics.events)


class TestNestedScopeMetrics:
    @pytest.mark.asyncio
    async def test_request_scope_opens_and_closes_independently(
        self, registry, metrics
    ):
        class ReqRes: ...

        registry.register(ReqRes, scope="request", contract=ReqRes)

        container = Container(registry, metrics=metrics)
        async with container.provider() as root:
            req = root.nested("request")
            async with req:
                req.resolve(ReqRes)

        scopes_opened = [e[1] for e in metrics.events if e[0] == "opened"]
        scopes_closed = [e[1] for e in metrics.events if e[0] == "closed"]

        assert scopes_opened == ["container", "request"]
        assert scopes_closed == ["request", "container"]

    @pytest.mark.asyncio
    async def test_container_instance_counted_under_container_scope(
        self, registry, metrics
    ):
        """Resolve из request-scope, но зависимость container-scoped —
        instance_created/alive должны быть под 'container'."""

        class ContainerRes: ...

        registry.register(ContainerRes, scope="container", contract=ContainerRes)

        container = Container(registry, metrics=metrics)
        async with container.provider() as root:
            req = root.nested("request")
            async with req:
                req.resolve(ContainerRes)

        created_scopes = [e[1] for e in metrics.events if e[0] == "created"]
        assert created_scopes == ["container"]

        alive_events = [e for e in metrics.events if e[0] == "alive"]
        # +1 при создании, -1 при закрытии — оба под 'container'
        assert ("alive", "container", 1) in alive_events
        assert ("alive", "container", -1) in alive_events
