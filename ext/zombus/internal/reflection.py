import inspect
import types
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import reduce
from operator import or_
from typing import Annotated, Any, Literal, Union, get_args, get_origin, get_type_hints


@dataclass(frozen=True)
class ParameterDescriptor:
    name: str
    parameter_type: Any
    is_container: bool
    annotated_metadata: list[Any]
    allows_none: bool
    parameter_kind: Literal["positional", "keyword"]


def parse_callable_signature(callback: Any) -> dict[str, ParameterDescriptor]:
    """Return descriptors for every parameter accepted by *callback*."""
    signature = inspect.signature(callback)
    annotations = _get_annotations(callback)

    return {
        name: _describe_parameter(
            name, parameter, annotations.get(name, parameter.annotation)
        )
        for name, parameter in signature.parameters.items()
    }


def _get_annotations(callback: Any) -> dict[str, Any]:
    annotation_source = callback
    if inspect.isclass(callback):
        annotation_source = callback.__init__
    elif not (inspect.isfunction(callback) or inspect.ismethod(callback)):
        annotation_source = callback.__call__

    try:
        return get_type_hints(annotation_source, include_extras=True)
    except NameError, TypeError:
        return {}


def _describe_parameter(
    name: str, parameter: inspect.Parameter, annotation: Any
) -> ParameterDescriptor:
    metadata: list[Any] = []
    annotation, metadata = _unwrap_annotated(annotation, metadata)
    annotation, allows_none = _unwrap_none(annotation)
    annotation, metadata = _unwrap_annotated(annotation, metadata)

    origin = get_origin(annotation)
    is_container = origin in (Sequence, Iterable)
    parameter_type = get_args(annotation)[0] if is_container else annotation
    parameter_type, metadata = _unwrap_annotated(parameter_type, metadata)
    parameter_type, element_allows_none = _unwrap_none(parameter_type)

    is_keyword = parameter.kind in (
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.VAR_KEYWORD,
    )
    return ParameterDescriptor(
        name=name,
        parameter_type=parameter_type,
        is_container=is_container,
        annotated_metadata=metadata,
        allows_none=allows_none or element_allows_none,
        parameter_kind="keyword" if is_keyword else "positional",
    )


def _unwrap_annotated(annotation: Any, metadata: list[Any]) -> tuple[Any, list[Any]]:
    while get_origin(annotation) is Annotated:
        annotation, *new_metadata = get_args(annotation)
        metadata.extend(new_metadata)
    return annotation, metadata


def _unwrap_none(annotation: Any) -> tuple[Any, bool]:
    origin = get_origin(annotation)
    if origin not in (Union, types.UnionType):
        return annotation, False

    arguments = get_args(annotation)
    non_none_arguments = tuple(
        argument for argument in arguments if argument is not type(None)
    )
    allows_none = len(non_none_arguments) != len(arguments)
    if not allows_none:
        return annotation, False
    if len(non_none_arguments) == 1:
        return non_none_arguments[0], True
    return reduce(or_, non_none_arguments), True
