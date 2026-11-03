"""Bounded execution witness for existing, exact-revision pure owners."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--input", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
source = args.source.resolve()
request = json.loads(args.input.read_bytes())
events = []

def audit(event, values):
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "sqlite3.connect", "os.system", "subprocess.Popen"}:
        events.append({"event": event, "denied": True})
        raise RuntimeError("OWNER_OPERATION_PROHIBITED:" + event)

sys.addaudithook(audit)
sys.path.insert(0, str(source))
from scripts.a1_first_current_genesis_semantic_closure_v0_3_1 import compose_condition_states
from close_loop_v2.relation_effective_state_resolver_v0_1 import (
    resolve_relation_change_effect_v0_1,
    resolve_stale_rejudge_state_v0_1,
)

if request["operation"] == "compose":
    response = {"state_combination_output": compose_condition_states(request["assessments"], request["validation_policy"])}
elif request["operation"] == "change_effects":
    cases = []
    for case in request["cases"]:
        effect = resolve_relation_change_effect_v0_1(case["relation"],
            source_revision=case["source_revision"], target_current_revision=case["target_current_revision"])
        cases.append({"id": case["id"], "effect": effect.to_dict(),
                      "state_output": resolve_stale_rejudge_state_v0_1(
                          stale_basis=effect.stale_basis, rejudge_required=effect.rejudge_required)})
    response = {"cases": cases}
else:
    raise ValueError("unsupported bounded witness operation")

origins = []
for name, module in sorted(sys.modules.items()):
    filename = getattr(module, "__file__", None)
    if filename is None:
        continue
    path = Path(filename).resolve()
    if path.is_relative_to(source) and path.is_file():
        raw = path.read_bytes()
        origins.append({"module": name, "path": path.relative_to(source).as_posix(),
                        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                        "git_blob": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()})

result = {"owner_revision": "9156f6d4bb9f26e9c6fc8db9a685d5d9b79b42e8",
          "request_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
          "operation": request["operation"], "output": response,
          "source_origins": origins, "prohibited_operation_events": events,
          "authority_effect": "none", "scope": "existing pure owner calculation only; no new judgment or mutation"}
with args.output.open("x") as stream:
    json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
    stream.write("\n")
print(json.dumps({"operation": request["operation"], "output": str(args.output), "authority_effect": "none"}))
