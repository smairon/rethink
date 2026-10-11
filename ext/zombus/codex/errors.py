# message_graph/errors.py
class ZombusError(Exception):
    pass


class MessageGraphError(ZombusError):
    pass


class HandlerRegistrationError(MessageGraphError):
    pass


class DuplicateHandlerError(MessageGraphError):
    pass


class NoHandlerError(MessageGraphError):
    pass


class UnknownMessageError(MessageGraphError):
    pass


class CycleError(MessageGraphError):
    def __init__(self, path: list[type]):
        self.path = path
        super().__init__(f"Cycle detected: {path}")


class MessageBusError(ZombusError):
    pass


class MessageBusPacketError(MessageBusError):
    pass
