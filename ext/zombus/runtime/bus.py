
from typing import Any
from collections.abc import Iterator
from ext.zorge import Container
from ext.zombus.runtime.graph import MessageGraph
from ext.zombus.codex.types import Message
from ext.zombus.codex.errors import MessageBusError




class Packet:
    def __init__(self, *messages: Message, **meta: Any) -> None:
        self._messages = self._ensure_messages(list(messages))
        self._meta = meta

    @staticmethod
    def _ensure_messages(messages: list[Message]) -> list[Message]:
        if len(messages) == 0:
            raise MessageBusError("Messages cannot be empty")
        if len(set([type(m) for m in messages])) != 1:
            raise MessageBusError("Messages must be of the same type")
        return messages

    def get_message_type(self) -> type[Message]:
        return type(self._messages[0])

    def __iter__(self) -> Iterator[Message]:
        return iter(self._messages)


class Zombus:
    def __init__(
        self,
        message_graph: MessageGraph,
        di_container: Container
    ):
        self._di_container = di_container
        self._message_graph = message_graph

    async def __call__(self, packet: Packet) -> list[Packet]:

