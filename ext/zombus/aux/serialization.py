# message_graph/serialization.py
import json

from ext.zombus.runtime.graph import MessageGraph

from .introspection import fqn


class JsonGraphSerializer:
    @staticmethod
    def serialize(graph: MessageGraph) -> dict:
        nodes_json = []
        for node in graph.nodes:
            handlers_json = []
            for handler in node.handlers:
                params_json = []
                for p in handler.parameters:
                    param = {
                        "name": p.name,
                        "annotation": fqn(p.annotation),
                        "kind": p.kind,
                    }
                    if p.kind == "uow":
                        if p.begin and p.end:
                            pass
                        else:
                            if p.begin:
                                param["begin"] = True
                            if p.end:
                                param["end"] = True
                    params_json.append(param)

                handler_json = {
                    "name": handler.func.__name__,
                    "qualname": handler.func.__qualname__,
                    "module": handler.func.__module__,
                    "is_async": handler.is_async,
                    "returns": sorted(fqn(t) for t in handler.return_types),
                    "parameters": params_json,
                }
                handlers_json.append(handler_json)

            node_json = {
                "id": node.message.__qualname__,
                "message": fqn(node.message),
                "handlers": handlers_json,
            }
            nodes_json.append(node_json)

        edges_json = []
        for edge in graph.edges:
            edges_json.append(
                {
                    "from": edge.source.__qualname__,
                    "to": edge.target.__qualname__,
                }
            )

        return {
            "nodes": nodes_json,
            "edges": edges_json,
        }

    def serialize_to_string(self, graph: MessageGraph) -> str:
        return json.dumps(self.serialize(graph), indent=2, ensure_ascii=False)
