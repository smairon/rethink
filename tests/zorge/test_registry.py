from ext.zorge.entity import Instance
from ext.zorge.internal.types import CallableKind
from ext.zorge.registry import DependencyRegistry, InstanceRegistry


class TestDependencyRegistry:
    def test_register_with_explicit_contract(self):
        reg = DependencyRegistry()

        class Service: ...

        class IService: ...

        reg.register(Service, scope="container", contract=IService)

        dep = reg.get(IService)
        assert dep is not None
        assert dep.entity is Service
        assert dep.contract is IService
        assert dep.scope == "container"

    def test_register_infers_class_as_contract(self):
        reg = DependencyRegistry()

        class Service: ...

        reg.register(Service, scope="container")
        assert reg.get(Service) is not None
        assert reg.get(Service).contract is Service

    def test_get_unregistered_returns_none(self):
        reg = DependencyRegistry()

        class Service: ...

        assert reg.get(Service) is None

    def test_register_overwrites_previous(self):
        reg = DependencyRegistry()

        class Service: ...

        class OtherService: ...

        reg.register(Service, scope="container", contract=Service)
        reg.register(OtherService, scope="container", contract=Service)

        assert reg.get(Service).entity is OtherService


class TestInstanceRegistry:
    def test_register_and_get(self):
        reg = InstanceRegistry(scope="container")
        obj = object()
        reg.register(entity=obj, contract=object, callable_kind=CallableKind.Sync)

        inst = reg[object]
        assert isinstance(inst, Instance)
        assert inst.entity is obj

    def test_get_missing_returns_none(self):
        reg = InstanceRegistry(scope="container")
        assert reg[object] is None

    def test_iter_yields_pairs(self):
        reg = InstanceRegistry(scope="container")
        obj = object()
        reg.register(entity=obj, contract=object, callable_kind=CallableKind.Sync)

        pairs = list(reg)
        assert len(pairs) == 1
        assert pairs[0][0] is object
        assert pairs[0][1].entity is obj

    def test_parent_chain(self):
        parent = InstanceRegistry(scope="container")
        child = InstanceRegistry(scope="request", parent=parent)

        assert child.parent is parent
        assert parent.parent is None

    def test_close_clears_contents(self):
        reg = InstanceRegistry(scope="container")
        reg.register(entity=object(), contract=object, callable_kind=CallableKind.Sync)

        reg.close()

        assert reg[object] is None
        assert list(reg) == []
