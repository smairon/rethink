from typing import Optional

from ext.zorge.entity import Dependency, Instance
from ext.zorge.internal.types import CallableKind, EntityKind


class TestDependencyKind:
    def test_class(self):
        class Foo: ...

        dep = Dependency(entity=Foo, contract=Foo, scope="container")
        assert dep.kind == EntityKind.Class

    def test_function(self):
        def foo(): ...

        dep = Dependency(entity=foo, contract=type(foo), scope="container")
        assert dep.kind == EntityKind.Function

    def test_instance(self):
        obj = object()
        dep = Dependency(entity=obj, contract=type(obj), scope="container")
        assert dep.kind == EntityKind.Instance


class TestCallableKind:
    def test_sync_function(self):
        def foo(): ...

        dep = Dependency(entity=foo, contract=type(foo), scope="container")
        assert dep.callable_kind == CallableKind.Sync

    def test_async_function(self):
        async def foo(): ...

        dep = Dependency(entity=foo, contract=type(foo), scope="container")
        assert dep.callable_kind == CallableKind.Async

    def test_class_is_sync(self):
        class Foo: ...

        dep = Dependency(entity=Foo, contract=Foo, scope="container")
        assert dep.callable_kind == CallableKind.Sync

    def test_async_method(self):
        class Foo:
            async def method(self): ...

        dep = Dependency(entity=Foo().method, contract=object, scope="container")
        assert dep.callable_kind == CallableKind.Async


class TestParameters:
    def test_extracts_typed_params(self):
        class Service: ...

        class Foo:
            def __init__(self, service: Service, count: int = 5): ...

        dep = Dependency(entity=Foo, contract=Foo, scope="container")
        params = {p.name: p for p in dep.parameters}

        assert "service" in params
        assert params["service"].type_annotation is Service
        assert params["service"].allows_none is False

        assert "count" in params
        assert params["count"].default == 5

    def test_skips_self_and_untyped_params(self):
        class Foo:
            def __init__(self, a, b: int = 1): ...

        dep = Dependency(entity=Foo, contract=Foo, scope="container")
        names = {p.name for p in dep.parameters}

        assert names == {"b"}

    def test_optional_param_allows_none(self):
        class Service: ...

        class Foo:
            def __init__(self, service: Optional[Service] = None): ...

        dep = Dependency(entity=Foo, contract=Foo, scope="container")
        params = {p.name: p for p in dep.parameters}

        assert params["service"].allows_none is True

    def test_union_pipe_optional(self):
        class Service: ...

        class Foo:
            def __init__(self, service: Service | None = None): ...

        dep = Dependency(entity=Foo, contract=Foo, scope="container")
        params = {p.name: p for p in dep.parameters}

        assert params["service"].allows_none is True


class TestInstanceContextManagerKind:
    def test_async_ctx_manager(self):
        class Resource:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

        inst = Instance(Resource(), CallableKind.Sync)
        assert inst.context_manager_kind == CallableKind.Async

    def test_sync_ctx_manager(self):
        class Resource:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        inst = Instance(Resource(), CallableKind.Sync)
        assert inst.context_manager_kind == CallableKind.Sync

    def test_no_ctx_manager(self):
        class Plain: ...

        inst = Instance(Plain(), CallableKind.Sync)
        assert inst.context_manager_kind is None


class TestInstance:
    def test_is_async_flag(self):
        inst = Instance(object(), CallableKind.Async)
        assert inst.is_async is True

        inst = Instance(object(), CallableKind.Sync)
        assert inst.is_async is False

    def test_entity_exposed(self):
        obj = object()
        inst = Instance(obj, CallableKind.Direct)
        assert inst.entity is obj
