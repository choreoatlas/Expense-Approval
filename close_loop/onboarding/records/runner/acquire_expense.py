"""Invoke the existing CEB producer against independently selected source/CI."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--run", required=True)
parser.add_argument("--job", required=True)
parser.add_argument("--attempt", type=int, required=True)
args = parser.parse_args()
INPUTS, OUTPUTS, EVIDENCE = [ROOT / name for name in ("inputs", "outputs", "evidence")]
for path in (INPUTS, OUTPUTS):
    path.mkdir(exist_ok=True)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")

def gh(path):
    return json.loads(subprocess.check_output(["gh", "api", "repos/choreoatlas/Expense-Approval/" + path]))

run, job = gh("actions/runs/" + args.run), gh("actions/jobs/" + args.job)
commit = gh("git/commits/" + args.source)
assert run["head_sha"] == args.source and run["event"] == "push"
assert run["run_attempt"] == args.attempt and run["status"] == "completed" and run["conclusion"] == "success"
assert job["run_id"] == int(args.run) and job["head_sha"] == args.source
assert job["run_attempt"] == args.attempt and job["status"] == "completed" and job["conclusion"] == "success"
assert job["name"] == "test"
save(EVIDENCE / "selected-push-run.json", run)
save(EVIDENCE / "selected-push-job.json", job)
profile = subprocess.check_output(["git", "-C", str(ROOT / "repos/expense"), "show", args.source + ":close_loop/onboarding/profile.json"])
p = json.loads(profile)
with (INPUTS / "profile.json").open("xb") as stream:
    stream.write(profile)
request = {
    "schema": "ceb.acquisition-request.v0.1", "repository": "choreoatlas/Expense-Approval",
    "target_ref": args.source, "profile_id": p["profile_id"], "profile_sha256": sha(profile),
    "ci_run_id": args.run, "ci_job_id": args.job, "ci_job_name": "test",
    "source_paths": [s["source_path"] for s in p["slices"]],
    "actor": "agent:codex:expense-3:read-only-acquisition",
    "scope": "Exact Expense source and existing successful push CI only; no Function or governance judgment",
    "authority_boundary": {"non_authority": True, "not_production_truth": True,
        "formal_import_allowed": False, "admission_effect": "none", "db_write_allowed": False,
        "upload_performed": False, "official_apply_run": False},
}
save(INPUTS / "acquisition-request.json", request)
save(EVIDENCE / "product-source.json", {"repository": "choreoatlas/Expense-Approval",
     "commit": args.source, "tree": commit["tree"]["sha"], "ci_run": args.run,
     "ci_job": args.job, "ci_attempt": args.attempt, "profile_sha256": sha(profile)})

# Token remains in memory/one permitted child environment, never argv or records.
token = subprocess.check_output(["gh", "auth", "token"], stderr=subprocess.PIPE).decode().strip()
env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR") if k in os.environ}
env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", GITHUB_TOKEN=token)
launcher = "import runpy,sys;sys.path.insert(0,sys.argv[1]);sys.argv=['workload_candidate']+sys.argv[2:];runpy.run_module('close_loop_evidence_builder.workload_candidate',run_name='__main__')"
commands = []
for name, mode in [("ceb-live-deliver", "deliver"), ("ceb-independent-validate", "validate-delivery")]:
    command = [str(ROOT / "envs/platform/bin/python"), "-I", "-B", "-c", launcher,
        str(ROOT / "repos/ceb"), mode, "--profile", str(INPUTS / "profile.json"),
        "--request", str(INPUTS / "acquisition-request.json"), "--delivery", str(OUTPUTS / "source-delivery.json")]
    if mode == "validate-delivery":
        env.pop("GITHUB_TOKEN", None)
    tick = time.monotonic()
    start = datetime.now(timezone.utc).isoformat()
    with (EVIDENCE / (name + ".stdout")).open("xb") as out, (EVIDENCE / (name + ".stderr")).open("xb") as err:
        result = subprocess.run(command, env=env, cwd=ROOT, stdout=out, stderr=err, timeout=240)
    commands.append({"name": name, "argv": command, "cwd": str(ROOT), "environment_keys": sorted(env),
        "started_at": start, "ended_at": datetime.now(timezone.utc).isoformat(),
        "seconds": round(time.monotonic() - tick, 3), "exit_code": result.returncode})
    (EVIDENCE / "acquisition-commands.json").write_text(json.dumps(commands, indent=2) + "\n")
    print(json.dumps({"step": name, "exit_code": result.returncode}), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
token = None
raw = (OUTPUTS / "source-delivery.json").read_bytes()
print(json.dumps({"delivery_bytes": len(raw), "delivery_sha256": sha(raw), "authority_effect": "none"}))
