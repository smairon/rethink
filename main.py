from dataclasses import dataclass

from ext.zombus.codex.types import Message
from ext.zombus.registry.actor import HandlerRegistry
from ext.zombus.runtime.graph import MessageGraph


class Command(Message):
    pass


class Event(Message):
    pass


@dataclass(frozen=True)
class CreateUser(Command):
    name: str


@dataclass(frozen=True)
class UserCreated(Event):
    id: int
    name: str


@dataclass(frozen=True)
class UpdateUser(Command):
    id: int
    name: str


@dataclass(frozen=True)
class UserUpdated(Event):
    id: int
    name: str


@dataclass(frozen=True)
class UserProcessed(Event):
    id: int


registry = HandlerRegistry()


@registry.register
def user_creation(message: CreateUser) -> UserCreated:
    return UserCreated(
        id=1,
        name=message.name,
    )


@registry.register
def user_updating(message: UpdateUser) -> UserUpdated:
    return UserUpdated(
        id=message.id,
        name=message.name,
    )


@registry.register
def user_update_writing(message: UserUpdated) -> None:
    pass


@registry.register
def user_processing(message: UserCreated) -> UserProcessed:
    return UserProcessed(
        id=message.id,
    )


@registry.register
async def user_storing(message: UserProcessed) -> None:
    return None


@registry.register
async def event_storing(message: UserProcessed) -> None:
    return None


def main():
    message_graph = MessageGraph(registry=registry)
    k = 1


if __name__ == "__main__":
    main()
