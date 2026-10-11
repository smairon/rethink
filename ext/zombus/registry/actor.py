import inspect
import typing
from collections.abc import Callable, Iterable, Iterator

from ext.zombus.aux import introspection
from ext.zombus.codex.errors import DuplicateHandlerError, HandlerRegistrationError
from ext.zombus.codex.types import Message
from ext.zombus.internals.descriptors import HandlerDescriptor, ParameterDescriptor


class HandlerRegistry:
    def __init__(self):
        self._handlers_by_message: dict[type[Message], list[HandlerDescriptor]] = {}
        self._descriptors: list[HandlerDescriptor] = []

    def register(self, func: Callable) -> Callable:
        try:
            hints = typing.get_type_hints(func)
        except Exception as e:
            raise HandlerRegistrationError(
                f"Failed to resolve annotations for {func}: {e}"
            ) from e

        if introspection.is_generator_handler(func):
            raise HandlerRegistrationError(f"Generator handler {func} is not allowed")

        sig = inspect.signature(func)
        parameters = []
        uow_types = set()
        message_type: type[Message] | None = None
        for name, param in sig.parameters.items():
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                raise HandlerRegistrationError(
                    "VAR_POSITIONAL and VAR_KEYWORD are not allowed"
                )
            if name not in hints:
                raise HandlerRegistrationError(
                    f"Missing annotation for parameter {name}"
                )
            ann = hints[name]
            if introspection.is_message_param(ann):
                if message_type is not None:
                    raise HandlerRegistrationError(
                        "Expected exactly one Message parameter"
                    )
                kind = "message"
                message_type = ann
                parameters.append(
                    ParameterDescriptor(name=name, annotation=ann, kind=kind)
                )
            else:
                if introspection.is_context_manager(ann):
                    if introspection.is_builtin(ann):
                        raise HandlerRegistrationError(
                            f"Builtin type {ann} cannot be UoW"
                        )
                    kind = "uow"
                    if ann in uow_types:
                        raise HandlerRegistrationError(
                            f"Duplicate UoW type {ann} in handler {func}"
                        )
                    uow_types.add(ann)
                elif introspection.is_protocol(ann):
                    kind = "other"
                else:
                    raise HandlerRegistrationError(
                        f"Parameter {name} of {func} is neither context manager nor Protocol"
                    )
                parameters.append(
                    ParameterDescriptor(name=name, annotation=ann, kind=kind)
                )

        if message_type is None:
            raise HandlerRegistrationError(f"Message type not specified for {func}")

        if "return" not in hints:
            raise HandlerRegistrationError(f"Missing return annotation for {func}")
        return_types = introspection.unwrap_return_types(hints["return"])

        is_async = introspection.is_async_handler(func)

        descriptor = HandlerDescriptor(
            func=func,
            message_type=message_type,
            return_types=return_types,
            parameters=tuple(parameters),
            is_async=is_async,
        )

        existing_list = self._handlers_by_message.get(message_type, [])
        for existing in existing_list:
            if existing.func is func:
                raise DuplicateHandlerError(
                    f"Handler {func} already registered for {message_type.__name__}"
                )
        existing_list.append(descriptor)
        self._handlers_by_message[message_type] = existing_list
        self._descriptors.append(descriptor)
        return func

    def actors(self, message_type: type[Message]) -> list[HandlerDescriptor]:
        return list(self._handlers_by_message.get(message_type, []))

    def auditors(self, message_type: type[Message]) -> list[HandlerDescriptor]:
        return list(self._handlers_by_message.get(message_type, []))

    def contexts(self, message_type: type[Message]) -> list[HandlerDescriptor]:
        return list(self._handlers_by_message.get(message_type, []))

    def messages(self) -> Iterable[type[Message]]:
        return self._handlers_by_message.keys()

    def __iter__(self) -> Iterator[HandlerDescriptor]:
        return iter(self._descriptors)
