"""Graph interpreter: items flow from node to node, like n8n.

Every node receives a list of items (dicts) on an input port and returns
{output_port: [items]}. Empty outputs don't propagate. Two node types are handled
by the engine itself because they need state across executions:

- logic.loop: sends its input in batches on "item"; whatever comes back into the
  loop (or, if the body dead-ends, the batch itself) is collected, and when every
  batch is done the collected items leave on "done". The next batch is only sent
  once the body has fully settled, so bodies with several branches work.
- logic.merge: waits for all its connected inputs (or for the rest of the graph to
  settle) and outputs input "a" then input "b".
"""

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

MAX_STEPS = 20_000
SAMPLE_SIZE = 3


class NodeError(Exception):
    """A node failed: the run stops and the message is shown on the node."""


class WorkflowCancelled(Exception):
    pass


class WorkflowFailed(Exception):
    def __init__(self, node_id: str | None, message: str) -> None:
        super().__init__(message)
        self.node_id = node_id
        self.message = message


class EngineContext(Protocol):
    async def check_cancel(self) -> None: ...
    async def record(self, node_id: str, items_in: list, outputs: dict, error: str | None,
                     duration_ms: int) -> None: ...


Executor = Callable[[dict, list, Any], Awaitable[dict]]


class WorkflowEngine:
    def __init__(self, graph: dict, executors: dict[str, Executor], ctx: EngineContext) -> None:
        self.nodes = {n["id"]: n for n in graph.get("nodes", [])}
        self.executors = executors
        self.ctx = ctx
        self.out_edges: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
        self.in_ports: dict[str, set[str]] = defaultdict(set)
        for e in graph.get("edges", []):
            if e.get("source") in self.nodes and e.get("target") in self.nodes:
                self.out_edges[(e["source"], e.get("source_port", "main"))].append(
                    (e["target"], e.get("target_port", "main")))
                self.in_ports[e["target"]].add(e.get("target_port", "main"))
        self.queue: deque[tuple[str, str, list]] = deque()
        self.loops: dict[str, dict] = {}
        self.loop_order: list[str] = []
        self.merges: dict[str, dict[str, list]] = {}
        self._bodies: dict[str, set[str]] = {}

    # ------------------------------------------------------------------ public

    async def run(self, start_node_id: str, items: list[dict]) -> None:
        if start_node_id not in self.nodes:
            raise WorkflowFailed(None, "Le bloc de départ n'existe plus dans le workflow")
        self.queue.append((start_node_id, "main", items))
        steps = 0
        while True:
            if self.queue:
                steps += 1
                if steps > MAX_STEPS:
                    raise WorkflowFailed(None, f"Arrêt de sécurité : plus de {MAX_STEPS} exécutions de blocs")
                await self.ctx.check_cancel()
                node_id, port, batch = self.queue.popleft()
                await self._dispatch(node_id, port, batch)
                continue
            # the graph has settled: release a waiting merge or move a loop forward
            if await self._flush_merge():
                continue
            if await self._advance_loop():
                continue
            break

    # ---------------------------------------------------------------- dispatch

    async def _dispatch(self, node_id: str, port: str, items: list) -> None:
        node = self.nodes[node_id]
        t = node["type"]
        if t == "logic.loop":
            await self._loop_input(node, items)
        elif t == "logic.merge":
            state = self.merges.setdefault(node_id, {})
            state.setdefault(port, []).extend(items)
            if set(state) >= self.in_ports[node_id]:
                await self._run_merge(node_id)
        else:
            await self._execute(node, items)

    async def _execute(self, node: dict, items: list) -> None:
        executor = self.executors.get(node["type"])
        if executor is None:
            raise WorkflowFailed(node["id"], f"Type de bloc non pris en charge : {node['type']}")
        started = time.monotonic()
        try:
            outputs = await executor(node, items, self.ctx)
        except (WorkflowCancelled, WorkflowFailed):
            raise
        except Exception as exc:  # any node failure stops the run, shown on the node
            message = str(exc) or exc.__class__.__name__
            await self.ctx.record(node["id"], items, {}, message, _ms(started))
            raise WorkflowFailed(node["id"], message) from exc
        await self.ctx.record(node["id"], items, outputs, None, _ms(started))
        self._emit(node["id"], outputs)

    def _emit(self, node_id: str, outputs: dict) -> None:
        for port, items in outputs.items():
            if not items:
                continue
            for target, target_port in self.out_edges[(node_id, port)]:
                self.queue.append((target, target_port, items))

    # ------------------------------------------------------------------ merge

    async def _run_merge(self, node_id: str) -> None:
        state = self.merges.pop(node_id, {})
        merged = state.get("a", []) + state.get("b", [])
        await self.ctx.record(node_id, merged, {"main": merged}, None, 0)
        self._emit(node_id, {"main": merged})

    async def _flush_merge(self) -> bool:
        if not self.merges:
            return False
        # inside an active loop, settle merges of that loop's body first
        active = self._innermost_loop()
        candidates = list(self.merges)
        if active:
            body = self._body(active)
            inside = [m for m in candidates if m in body]
            if not inside:
                return False
            candidates = inside
        await self._run_merge(candidates[0])
        return True

    # ------------------------------------------------------------------- loop

    def _body(self, loop_id: str) -> set[str]:
        if loop_id not in self._bodies:
            seen: set[str] = set()
            stack = [t for t, _ in self.out_edges[(loop_id, "item")]]
            while stack:
                n = stack.pop()
                if n in seen or n == loop_id:
                    continue
                seen.add(n)
                for (src, _port), targets in self.out_edges.items():
                    if src == n:
                        stack.extend(t for t, _ in targets)
            self._bodies[loop_id] = seen
        return self._bodies[loop_id]

    def _innermost_loop(self) -> str | None:
        for loop_id in reversed(self.loop_order):
            if loop_id in self.loops:
                return loop_id
        return None

    async def _loop_input(self, node: dict, items: list) -> None:
        state = self.loops.get(node["id"])
        if state is not None:  # an iteration coming back from the body
            state["results"].extend(items)
            state["returned"] = True
            return
        try:
            size = max(1, int((node.get("config") or {}).get("batch_size", 1)))
        except (TypeError, ValueError):
            size = 1
        self.loops[node["id"]] = {"pending": list(items), "results": [], "batch": None,
                                  "returned": False, "size": size, "iterations": 0, "in": len(items)}
        self.loop_order.append(node["id"])
        await self._next_batch(node["id"])

    async def _next_batch(self, loop_id: str) -> None:
        state = self.loops[loop_id]
        body_targets = self.out_edges[(loop_id, "item")]
        while state["pending"]:
            batch = state["pending"][: state["size"]]
            state["pending"] = state["pending"][state["size"]:]
            state["iterations"] += 1
            if not body_targets:  # nothing in the loop: items go straight to "done"
                state["results"].extend(batch)
                continue
            state["batch"], state["returned"] = batch, False
            self._emit(loop_id, {"item": batch})
            return
        done = state["results"]
        del self.loops[loop_id]
        await self.ctx.record(loop_id, [None] * state["in"],
                              {"item": [None] * state["iterations"], "done": done}, None, 0)
        self._emit(loop_id, {"done": done})

    async def _advance_loop(self) -> bool:
        loop_id = self._innermost_loop()
        if loop_id is None:
            return False
        state = self.loops[loop_id]
        if not state["returned"] and state["batch"]:
            # the body ended without coming back: its input is the iteration result
            state["results"].extend(state["batch"])
        state["batch"] = None
        await self._next_batch(loop_id)
        return True


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def sample(items: list, n: int = SAMPLE_SIZE) -> list:
    return [i for i in items[:n] if i is not None]
