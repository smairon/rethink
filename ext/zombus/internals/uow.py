# message_graph/internals/uow.py
from collections import deque
from dataclasses import replace


def analyze_uow(nodes, edges):
    # Reset all flags
    new_nodes = []
    for node in nodes:
        new_handlers = []
        for h in node.handlers:
            new_params = tuple(replace(p, begin=False, end=False) for p in h.parameters)
            new_handlers.append(replace(h, parameters=new_params))
        new_nodes.append(replace(node, handlers=tuple(new_handlers)))
    nodes = tuple(new_nodes)

    n = len(nodes)
    if n == 0:
        return nodes

    msg_to_idx = {node.message: i for i, node in enumerate(nodes)}

    succ = {i: [] for i in range(n)}
    pred = {i: [] for i in range(n)}
    indegree = [0] * n
    for edge in edges:
        s = msg_to_idx[edge.source]
        t = msg_to_idx[edge.target]
        succ[s].append(t)
        pred[t].append(s)
        indegree[t] += 1

    queue = deque([i for i in range(n) if indegree[i] == 0])
    topo_order = []
    while queue:
        i = queue.popleft()
        topo_order.append(i)
        for j in succ[i]:
            indegree[j] -= 1
            if indegree[j] == 0:
                queue.append(j)

    uow_types = set()
    for node in nodes:
        for h in node.handlers:
            for p in h.parameters:
                if p.kind == "uow":
                    uow_types.add(p.annotation)

    new_nodes_list = list(nodes)
    for P in uow_types:
        contains = [False] * n
        for i, node in enumerate(nodes):
            for h in node.handlers:
                if any(p.kind == "uow" and p.annotation == P for p in h.parameters):
                    contains[i] = True
                    break

        above = [False] * n
        for i in topo_order:
            for pred_idx in pred[i]:
                if contains[pred_idx] or above[pred_idx]:
                    above[i] = True
                    break

        below = [False] * n
        for i in reversed(topo_order):
            for succ_idx in succ[i]:
                if contains[succ_idx] or below[succ_idx]:
                    below[i] = True
                    break

        for i in range(n):
            if not contains[i]:
                continue
            begin = not above[i]
            end = not below[i]
            if begin and end:
                begin = False
                end = False

            node = new_nodes_list[i]
            new_handlers = []
            for h in node.handlers:
                new_params = []
                for p in h.parameters:
                    if p.kind == "uow" and p.annotation == P:
                        new_params.append(replace(p, begin=begin, end=end))
                    else:
                        new_params.append(p)
                new_handlers.append(replace(h, parameters=tuple(new_params)))
            new_nodes_list[i] = replace(node, handlers=tuple(new_handlers))

    return tuple(new_nodes_list)