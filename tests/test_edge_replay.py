from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = ROOT / "close_loop" / "edge-retrofit" / "replay.py"
GRAPH_PATH = ROOT / "close_loop" / "edge-retrofit" / "relation-graph.v0.2.json"

spec = importlib.util.spec_from_file_location("edge_replay", REPLAY_PATH)
edge_replay = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(edge_replay)
RelationGraph = edge_replay.RelationGraph


class EdgeReplayTests(unittest.TestCase):
    def setUp(self):
        self.graph = RelationGraph.load(GRAPH_PATH)

    def effects(self, event_type: str, node: str):
        return self.graph.propagate({"type": event_type, "node": node})

    def test_owner_governance_change_flows_down_to_functions_then_execution_inspection(self):
        effects = self.effects("source_changed", "GN1-v2")
        by_node = {(effect.node, effect.effect) for effect in effects}

        self.assertIn(("FL-general-manager-final-approval", "stale_rejudge"), by_node)
        self.assertIn(("FL-authority-safe-review", "stale_rejudge"), by_node)
        self.assertIn(("EL-domain-rules", "impact_inspection_required"), by_node)
        self.assertIn(("EL-ledger-store", "impact_inspection_required"), by_node)
        self.assertIn(("EL-http", "impact_inspection_required"), by_node)
        self.assertIn(("EL-browser-ui", "impact_inspection_required"), by_node)

        # Downward propagation requests inspection; it does not declare the
        # implementation invalid before material facts are checked.
        execution_effects = [
            effect.effect for effect in effects if effect.node.startswith("EL-")
        ]
        self.assertEqual({"impact_inspection_required"}, set(execution_effects))

    def test_execution_revision_change_flows_up_only_to_direct_dependents_first(self):
        effects = self.effects("target_revision_changed", "EL-verification-environment")
        reverse = [effect for effect in effects if effect.direction == "reverse"]
        reverse_nodes = {effect.node for effect in reverse}

        self.assertEqual({"FL-durable", "FL-browser"}, reverse_nodes)
        self.assertTrue(all(effect.effect == "stale_rejudge" for effect in reverse))

    def test_invalidated_evidence_propagates_up_to_governance_and_effective_state(self):
        effects = self.effects("source_invalidated", "EV-ci-c0f01")
        by_node = {(effect.node, effect.effect) for effect in effects}

        self.assertIn(("FJ-c0f01", "stale_rejudge"), by_node)
        self.assertIn(("GOV-accept-c0f01", "basis_stale_rejudge"), by_node)
        self.assertIn(("ES-reference-sample", "stale_not_admitted"), by_node)

    def test_supersedes_retains_old_node_but_removes_it_from_current_planning(self):
        effects = self.effects("source_effective", "GN1-v2")
        matches = [effect for effect in effects if effect.node == "GN1-v1"]
        self.assertEqual(1, len(matches))
        self.assertEqual("superseded", matches[0].effect)
        self.assertIn("GN1-v1", self.graph.nodes)


if __name__ == "__main__":
    unittest.main()
