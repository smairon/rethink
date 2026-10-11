"""Тесты взаимодействия вложенных Provider-ов и их жизненного цикла.

Ключевая идея: у каждого nested-провайдера собственный InstanceRegistry,
но всё, что относится к родительским scope-ам, хранится в родительских
registry — и, соответственно, закрывается родителем, а не ребёнком.
"""

import pytest

from ext.zorge.provider import Provider
from ext.zorge.registry import DependencyRegistry


@pytest.fixture
def provider(registry) -> Provider:
    return Provider(scope="container", dependency_registry=registry)


# ---------------------------------------------------------------------------
# Разрешение зависимостей во вложенных scope-ах
# ---------------------------------------------------------------------------


class TestNestedResolve:
    @pytest.mark.asyncio
    async def test_nested_provider_inside_context_manager(self, registry):
        class ContainerService: ...

        class RequestService: ...

        registry.register(
            ContainerService, scope="container", contract=ContainerService
        )
        registry.register(RequestService, scope="request", contract=RequestService)

        async with provider_ctx(registry) as container:
            request = container.nested("request")
            async with request:
                a = request.resolve(ContainerService)
                b = request.resolve(RequestService)

                assert isinstance(a.entity, ContainerService)
                assert isinstance(b.entity, RequestService)

    @pytest.mark.asyncio
    async def test_container_scope_shared_across_sibling_requests(self, registry):
        class Shared: ...

        registry.register(Shared, scope="container", contract=Shared)

        async with provider_ctx(registry) as container:
            req1 = container.nested("request")
            req2 = container.nested("request")

            async with req1, req2:
                a = req1.resolve(Shared)
                b = req2.resolve(Shared)

                # container-scope: один и тот же Instance, один и тот же entity
                assert a is b
                assert a.entity is b.entity

    @pytest.mark.asyncio
    async def test_request_scope_isolated_between_siblings(self, registry):
        class ReqRes: ...

        registry.register(ReqRes, scope="request", contract=ReqRes)

        async with provider_ctx(registry) as container:
            req1 = container.nested("request")
            req2 = container.nested("request")

            async with req1, req2:
                a = req1.resolve(ReqRes)
                b = req2.resolve(ReqRes)

                assert a is not b
                assert a.entity is not b.entity

    @pytest.mark.asyncio
    async def test_request_scope_cached_within_same_nested(self, registry):
        class ReqRes: ...

        registry.register(ReqRes, scope="request", contract=ReqRes)

        async with provider_ctx(registry) as container:
            request = container.nested("request")
            async with request:
                a = request.resolve(ReqRes)
                b = request.resolve(ReqRes)
                assert a is b

    @pytest.mark.asyncio
    async def test_request_dep_depends_on_container_dep(self, registry):
        class DB:
            def __init__(self):
                self.tag = "db"

        class Repo:
            def __init__(self, db: DB):
                self.db = db

        registry.register(DB, scope="container", contract=DB)
        registry.register(Repo, scope="request", contract=Repo)

        async with provider_ctx(registry) as container:
            req1 = container.nested("request")
            req2 = container.nested("request")

            async with req1, req2:
                r1 = req1.resolve(Repo).entity
                r2 = req2.resolve(Repo).entity

                # request-scoped: разные инстансы
                assert r1 is not r2
                # container-scoped: общий DB
                assert r1.db is r2.db

    @pytest.mark.asyncio
    async def test_three_level_nesting(self, registry):
        class A: ...

        class B: ...

        class C: ...

        registry.register(A, scope="container", contract=A)
        registry.register(B, scope="session", contract=B)
        registry.register(C, scope="request", contract=C)

        async with provider_ctx(registry) as container:
            session = container.nested("session")

            async with session:
                req1 = session.nested("request")
                req2 = session.nested("request")

                async with req1, req2:
                    # container-scope — общий для всех
                    assert req1.resolve(A) is req2.resolve(A)
                    # session-scope — общий между сессионными детьми
                    assert session.resolve(B) is req1.resolve(B)
                    assert req1.resolve(B) is req2.resolve(B)
                    # request-scope — изолирован
                    assert req1.resolve(C).entity is not req2.resolve(C).entity


# ---------------------------------------------------------------------------
# Жизненный цикл: что и когда закрывается
# ---------------------------------------------------------------------------


class TestNestedLifecycle:
    @pytest.mark.asyncio
    async def test_request_resource_closed_when_nested_exits(self, registry):
        events: list[str] = []

        class ReqRes:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                events.append("request-exit")

        registry.register(ReqRes, scope="request", contract=ReqRes)

        async with provider_ctx(registry) as container:
            request = container.nested("request")

            async with request:
                request.resolve(ReqRes)
                assert events == []  # ещё не закрыт

            # вышли из nested — request-ресурс закрыт
            assert events == ["request-exit"]

        # выход из root не должен закрывать повторно
        assert events == ["request-exit"]

    @pytest.mark.asyncio
    async def test_container_resource_closed_only_by_root(self, registry):
        events: list[str] = []

        class ContainerRes:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                events.append("container-exit")

        registry.register(ContainerRes, scope="container", contract=ContainerRes)

        async with provider_ctx(registry) as container:
            request = container.nested("request")

            async with request:
                # resolve идёт через nested, но scope = container,
                # значит instance попадёт в родительский registry
                request.resolve(ContainerRes)

            # nested-выход не должен закрыть container-ресурс
            assert events == []

        # а вот root при выходе — должен
        assert events == ["container-exit"]

    @pytest.mark.asyncio
    async def test_sync_and_async_context_managers_closed_in_nested(self, registry):
        events: list[str] = []

        class SyncRes:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                events.append("sync-exit")

        class AsyncRes:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                events.append("async-exit")

        registry.register(SyncRes, scope="request", contract=SyncRes)
        registry.register(AsyncRes, scope="request", contract=AsyncRes)

        async with provider_ctx(registry) as container:
            request = container.nested("request")

            async with request:
                request.resolve(SyncRes)
                request.resolve(AsyncRes)
                assert events == []

            # Оба ресурса закрыты; порядок не гарантируем
            assert set(events) == {"sync-exit", "async-exit"}

    @pytest.mark.asyncio
    async def test_sibling_requests_lifecycle_independent(self, registry):
        events: list[tuple[str, int]] = []
        counter = {"n": 0}

        class ReqRes:
            def __init__(self):
                self.id = counter["n"]
                counter["n"] += 1

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                events.append(("exit", self.id))

        registry.register(ReqRes, scope="request", contract=ReqRes)

        async with provider_ctx(registry) as container:
            req1 = container.nested("request")
            async with req1:
                req1.resolve(ReqRes)

            # первый закрыт сразу после своего выхода
            assert events == [("exit", 0)]

            req2 = container.nested("request")
            async with req2:
                req2.resolve(ReqRes)

            assert events == [("exit", 0), ("exit", 1)]

    @pytest.mark.asyncio
    async def test_plain_objects_do_not_break_nested_exit(self, registry):
        class Plain: ...

        registry.register(Plain, scope="request", contract=Plain)

        async with provider_ctx(registry) as container:
            request = container.nested("request")
            async with request:
                request.resolve(Plain)
            # дошли до сюда без исключений

    @pytest.mark.asyncio
    async def test_exception_inside_nested_still_closes_resources(self, registry):
        events: list[str] = []

        class ReqRes:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                events.append("exit")

        registry.register(ReqRes, scope="request", contract=ReqRes)

        async with provider_ctx(registry) as container:
            request = container.nested("request")
            with pytest.raises(RuntimeError, match="boom"):
                async with request:
                    request.resolve(ReqRes)
                    raise RuntimeError("boom")

            # Ресурс всё равно закрыт
            assert events == ["exit"]


# ---------------------------------------------------------------------------
# Изоляция кэша между независимыми деревьями провайдеров
# ---------------------------------------------------------------------------


class TestNestedIsolation:
    @pytest.mark.asyncio
    async def test_independent_root_providers_do_not_share_cache(self, registry):
        class Shared: ...

        registry.register(Shared, scope="container", contract=Shared)

        async with provider_ctx(registry) as p1:
            async with provider_ctx(registry) as p2:
                a = p1.resolve(Shared)
                b = p2.resolve(Shared)
                # У каждого корневого провайдера свой InstanceRegistry
                assert a.entity is not b.entity

    @pytest.mark.asyncio
    async def test_nested_after_root_resolve_shares_cache(self, registry):
        class Shared: ...

        registry.register(Shared, scope="container", contract=Shared)

        async with provider_ctx(registry) as container:
            # Сначала резолвим из корня
            root_instance = container.resolve(Shared)

            # Затем — из вложенного
            request = container.nested("request")
            async with request:
                nested_instance = request.resolve(Shared)

            # Оба указывают на один и тот же container-scoped объект
            assert root_instance is nested_instance


# ---------------------------------------------------------------------------
# helper
# ---------------------------------------------------------------------------


def provider_ctx(registry: DependencyRegistry) -> Provider:
    """Просто сахар: корневой Provider для использования в `async with`."""
    return Provider(scope="container", dependency_registry=registry)
