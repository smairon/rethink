import logging

from ext.zorge.container import Container
from ext.zorge.registry import DependencyRegistry

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = ["Container", "DependencyRegistry"]
