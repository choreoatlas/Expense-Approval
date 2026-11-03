"""Materialize Controller-authored, already-reviewed pilot judgments as data.

The explicit decisions/reasons below were authored after reading both raw runs
and the unchanged domain/store code. This is not an automatic validity engine.
"""
from datetime import datetime, timezone
import hashlib
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
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")

# Explicit authored judgments, not states inferred from an exit code or rule pass.
DECISIONS = {
 "FC-final-sequence": ("valid", "The submitted-revision GM attempt is rejected before any decision is inserted. Bob's first-stage decision records revision1 and leaves manager_pending; only Carol's later decision on revision1 records the GM role and changes that revision to approved. Both runs expose the actual HTTP bodies and complete table transitions. Domain ensure_can_review and store.decide place role/state checks before the transaction and derive the intermediate/final states by the actual actor role."),
 "FC-final-authority": ("valid", "All three final-role denials occur while the same expense is manager_pending, so they reach the intended authority rules. Unknown Mallory lacks assigned authority, employee Alice hits the own-expense prohibition, and approver Bob hits the GM-role requirement. Full before/after actors/expenses/revisions/decisions are unchanged. The authorized Carol succeeds. The source role lookup and ensure_can_review ordering explain these observations within seeded-local-role limits."),
 "FC-final-revision": ("valid", "Both the first-stage-reject and GM-reject branches preserve revision1, create revision2 as draft and resubmit it. A final decision on revision1 is rejected by the exact-current-revision check; a GM attempt on newly submitted revision2 is separately denied until Bob performs a new first-stage approval. Carol then approves revision2. This shows prior approvals do not float across either observed rework branch; store.decide compares latest revision before review/write and revise_rejected inserts a new row rather than altering the old content."),
 "FC-final-rework-history": ("valid", "The observed first-stage and GM rejection histories retain original revision, actor, actor_role, outcome and reason, followed by new revision2 and its fresh two-stage decisions. The browser sequence additionally retains rejected revisions1 and2 and the final approved revision3 with five ordered decisions. Revision insertion and ordered history queries in store.py account for preservation within this bounded selected path; no complete new judgment of the separate history/rework Functions is made."),
 "FC-final-invalid-nonmutation": ("valid", "All13 declared invalid actions return their actual400/403 errors with exact equality of complete actors/expenses/revisions/decisions snapshots: skipped stages, unknown/self/wrong-role final decisions, invalid outcome/reason, repeated final decision, edits/revisions of approved content, and stale/current-revision skip cases in both rework branches. The selected store/domain branches reject before INSERT/UPDATE. These bounded sequential observations do not claim concurrency/crash safety or all possible invalid inputs."),
 "FC-final-browser": ("valid", "Real Chromium executes draft edit/submit, first-stage rejection and revision2, GM rejection and revision3, then first-stage manager_pending and GM approved on revision3. Captured UI JSON, actual API responses and raw store snapshots agree, and visible history retains both rejected versions and role-labelled ordered decisions. This supplies the selected terminal-review path's UI support without asserting a full fresh FL-browser judgment or other browsers/accessibility."),
 "FC-final-restart": ("valid", "The first actual application process records an approved current revision with Bob/Carol ordered decisions and seeded actor roles, then is stopped/reaped. A different application PID starts on the same invocation-owned SQLite file; current response, history response and all business tables are byte-value equal before/after. Both processes are reaped and the temporary directory removed. This is normal local restart support for the selected path, not crash consistency, replication, backup recovery or a full new FL-durable judgment."),
}

decl = ROOT / "repos/expense/close_loop/onboarding"
conditions_raw = (decl / "conditions.json").read_bytes()
conditions = json.loads(conditions_raw)
composition_raw = (decl / "composition.json").read_bytes()
composition = json.loads(composition_raw)
assert set(DECISIONS) == {c["id"] for c in conditions["required_conditions"]}
for label, filename, package_path, origin in [
 ("A", "relay-observation-A.json", "observations-A.json", "Local exact-source invocation; command and original raw output retained"),
 ("B", "ci-observation-B.json", "observations-B.json", "GitHub push run41640672264/job125933074273/artifact13233051334; downloaded archive digest checked"),
]:
    raw = (ROOT / "evidence" / filename).read_bytes()
    observation = json.loads(raw)
    assert observation["completed"] and observation["source"]["product_git_revision"] == "57fa2b3551a0e8f9243241cb2604d03ca09b19d8"
    observed = {row["id"]: i for i, row in enumerate(observation["observations"])}
    execution = {row["implementation_entity"]: row for row in observation["execution_records"]}
    assessments = []
    for condition in conditions["required_conditions"]:
        ident = condition["id"]
        status, reason = DECISIONS[ident]
        carriers = [x for x in conditions["required_execution_support"] if ident == "FC-final-browser" or x != "EL-browser-ui"]
        item = {
          "assessment_id": "assessment:expense3:" + ident,
          "function_id": conditions["function_id"], "condition_id": ident,
          "condition_revision": rev(condition), "basis_snapshot": label,
          "actor": "agent:codex:expense3:controller-function-assessor",
          "judgment_kind": "explicit candidate Function-condition assessment; documentation pilot only",
          "status": status, "reason": reason,
          "scope": condition["scope"], "limits": conditions["limits"],
          "product_source": {"repository": "choreoatlas/Expense-Approval",
              "commit": observation["source"]["product_git_revision"], "tree": observation["source"]["product_git_tree"]},
          "basis_execution_records": [{"ref": x["id"], "revision": x["record_revision"],
               "pointer": "#/execution_records/" + str(observation["execution_records"].index(x))}
               for x in (execution[c] for c in carriers)],
          "basis_evidence": {"locator": package_path, "sha256": hashlib.sha256(raw).hexdigest(),
              "source_origin": origin, "run_id": observation["run_id"],
              "observation_pointers": ["#/observations/" + str(observed[x]) for x in condition["required_observations"]]},
          "requirement_sources": condition["requirement_sources"],
          "source_review": ["expense/domain.py#L69-L80", "expense/store.py#L132-L176", "expense/store.py#L178-L193"],
          "authority_effect": "none", "pilot_mode_change": False,
        }
        item["assessment_revision"] = rev(item)
        assessments.append(item)
    packet = {"format": "expense.explicit-condition-assessment-set.v0.1",
        "task_semantics": "condition-assessment pilot", "function_id": conditions["function_id"],
        "basis_snapshot": label, "run_id": observation["run_id"],
        "authored_at": datetime.now(timezone.utc).isoformat(),
        "conditions_sha256": hashlib.sha256(conditions_raw).hexdigest(),
        "predeclared_composition_sha256": hashlib.sha256(composition_raw).hexdigest(),
        "required_condition_ids": [c["id"] for c in conditions["required_conditions"]],
        "assessment_cardinality": "one per required condition for this basis snapshot; prior snapshots retained",
        "assessments": assessments,
        "scope": conditions["scope"], "limits": conditions["limits"],
        "basis_limits": observation["environment"], "authority_effect": "none",
    }
    save(ROOT / "inputs" / ("assessments-" + label + ".json"), packet)
    save(ROOT / "inputs" / ("composition-input-" + label + ".json"), {
        "operation": "compose", "assessments": assessments,
        "validation_policy": composition["validation_policy"]})
    print(json.dumps({"basis": label, "explicit_assessments": len(assessments), "actor": assessments[0]["actor"], "authority_effect": "none"}))
