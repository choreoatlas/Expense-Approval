"""Build explicit candidate relation inputs; existing owner computes effects."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "management-owner-snapshot"))
from close_loop_contract_core import compute_digest

def rev(value):
    return "sha256:" + compute_digest(value, excluded_field="__no_excluded_field__")

def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, ensure_ascii=False, indent=2)
        stream.write("\n")

sets, paths, runs = {}, {}, {}
for label, filename in [("A", "relay-observation-A.json"), ("B", "ci-observation-B.json")]:
    packet = json.loads((ROOT / f"inputs/assessments-{label}.json").read_bytes())
    owner = json.loads((ROOT / f"outputs/composition-owner-{label}.json").read_bytes())
    assert {x["condition_id"] for x in packet["assessments"]} == set(packet["required_condition_ids"])
    assert len(packet["assessments"]) == len(packet["required_condition_ids"]) == 7
    sets[label] = packet
    runs[label] = json.loads((ROOT / "evidence" / filename).read_bytes())
    result = {"result_id": "function-result:expense3:FL-general-manager-final-approval",
       "record_kind": "explicit candidate Function result; documentation pilot only",
       "function_id": packet["function_id"], "basis_snapshot": label,
       "upstream_governance_need": "GN1", "source_commit": "57fa2b3551a0e8f9243241cb2604d03ca09b19d8",
       "scope": packet["scope"], "limits": packet["limits"],
       "actor": "agent:codex:expense3:controller-function-assessor",
       "assessment_refs": [{"id": x["assessment_id"], "revision": x["assessment_revision"]} for x in packet["assessments"]],
       "complete_condition_set_reviewed": True, "one_assessment_per_condition_for_this_basis": True,
       "composition_declaration_sha256": packet["predeclared_composition_sha256"],
       "composition_input": f"composition-input-{label}.json",
       "composition_owner_output": f"composition-owner-{label}.json",
       "path_state": owner["output"]["state_combination_output"],
       "authority_effect": "none", "currentness": "not_checked", "allowed": False,
       "pilot_mode_change": False,
    }
    result["result_revision"] = rev(result)
    paths[label] = result
    save(ROOT / f"outputs/function-result-{label}.json", result)

execution = {label: {x["implementation_entity"]: x for x in runs[label]["execution_records"]} for label in ["A", "B"]}
cases = []
for a, b in zip(sets["A"]["assessments"], sets["B"]["assessments"]):
    assert a["condition_id"] == b["condition_id"]
    for record in a["basis_execution_records"]:
        carrier = record["ref"].split("/")[-1]
        old, new = execution["A"][carrier], execution["B"][carrier]
        relation = {"edge_id": "candidate-edge:expense3:" + a["condition_id"] + ":" + carrier,
            "edge_type": "depends_on", "source_id": a["assessment_id"],
            "source_revision": a["assessment_revision"], "target_id": carrier,
            "target_revision": old["record_revision"], "propagation_rule": "rejudge_on_target_change",
            "scope": a["scope"], "actor": a["actor"],
            "basis_record_ref": old["id"], "selected_new_basis_record_ref": new["id"],
            "limits": "Candidate selected execution-loop basis context only; not a canonical edge or live current-state query"}
        cases.append({"id": a["condition_id"] + "/" + carrier + "/changed-basis",
            "relation": relation, "source_revision": a["assessment_revision"],
            "target_current_revision": new["record_revision"], "expected_state": "requires_rejudge"})
    relation = {"edge_id": "candidate-edge:expense3:path:" + a["condition_id"],
        "edge_type": "composes", "source_id": paths["A"]["result_id"],
        "source_revision": paths["A"]["result_revision"], "target_id": a["assessment_id"],
        "target_revision": a["assessment_revision"], "propagation_rule": "stale_on_target_change",
        "scope": a["scope"], "actor": a["actor"], "limits": "Candidate replay only; no relation writes"}
    cases.append({"id": a["condition_id"] + "/composition-changed-assessment",
        "relation": relation, "source_revision": paths["A"]["result_revision"],
        "target_current_revision": b["assessment_revision"], "expected_state": "stale"})

a = sets["A"]["assessments"][0]
cases.append({"id": "unchanged-condition-definition-control", "source_revision": a["assessment_revision"],
    "target_current_revision": a["condition_revision"], "expected_state": "revalidated",
    "relation": {"edge_id": "candidate-edge:expense3:unchanged-condition", "edge_type": "depends_on",
        "source_id": a["assessment_id"], "source_revision": a["assessment_revision"],
        "target_id": a["condition_id"], "target_revision": a["condition_revision"],
        "propagation_rule": "rejudge_on_target_change"}})
save(ROOT / "inputs/change-effects-input.json", {"operation": "change_effects", "cases": cases,
    "replay_semantics": "Offline effect replay using two real event bases; selected B is explicit context, not global current state",
    "execution_basis_identity": "Stable existing EL carrier identity, with each selected actual run record as that loop's basis revision",
    "authority_effect": "none"})
print(json.dumps({"candidate_relation_cases": len(cases), "assessment_basis_changes": sum(x["expected_state"] == "requires_rejudge" for x in cases), "composition_changes": 7, "unchanged_control": 1}))
