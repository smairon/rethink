from dataclasses import dataclass

from ext.zombus.aux.introspection import fqn
from ext.zombus.codex.errors import CycleError, NoHandlerError, UnknownMessageError
from ext.zombus.codex.types import Message
from ext.zombus.internals.descriptors import HandlerDescriptor
from ext.zombus.internals.uow import analyze_uow
from ext.zombus.registry import HandlerRegistry


@dataclass(frozen=True, slots=True)
class Node:
    message: type[Message]
    handlers: tuple[HandlerDescriptor, ...]
    auditors: tuple[HandlerDescriptor, ...]
    contexts: tuple[HandlerDescriptor, ...]


@dataclass(frozen=True, slots=True)
class Edge:
    source: type[Message]
    target: type[Message]


class MessageGraph:
    def __init__(self, registry: HandlerRegistry) -> None:
        all_descriptors = list(registry)
        messages = set()
        for d in all_descriptors:
            messages.add(d.message_type)
            messages.update(d.return_types)

        nodes_list = []
        for msg in messages:
            handlers = registry.handlers(msg)
            if not handlers:
                raise NoHandlerError(f"No handlers for message {msg}")
            nodes_list.append(Node(message=msg, handlers=tuple(handlers)))

        edges_set = set()
        for node in nodes_list:
            for handler in node.handlers:
                for ret in handler.return_types:
                    edges_set.add((node.message, ret))

        edges_list = [Edge(source=s, target=t) for s, t in edges_set]

        nodes_list.sort(key=lambda n: fqn(n.message))
        edges_list.sort(key=lambda e: (fqn(e.source), fqn(e.target)))

        self._check_cycles(nodes_list, edges_list)

        nodes_list = analyze_uow(tuple(nodes_list), tuple(edges_list))

        self._nodes = tuple(nodes_list)
        self._edges = tuple(edges_list)

    @property
    def nodes(self) -> tuple[Node, ...]:
        return self._nodes

    @property
    def edges(self) -> tuple[Edge, ...]:
        return self._edges

    def sub(self, message: type[Message]) -> MessageGraph:
        node_map = {n.message: n for n in self._nodes}
        if message not in node_map:
            raise UnknownMessageError(f"Message {message} not in graph")

        adj: dict[type[Message], list[type[Message]]] = {}
        for e in self._edges:
            adj.setdefault(e.source, []).append(e.target)

        reachable = set()
        stack = [message]
        while stack:
            m = stack.pop()
            if m in reachable:
                continue
            reachable.add(m)
            for child in adj.get(m, []):
                if child not in reachable:
                    stack.append(child)

        new_nodes = tuple(n for n in self._nodes if n.message in reachable)
        new_edges = tuple(
            e for e in self._edges if e.source in reachable and e.target in reachable
        )

        return self._from_parts(new_nodes, new_edges)

    @staticmethod
    def _check_cycles(nodes: list[Node], edges: list[Edge]) -> None:
        adj: dict[type[Message], list[type[Message]]] = {}
        for e in edges:
            adj.setdefault(e.source, []).append(e.target)

        color: dict[type[Message], int] = {n.message: 0 for n in nodes}

        for start in nodes:
            if color[start.message] != 0:
                continue
            stack = [(start.message, 0)]
            color[start.message] = 1
            path = [start.message]

            while stack:
                node, idx = stack[-1]
                children = adj.get(node, [])
                if idx < len(children):
                    child = children[idx]
                    stack[-1] = (node, idx + 1)
                    if color[child] == 1:
                        start_idx = path.index(child)
                        cycle_path = path[start_idx:] + [child]
                        raise CycleError(cycle_path)
                    elif color[child] == 0:
                        color[child] = 1
                        path.append(child)
                        stack.append((child, 0))
                else:
                    color[node] = 2
                    stack.pop()
                    path.pop()

    @classmethod
    def _from_parts(
        cls, nodes: tuple[Node, ...], edges: tuple[Edge, ...]
    ) -> MessageGraph:
        obj = cls.__new__(cls)
        new_nodes = analyze_uow(nodes, edges)
        obj._nodes = tuple(new_nodes)
        obj._edges = tuple(edges)
        return obj
