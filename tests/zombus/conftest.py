import pytest


@pytest.fixture
def fresh_registry():
    from ext.zombus.registry import HandlerRegistry

    return HandlerRegistry()
