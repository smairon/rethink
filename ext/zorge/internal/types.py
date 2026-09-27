import typing
from dataclasses import dataclass
from enum import StrEnum


class CallableKind(StrEnum):
    Sync = "sync"
    Async = "async"
    Direct = "direct"


class EntityKind(StrEnum):
    Class = "class"
    Function = "function"
    Instance = "instance"


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    type_annotation: typing.Any
    default: typing.Any
    allows_none: bool
    annotated_metadata: tuple[typing.Any, ...] = ()


type EntityType = type[typing.Any]
type InstanceType = object
type ContractType = type[typing.Any]
type NoValue = object
type ScopeType = str
