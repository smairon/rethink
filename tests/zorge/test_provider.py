from typing import Optional

import pytest

from ext.zorge.internal.types import CallableKind, NoValue
from ext.zorge.provider import Provider


@pytest.fixture
def provider(registry) -> Provider:
    return Provider(scope="container", dependency_registry=registry)


class TestBasicResolve:
    def test_resolve_registered_class(self, registry, provider):
        class Service: ...

        registry.register(Service, scope="container", contract=Service)

        result = provider.resolve(Service)
        assert result is not NoValue
        assert isinstance(result.entity, Service)

    def test_unregistered_returns_novalue(self, provider):
        class Service: ...

        assert provider.resolve(Service) is NoValue

    def test_transitive_dependencies(self, registry, provider):
        class Database: ...

        class Repository:
            def __init__(self, db: Database):
                self.db = db

        registry.register(Database, scope="container", contract=Database)
        registry.register(Repository, scope="container", contract=Repository)

        result = provider.resolve(Repository)
        assert result is not NoValue
        assert isinstance(result.entity, Repository)
        assert isinstance(result.entity.db, Database)

    def test_caching_returns_same_instance(self, registry, provider):
        class Service: ...

        registry.register(Service, scope="container", contract=Service)

        a = provider.resolve(Service)
        b = provider.resolve(Service)
        assert a is b
        assert a.entity is b.entity

    def test_shared_dependency_across_consumers(self, registry, provider):
        class Shared: ...

        class A:
            def __init__(self, s: Shared):
                self.s = s

        class B:
            def __init__(self, s: Shared):
                self.s = s

        registry.register(Shared, scope="container", contract=Shared)
        registry.register(A, scope="container", contract=A)
        registry.register(B, scope="container", contract=B)

        a = provider.resolve(A).entity
        b = provider.resolve(B).entity

        assert a.s is b.s


class TestDefaults:
    def test_default_used_when_unresolvable(self, registry, provider):
        class Missing: ...

        class Service:
            def __init__(self, dep: Missing = "fallback"):
                self.dep = dep

        registry.register(Service, scope="container", contract=Service)

        result = provider.resolve(Service)
        assert result.entity.dep == "fallback"

    def test_optional_uses_none(self, registry, provider):
        class Missing: ...

        class Service:
            def __init__(self, dep: Optional[Missing] = None):
                self.dep = dep

        registry.register(Service, scope="container", contract=Service)

        result = provider.resolve(Service)
        assert result.entity.dep is None

    def test_required_unresolvable_raises(self, registry, provider):
        class Missing: ...

        class Service:
            def __init__(self, dep: Missing):
                self.dep = dep

        registry.register(Service, scope="container", contract=Service)

        with pytest.raises(ValueError, match="Cannot resolve"):
            provider.resolve(Service)

    def test_registered_dependency_wins_over_default(self, registry, provider):
        class Dep:
            def __init__(self):
                self.source = "registered"

        class Service:
            def __init__(self, dep: Dep = "default"):
                self.dep = dep

        registry.register(Dep, scope="container", contract=Dep)
        registry.register(Service, scope="container", contract=Service)

        result = provider.resolve(Service)
        assert isinstance(result.entity.dep, Dep)
        assert result.entity.dep.source == "registered"


class TestScopes:
    def test_nested_inherits_parent_cache(self, registry, provider):
        class Service: ...

        registry.register(Service, scope="container", contract=Service)

        a = provider.resolve(Service)
        nested = provider.nested("request")
        b = nested.resolve(Service)

        assert a is b

    def test_request_scope_isolated_between_requests(self, registry, provider):
        class ReqService: ...

        registry.register(ReqService, scope="request", contract=ReqService)

        req1 = provider.nested("request")
        req2 = provider.nested("request")

        a = req1.resolve(ReqService)
        b = req2.resolve(ReqService)

        assert a.entity is not b.entity

    def test_request_scope_caches_within_request(self, registry, provider):
        class ReqService: ...

        registry.register(ReqService, scope="request", contract=ReqService)

        req = provider.nested("request")
        a = req.resolve(ReqService)
        b = req.resolve(ReqService)

        assert a is b


class TestNoValueBehaviour:
    def test_novalue_is_falsy(self):
        assert not NoValue

    def test_novalue_repr(self):
        assert repr(NoValue) == "NoValue"


class TestFunctionDependency:
    def test_sync_function_factory(self, registry, provider):
        class Config:
            def __init__(self):
                self.value = 42

        class ClientMarker: ...

        def make_client(config: Config) -> dict:
            return {"config_value": config.value}

        registry.register(Config, scope="container", contract=Config)
        registry.register(make_client, scope="container", contract=ClientMarker)

        result = provider.resolve(ClientMarker)
        assert result is not NoValue
        assert result.callable_kind == CallableKind.Sync

        client = result.entity()  # partial(...)
        assert client == {"config_value": 42}

    def test_async_function_marked_async(self, registry, provider):
        class Marker: ...

        async def make_async() -> int:
            return 1

        registry.register(make_async, scope="container", contract=Marker)

        result = provider.resolve(Marker)
        assert result.callable_kind == CallableKind.Async


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_sync_context_manager_exit_called(self, registry):
        events: list[str] = []

        class Resource:
            def __enter__(self):
                events.append("enter")
                return self

            def __exit__(self, *args):
                events.append("exit")

        registry.register(Resource, scope="container", contract=Resource)

        provider = Provider(scope="container", dependency_registry=registry)
        async with provider:
            provider.resolve(Resource)

        assert "exit" in events

    @pytest.mark.asyncio
    async def test_async_context_manager_exit_called(self, registry):
        events: list[str] = []

        class Resource:
            async def __aenter__(self):
                events.append("enter")
                return self

            async def __aexit__(self, *args):
                events.append("exit")

        registry.register(Resource, scope="container", contract=Resource)

        provider = Provider(scope="container", dependency_registry=registry)
        async with provider:
            provider.resolve(Resource)

        assert "exit" in events

    @pytest.mark.asyncio
    async def test_exit_not_called_for_plain_objects(self, registry):
        exited: list[str] = []

        class Plain: ...

        registry.register(Plain, scope="container", contract=Plain)

        provider = Provider(scope="container", dependency_registry=registry)
        async with provider:
            inst = provider.resolve(Plain).entity
            # У чистого объекта нет __exit__, ничего не должно упасть.

        assert exited == []

    @pytest.mark.asyncio
    async def test_aenter_returns_provider(self, registry):
        provider = Provider(scope="container", dependency_registry=registry)
        async with provider as entered:
            assert entered is provider
