from msgspec import Struct

from ext.zorge import Container


class Message(Struct):
    pass


class Packet:
    def __init__(self, *messages: Message):
        self.messages = messages


class Zombus:
    def __init__(self, di_container: Container):
        self._di_container = di_container
