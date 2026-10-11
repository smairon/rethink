import pytest

from ext.zorge.registry import DependencyRegistry


@pytest.fixture
def registry() -> DependencyRegistry:
    return DependencyRegistry()
