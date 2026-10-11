from ext.zorge.container import Container
from ext.zorge.registry import DependencyRegistry


class TestContainer:
    def test_provider_resolves(self):
        registry = DependencyRegistry()

        class Service: ...

        registry.register(Service, scope="container", contract=Service)

        container = Container(registry)
        provider = container.provider()

        result = provider.resolve(Service)
        assert isinstance(result.entity, Service)

    def test_custom_root_scope(self):
        registry = DependencyRegistry()

        class Service: ...

        registry.register(Service, scope="app", contract=Service)

        container = Container(registry, root_scope="app")
        provider = container.provider()

        result = provider.resolve(Service)
        assert isinstance(result.entity, Service)

    def test_each_provider_is_fresh(self):
        registry = DependencyRegistry()

        class Service: ...

        registry.register(Service, scope="container", contract=Service)

        container = Container(registry)
        p1 = container.provider()
        p2 = container.provider()

        a = p1.resolve(Service)
        b = p2.resolve(Service)
        # Каждый корневой Provider имеет свой InstanceRegistry,
        # поэтому инстансы независимы.
        assert a.entity is not b.entity

    def test_registry_shared_between_providers(self):
        registry = DependencyRegistry()

        class Service: ...

        registry.register(Service, scope="container", contract=Service)

        container = Container(registry)
        p1 = container.provider()
        p2 = container.provider()

        assert p1._dependency_registry is p2._dependency_registry
