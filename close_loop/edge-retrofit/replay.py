from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Effect:
    node: str
    effect: str
    via_edge: str
    direction: str
    reason: str


class RelationGraph:
    def __init__(self, document: dict[str, Any]):
        self.document = document
        self.nodes = {node["id"]: node for node in document["nodes"]}
        self.edges = document["edges"]
        self.outgoing: dict[str, list[dict[str, Any]]] = {}
        self.incoming: dict[str, list[dict[str, Any]]] = {}
        for edge in self.edges:
            self.outgoing.setdefault(edge["source"], []).append(edge)
            self.incoming.setdefault(edge["target"], []).append(edge)

    @classmethod
    def load(cls, path: Path) -> "RelationGraph":
        return cls(json.loads(path.read_text()))

    def propagate(self, event: dict[str, str]) -> list[Effect]:
        """Propagate one observed event using edge semantics only.

        Supported events:
        - source_changed: a node that owns/expresses a requirement changed.
        - target_revision_changed: a dependency target changed revision.
        - source_invalidated: a supporting source became invalid/stale.
        - source_stale: a supporting source became stale.
        - source_effective: a new source became current/effective.

        The replay deliberately separates edge writing direction from event
        propagation direction. For depends_on edges, revision change starts at
        the target and propagates backwards to the source Function.
        """
        event_type = event["type"]
        start = event["node"]
        effects: list[Effect] = []
        seen: set[tuple[str, str, str]] = set()
        queue: deque[tuple[str, str]] = deque([(start, event_type)])

        while queue:
            node, current_event = queue.popleft()

            if current_event in {"source_changed", "source_invalidated", "source_stale", "source_effective"}:
                edges = self.outgoing.get(node, [])
                direction = "forward"
            elif current_event == "target_revision_changed":
                edges = self.incoming.get(node, [])
                direction = "reverse"
            else:
                raise ValueError(f"unsupported event type: {current_event}")

            for edge in edges:
                effect = self._effect_for(edge, current_event, direction)
                if effect is None:
                    continue
                key = (effect.node, effect.effect, effect.via_edge)
                if key in seen:
                    continue
                seen.add(key)
                effects.append(effect)

                next_event = self._next_event(effect.effect)
                if next_event:
                    queue.append((effect.node, next_event))

        return effects

    def _effect_for(self, edge: dict[str, Any], event_type: str, direction: str) -> Effect | None:
        propagation = edge.get("propagation", {})
        edge_type = edge["edge_type"]

        if direction == "forward":
            mapping = {
                "source_changed": "on_source_change",
                "source_invalidated": "on_source_invalidated",
                "source_stale": "on_source_stale",
                "source_effective": "on_source_effective",
            }
            rule = propagation.get(mapping[event_type])
            if not rule:
                return None
            target = edge["target"]
        else:
            if edge_type != "depends_on":
                return None
            rule = propagation.get("on_target_revision_change")
            if not rule:
                return None
            target = edge["source"]

        normalized = self._normalize_effect(rule)
        return Effect(
            node=target,
            effect=normalized,
            via_edge=edge["id"],
            direction=direction,
            reason=edge.get("reason") or edge.get("claim") or edge_type,
        )

    @staticmethod
    def _normalize_effect(rule: str) -> str:
        lowered = rule.lower()
        if "superseded" in lowered:
            return "superseded"
        if "basis becomes stale" in lowered:
            return "basis_stale"
        if "effective state becomes stale" in lowered:
            return "stale"
        if "evidence becomes stale" in lowered:
            return "evidence_stale_rejudge"
        if "stale/rejudge" in lowered or "realign/rejudge" in lowered:
            return "stale_rejudge"
        if "rejudge" in lowered:
            return "rejudge"
        if "consumable" in lowered:
            return "accepted_consumable"
        return rule

    @staticmethod
    def _next_event(effect: str) -> str | None:
        if effect in {"stale", "stale_rejudge", "evidence_stale_rejudge", "basis_stale"}:
            return "source_stale"
        if effect == "superseded":
            return None
        return None


def replay(graph_path: Path, event: dict[str, str]) -> list[dict[str, str]]:
    graph = RelationGraph.load(graph_path)
    return [effect.__dict__ for effect in graph.propagate(event)]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("graph")
    parser.add_argument("event_type")
    parser.add_argument("node")
    args = parser.parse_args()

    print(json.dumps(replay(Path(args.graph), {"type": args.event_type, "node": args.node}), indent=2))
