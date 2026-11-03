"""Supply explicit authored data to the unchanged installed public assembler."""
from copy import deepcopy
from datetime import datetime, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "management-owner-snapshot"))
from close_loop_contract_core import compute_digest

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def raw(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw(value))

inputs, outputs, evidence = [ROOT / x for x in ("inputs", "outputs", "evidence")]
delivery = json.loads((outputs / "source-delivery.json").read_bytes())
profile = json.loads((inputs / "profile.json").read_bytes())
source = json.loads((evidence / "product-source.json").read_bytes())
observations = json.loads((evidence / "ci-observation-B.json").read_bytes())
definition = json.loads((ROOT / "repos/expense/close_loop/attempt-1/function-model.v0.2.json").read_bytes())
definitions = {x["id"]: x for x in definition["functions"]}
pilot = json.loads((outputs / "function-result-B.json").read_bytes())
scope = "Expense source and explicit judgment inspection; final-review pilot result attached within its original scope"
rows = []
for fid in profile["functions"]:
    original = definitions[fid]
    selected = fid == pilot["function_id"]
    basis = {"product_commit": source["commit"],
        "profile_sha256": sha((inputs / "profile.json").read_bytes()),
        "candidate_sha256": delivery["candidate"]["candidate_sha256"],
        "material_sha256": delivery["candidate"]["material_sha256"],
        "slice_ids": profile["coverage"][fid],
        "execution_records": [{"ref": x["id"], "revision": x["record_revision"]}
            for x in observations["execution_records"] if x["implementation_entity"] in original["required_execution_support"]],
        "evidence_refs": ["observations-B.json#sha256=" + sha((evidence / "ci-observation-B.json").read_bytes()),
                          "https://github.com/choreoatlas/Expense-Approval/actions/runs/41640672264"],
    }
    limits = [original["limits"], "Current outer scope is assembly inspection, not replacement of the original Function scope",
              "No new Governance/admission/effective-state/downstream permission", "Only the selected final-review Function has a new candidate assessment set"]
    statement = {"function_id": fid,
        "target_path_ref": "repository:github:choreoatlas/Expense-Approval:function:" + fid,
        "judgment_id": "inspection-statement:expense3:" + fid,
        "revision": "authored-expense3-inspection-v0.1", "assessor": "agent:codex:expense3:controller-function-assessor",
        "state": "candidate_pilot_result_attached" if selected else "not_rejudged",
        "reason": ("The separately authored seven-condition candidate result is attached verbatim with its own final-review scope, limitations and basis. The outer state denotes an available referenced pilot result, not a new canonical path_state or the assembler's judgment."
            if selected else "This original Function definition and historical scope are preserved. The new source/CI material is available, but this Function is explicitly not rejudged by this inspection."),
        "scope": scope, "limits": limits, "basis": basis,
        "original_path_definition": deepcopy(original),
        "scope_interpretation": "The outer scope describes only this common assembly/inspection; original_path_definition.scope is unchanged",
        "historical_acceptance_ref": "https://github.com/choreoatlas/Expense-Approval/issues/1#issuecomment-5571375864",
    }
    if selected:
        statement["referenced_pilot_result"] = deepcopy(pilot)
    authored = raw({"statement": statement})
    name = "authoring/" + fid + ".json"
    with (inputs / name).parent.mkdir(parents=True, exist_ok=True) or (inputs / name).open("xb") as stream:
        stream.write(authored)
    row = {k: deepcopy(statement[k]) for k in ["function_id", "target_path_ref", "judgment_id", "revision", "assessor", "state", "reason", "scope", "limits", "basis"]}
    row["original"] = {"statement": deepcopy(statement)}
    row["provenance"] = {"kind": "authored", "ref": name, "revision": statement["revision"],
        "sha256": sha(authored), "bytes_base64": base64.b64encode(authored).decode(), "pointer": "/statement"}
    rows.append(row)
judgments = {"schema": "commercial.explicit-function-judgments.v0.1", "judgments": rows}
save(inputs / "judgments.json", judgments)
example = json.loads((ROOT / "repos/commercial/examples/source_delivery_candidate_v0_1/todo2/evaluation_request.json").read_bytes())
request = {"schema": example["schema"], "request_id": "expense3-frozen-source-and-pilot-inspection",
    "request_revision": "v0.1", "subject": profile["subject"], "subject_ref": profile["subject_ref"],
    "governance_domain": profile["governance_domain"], "requested_scope": scope,
    "limits": ["Source/CI and explicit statements only; seven nonselected Functions not rejudged",
        "Pilot scope_limited result is a separately authored candidate, not recomputed by this assembler",
        "Source consistency does not establish provider authenticity/freshness or new business permission"],
    "product": {"repository": source["repository"], "commit": source["commit"], "tree": source["tree"]},
    "profile_sha256": sha((inputs / "profile.json").read_bytes()),
    "acquisition_request_sha256": sha((inputs / "acquisition-request.json").read_bytes()),
    "delivery_sha256": sha((outputs / "source-delivery.json").read_bytes()),
    "candidate_sha256": delivery["candidate"]["candidate_sha256"], "material_sha256": delivery["candidate"]["material_sha256"],
    "ci": {"run_id": source["ci_run"], "job_id": source["ci_job"], "job_name": "test", "run_attempt": source["ci_attempt"]},
    "functions": [{"function_id": x["function_id"], "target_path_ref": x["target_path_ref"],
        "scope": x["scope"], "limits": x["limits"], "slice_ids": x["basis"]["slice_ids"],
        "judgment_id": x["judgment_id"], "judgment_revision": x["revision"],
        "judgment_sha256": compute_digest(x, excluded_field="__no_excluded_field__")} for x in rows],
    "assembly": {"task_id": "Expense-Approval#3", "actor": "agent:codex:expense3:assembly",
        "revision": "expense3-new-inspection-assembly-v0.1"},
    "producer": example["producer"], "authority_boundary": example["authority_boundary"],
}
save(inputs / "evaluation-request.json", request)

launcher = '''import importlib.metadata as m,sys,json,os
def audit(event,args):
 if event in {'socket.connect','socket.bind','socket.getaddrinfo','sqlite3.connect','os.system','subprocess.Popen'}:
  with open(os.environ['EXPENSE_ASSEMBLY_AUDIT'],'a') as s:s.write(json.dumps({'event':event,'denied':True})+'\\n')
  raise RuntimeError('ASSEMBLY_OPERATION_PROHIBITED:'+event)
sys.addaudithook(audit)
sys.argv=['commercial-source-delivery-candidate']+sys.argv[1:]
matches=list(m.entry_points(group='console_scripts',name='commercial-source-delivery-candidate'))
assert len(matches)==1
raise SystemExit(matches[0].load()())
'''
env = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
env.update(TMPDIR=str(ROOT / "runtime-tmp"), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
commands = []

def call(name, request_path, judgments_path, delivery_path, expected):
    cwd = ROOT / ("unrelated-" + name)
    cwd.mkdir()
    outdir = outputs / name
    selected = dict(env, EXPENSE_ASSEMBLY_AUDIT=str(evidence / (name + ".audit.jsonl")))
    argv = [str(ROOT / "envs/consumer/bin/python"), "-I", "-B", "-c", launcher,
        "--delivery", str(delivery_path), "--evaluation-request", str(request_path),
        "--judgments", str(judgments_path), "--profile", str(inputs / "profile.json"),
        "--acquisition-request", str(inputs / "acquisition-request.json"), "--output-dir", str(outdir)]
    tick = time.monotonic()
    start = datetime.now(timezone.utc).isoformat()
    with (evidence / (name + ".stdout")).open("xb") as out, (evidence / (name + ".stderr")).open("xb") as err:
        response = subprocess.run(argv, env=selected, cwd=cwd, stdout=out, stderr=err, timeout=120)
    commands.append({"name": name, "argv": argv, "cwd": str(cwd), "environment_keys": sorted(selected),
        "started_at": start, "ended_at": datetime.now(timezone.utc).isoformat(),
        "seconds": round(time.monotonic() - tick, 3), "exit_code": response.returncode,
        "expected_exit_code": expected})
    (evidence / "commercial-integration-commands.json").write_bytes(raw(commands))
    assert response.returncode == expected, (name, (evidence / (name + ".stdout")).read_text()[:700], (evidence / (name + ".stderr")).read_text()[:700])
    if expected:
        assert not outdir.exists(), name
    print(json.dumps({"step": name, "exit_code": response.returncode}), flush=True)

req, judgments_path, supplied = inputs / "evaluation-request.json", inputs / "judgments.json", outputs / "source-delivery.json"
call("commercial-positive", req, judgments_path, supplied, 0)
call("commercial-replay", req, judgments_path, supplied, 0)
for filename in ("function_candidate.json", "mechanical_report.json"):
    assert (outputs / "commercial-positive" / filename).read_bytes() == (outputs / "commercial-replay" / filename).read_bytes()

bad = deepcopy(request)
bad["product"]["commit"] = "0" * 40
save(inputs / "negative-wrong-product.json", bad)
call("reject-wrong-product", inputs / "negative-wrong-product.json", judgments_path, supplied, 1)
missing = deepcopy(judgments)
missing["judgments"].pop()
save(inputs / "negative-missing-judgment.json", missing)
call("reject-missing-judgment", req, inputs / "negative-missing-judgment.json", supplied, 1)
changed = deepcopy(delivery)
domain = changed["acquired"]["material"]["sources"]["expense/domain.py"]
domain_bytes = base64.b64decode(domain["bytes_base64"]) + b" "
domain["bytes_base64"] = base64.b64encode(domain_bytes).decode()
domain["sha256"] = sha(domain_bytes)
save(inputs / "negative-rehashed-source.json", changed)
bad = deepcopy(request)
bad["delivery_sha256"] = sha((inputs / "negative-rehashed-source.json").read_bytes())
save(inputs / "negative-rehashed-source-request.json", bad)
call("reject-rehashed-source", inputs / "negative-rehashed-source-request.json", judgments_path, inputs / "negative-rehashed-source.json", 1)
changed = deepcopy(judgments)
index = next(i for i, x in enumerate(changed["judgments"]) if x["function_id"] == pilot["function_id"])
changed["judgments"][index]["state"] = "canonical_accepted_and_allowed"
save(inputs / "negative-rehashed-state.json", changed)
bad = deepcopy(request)
bad["functions"][index]["judgment_sha256"] = compute_digest(changed["judgments"][index], excluded_field="__no_excluded_field__")
save(inputs / "negative-rehashed-state-request.json", bad)
call("reject-rehashed-state", inputs / "negative-rehashed-state-request.json", inputs / "negative-rehashed-state.json", supplied, 1)
bad = deepcopy(request)
bad["authority_boundary"]["downstream_permission"] = True
save(inputs / "negative-permission-request.json", bad)
call("reject-permission", inputs / "negative-permission-request.json", judgments_path, supplied, 1)
print(json.dumps({"independent_assembly_replay_byte_equal": True, "refusals": 5, "authority_effect": "none"}))
