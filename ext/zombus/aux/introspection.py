# message_graph/internals/introspection.py
import inspect
import types
import typing
from collections.abc import Collection, Iterable, Sequence

from ext.zombus.codex.errors import HandlerRegistrationError
from ext.zombus.codex.types import Message


def get_type_hints_safe(func):
    try:
        return typing.get_type_hints(func)
    except Exception as e:
        raise HandlerRegistrationError(
            f"Failed to resolve annotations for {func}: {e}"
        ) from e


def is_context_manager(t):
    return (hasattr(t, "__enter__") and hasattr(t, "__exit__")) or (
        hasattr(t, "__aenter__") and hasattr(t, "__aexit__")
    )


def is_builtin(t):
    return getattr(t, "__module__", None) == "builtins"


def is_protocol(t):
    if not isinstance(t, type):
        return False
    if t is typing.Protocol:
        return False
    return typing.Protocol in t.__mro__


def is_async_handler(func):
    return inspect.iscoroutinefunction(func)


def is_generator_handler(func):
    return inspect.isgeneratorfunction(func) or inspect.isasyncgenfunction(func)


def fqn(t):
    return f"{t.__module__}.{t.__qualname__}"


def is_message_param(ann: type):
    if not isinstance(ann, type) or not issubclass(ann, Message):
        return False
    if is_context_manager(ann):
        raise HandlerRegistrationError(
            f"Message type {ann} cannot be a context manager"
        )
    return True


def get_message_param(func, hints=None):
    if hints is None:
        hints = get_type_hints_safe(func)
    sig = inspect.signature(func)
    message_params = []
    for name, param in sig.parameters.items():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            raise HandlerRegistrationError(
                "VAR_POSITIONAL and VAR_KEYWORD are not allowed"
            )
        ann = hints.get(name)
        if ann is None:
            continue
        if isinstance(ann, type) and issubclass(ann, Message):
            message_params.append((param, ann))
    if len(message_params) != 1:
        raise HandlerRegistrationError(
            f"Expected exactly one Message parameter, got {len(message_params)}"
        )
    param, ann = message_params[0]
    if is_context_manager(ann):
        raise HandlerRegistrationError(
            f"Message type {ann} cannot be a context manager"
        )
    return param


def get_other_params(func, hints=None, message_param=None):
    if hints is None:
        hints = get_type_hints_safe(func)
    if message_param is None:
        message_param = get_message_param(func, hints)
    sig = inspect.signature(func)
    others = []
    for name, param in sig.parameters.items():
        if param is message_param:
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            raise HandlerRegistrationError(
                "VAR_POSITIONAL and VAR_KEYWORD are not allowed"
            )
        if name not in hints:
            raise HandlerRegistrationError(f"Missing annotation for parameter {name}")
        others.append(param)
    return others


CONTAINER_ORIGINS = {
    list,
    set,
    frozenset,
    tuple,
    Sequence,
    Iterable,
    Collection,
}


def unwrap_return_types(annotation):
    return _unwrap(annotation, 0)


def _unwrap(ann, depth):
    if ann is None or ann is type(None):
        return frozenset()
    origin = typing.get_origin(ann)
    if origin in (typing.Union, types.UnionType):
        result = set()
        for arg in typing.get_args(ann):
            result |= _unwrap(arg, depth)
        return frozenset(result)
    if origin in CONTAINER_ORIGINS:
        if depth > 0:
            raise HandlerRegistrationError("Nested containers are not allowed")
        args = typing.get_args(ann)
        if origin is tuple and len(args) == 2 and args[1] is Ellipsis:
            return _unwrap(args[0], depth + 1)
        result = set()
        for arg in args:
            result |= _unwrap(arg, depth + 1)
        return frozenset(result)
    if isinstance(ann, type):
        if issubclass(ann, Message):
            return frozenset({ann})
        else:
            raise HandlerRegistrationError(
                f"Return type {ann} is not a Message subclass"
            )
    if origin is not None:
        raise HandlerRegistrationError(
            f"Unsupported generic alias in return type: {ann}"
        )
    raise HandlerRegistrationError(f"Unsupported return type annotation: {ann}")
