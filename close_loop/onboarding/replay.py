"""Restore and reproduce the frozen Expense #3 handoff with original owners.

No project database is opened and no assessment is authored. Local Git objects
and trusted, prepared Python environments are explicit operator inputs.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
import time


MANIFEST_SHA256 = "3fe8867bbf343916a15e89d193f9ccb49b327af0d41bc57c5d189eecd37f8994"
CEB_COMMIT = "5a19e9af830f4f326a8000fd022994bc0b5daf96"
MANAGEMENT_COMMIT = "9156f6d4bb9f26e9c6fc8db9a685d5d9b79b42e8"
LAUNCHER = """
import importlib.metadata as metadata, runpy, sys
def audit(event, args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo','sqlite3.connect','os.system','subprocess.Popen'}:
        raise RuntimeError('OFFLINE_REPLAY_OPERATION_PROHIBITED:' + event)
sys.addaudithook(audit)
mode, target, *args = sys.argv[1:]
if mode == 'ceb':
    sys.path.insert(0, target)
    sys.argv = ['workload_candidate'] + args
    runpy.run_module('close_loop_evidence_builder.workload_candidate', run_name='__main__')
else:
    entries = list(metadata.entry_points(group='console_scripts', name=target))
    if len(entries) != 1:
        raise RuntimeError('PUBLIC_ENTRY_POINT_NOT_UNIQUE')
    sys.argv = [target] + args
    raise SystemExit(entries[0].load()())
"""


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def relative_path(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError("UNSAFE_FROZEN_RELATIVE_PATH")
    return path


def restore(records, destination):
    manifest_raw = (records / "MANIFEST.json").read_bytes()
    if sha256(manifest_raw) != MANIFEST_SHA256:
        raise ValueError("FROZEN_MANIFEST_DIGEST_MISMATCH")
    manifest = json.loads(manifest_raw)
    for item in manifest["files"]:
        saved_path = records / relative_path(item["path"])
        if saved_path.is_symlink() or not saved_path.resolve().is_relative_to(records):
            raise ValueError("FROZEN_FILE_OUTSIDE_RECORDS")
        saved = saved_path.read_bytes()
        if len(saved) != item["bytes"] or sha256(saved) != item["sha256"] or git_blob(saved) != item["git_blob"]:
            raise ValueError("FROZEN_SAVED_BYTES_MISMATCH:" + item["path"])
        if item["encoding"] not in {"identity", "gzip"}:
            raise ValueError("UNSUPPORTED_FROZEN_ENCODING")
        raw = gzip.decompress(saved) if item["encoding"] == "gzip" else saved
        if len(raw) != item["raw_bytes"] or sha256(raw) != item["raw_sha256"]:
            raise ValueError("FROZEN_DECODED_BYTES_MISMATCH:" + item["logical_path"])
        target = destination / relative_path(item["logical_path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    return len(manifest["files"])


def python_entry(value):
    # Canonicalize directory aliases, retaining the venv's interpreter entry.
    # Resolving the final symlink would change its pyvenv.cfg/site-packages.
    path = Path(value).expanduser().absolute()
    path = path.parent.resolve() / path.name
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("PYTHON_ENTRY_NOT_EXECUTABLE")
    return path


def snapshot(repository, revision, destination, environment, paths=()):
    repository = repository.expanduser().resolve()
    prefix = ["git", "-C", str(repository)]
    selected = subprocess.check_output(prefix + ["rev-parse", revision + "^{commit}"], env=environment).decode().strip()
    if selected != revision:
        raise ValueError("OWNER_GIT_IDENTITY_MISMATCH")
    entries = subprocess.check_output(prefix + ["ls-tree", "-rz", "--full-tree", revision], env=environment).split(b"\0")
    expected = {}
    for entry in entries:
        if entry:
            header, path = entry.split(b"\t", 1)
            mode, kind, blob = header.decode().split()
            expected[path.decode()] = (mode, kind, blob)
    archive = subprocess.check_output(prefix + ["archive", "--format=tar", revision, *paths], env=environment)
    destination.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as members:
        for member in members:
            path = relative_path(member.name)
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError("OWNER_SNAPSHOT_ENTRY_NOT_REGULAR")
            mode, kind, blob = expected.get(member.name, (None, None, None))
            raw = members.extractfile(member).read()
            if kind != "blob" or mode not in {"100644", "100755"} or git_blob(raw) != blob:
                raise ValueError("OWNER_SNAPSHOT_GIT_BYTES_MISMATCH")
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            target.chmod(0o755 if mode == "100755" else 0o644)


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, default=Path(__file__).resolve().parent / "records")
    parser.add_argument("--ceb-repository", type=Path, required=True, help="Local Git object repository containing the exact CEB commit")
    parser.add_argument("--management-repository", type=Path, required=True, help="Local Git object repository containing the exact Management commit")
    parser.add_argument("--owner-python", required=True, help="Trusted Python with rfc8785/jsonschema, also used for CEB")
    parser.add_argument("--consumer-python", required=True, help="Trusted Python with the adopted Commercial public entry installed")
    parser.add_argument("--report", type=Path, help="Optional new replay-summary file; existing files are preserved")
    args = parser.parse_args(arguments)
    if args.report and os.path.lexists(args.report):
        raise FileExistsError("REPLAY_REPORT_ALREADY_EXISTS")
    owner, consumer = python_entry(args.owner_python), python_entry(args.consumer_python)
    records = args.records.expanduser().resolve()
    commands = []
    with tempfile.TemporaryDirectory(prefix="expense-offline-replay-") as temporary:
        root = Path(temporary).resolve()
        inputs, outputs, scratch = root / "inputs", root / "outputs", root / "tmp"
        inputs.mkdir(); outputs.mkdir(); scratch.mkdir()
        environment = {key: os.environ[key] for key in ("PATH", "HOME", "SYSTEMROOT") if key in os.environ}
        environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", TMPDIR=str(scratch),
                           GIT_NO_REPLACE_OBJECTS="1", GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
        count = restore(records, inputs)
        frozen_owner = json.loads((inputs / "composition-owner-A.json").read_bytes())
        owner_paths = sorted({row["path"] for row in frozen_owner["source_origins"]})
        ceb, management = root / "ceb", root / "management"
        snapshot(args.ceb_repository, CEB_COMMIT, ceb, environment)
        snapshot(args.management_repository, MANAGEMENT_COMMIT, management, environment, owner_paths)

        def run(name, argv, expected=0):
            started = time.monotonic()
            result = subprocess.run(list(map(str, argv)), cwd=root, env=environment,
                                    capture_output=True, text=True, timeout=60)
            commands.append({"name": name, "argv": list(map(str, argv)), "exit_code": result.returncode,
                             "seconds": round(time.monotonic() - started, 3),
                             "stdout": result.stdout, "stderr": result.stderr})
            if result.returncode != expected:
                raise RuntimeError("REPLAY_COMMAND_FAILED:" + name + ":" + result.stderr[-2000:] + result.stdout[-2000:])
            return result

        ceb_entry = [owner, "-I", "-B", "-c", LAUNCHER, "ceb", ceb]
        common = ["--profile", inputs / "profile.json", "--request", inputs / "acquisition-request.json"]
        run("ceb-independent-validation", ceb_entry + ["validate-delivery", *common, "--delivery", inputs / "source-delivery.json"])
        delivery = json.loads((inputs / "source-delivery.json").read_bytes())
        (inputs / "acquired.json").write_text(json.dumps(delivery["acquired"], ensure_ascii=False, indent=2) + "\n")
        run("ceb-frozen-export", ceb_entry + ["export", *common, "--material", inputs / "acquired.json", "--delivery", outputs / "source-delivery.json"])
        if (outputs / "source-delivery.json").read_bytes() != (inputs / "source-delivery.json").read_bytes():
            raise ValueError("CEB_REPLAY_BYTES_DIFFER")

        for suffix, input_name, expected_name in [
            ("compose-A", "composition-input-A.json", "composition-owner-A.json"),
            ("compose-B", "composition-input-B.json", "composition-owner-B.json"),
            ("change-effects", "change-effects-input.json", "change-effects-owner.json"),
        ]:
            output = outputs / (suffix + ".json")
            run("management-" + suffix, [owner, "-I", "-B", inputs / "runner/invoke_management_owner.py",
                                        "--source", management, "--input", inputs / input_name, "--output", output])
            actual = json.loads(output.read_bytes())
            frozen = json.loads((inputs / expected_name).read_bytes())
            if actual["output"] != frozen["output"] or actual["request_sha256"] != frozen["request_sha256"]:
                raise ValueError("OWNER_REPLAY_OUTPUT_DIFFERS:" + suffix)
            if actual["owner_revision"] != MANAGEMENT_COMMIT or actual["authority_effect"] != "none":
                raise ValueError("OWNER_REPLAY_IDENTITY_OR_SCOPE_DIFFERS")
            if actual["source_origins"] != frozen["source_origins"] or actual["prohibited_operation_events"]:
                raise ValueError("OWNER_REPLAY_ORIGINS_OR_OPERATIONS_DIFFER")
            for origin in actual["source_origins"]:
                raw = (management / relative_path(origin["path"])).read_bytes()
                if sha256(raw) != origin["sha256"] or git_blob(raw) != origin["git_blob"]:
                    raise ValueError("OWNER_REPLAY_ORIGIN_BYTES_DIFFER")

        commercial_entry = [consumer, "-I", "-B", "-c", LAUNCHER, "entry", "commercial-source-delivery-candidate"]

        def assemble(name, delivery_name="source-delivery.json", request_name="evaluation-request.json",
                     judgments_name="judgments.json", code=None):
            output = outputs / name
            result = run(name, commercial_entry + ["--delivery", inputs / delivery_name,
                         "--evaluation-request", inputs / request_name, "--judgments", inputs / judgments_name,
                         "--profile", inputs / "profile.json", "--acquisition-request", inputs / "acquisition-request.json",
                         "--output-dir", output], 1 if code else 0)
            if code:
                refusal = json.loads(result.stdout)
                if refusal.get("ok") is not False or refusal.get("code") != code or refusal.get("authority_effect") != "none" or output.exists():
                    raise ValueError("FROZEN_REFUSAL_NOT_REPRODUCED:" + name)
            else:
                for file in ["function_candidate.json", "mechanical_report.json"]:
                    if (output / file).read_bytes() != (inputs / "commercial" / file).read_bytes():
                        raise ValueError("COMMERCIAL_REPLAY_BYTES_DIFFER:" + file)

        assemble("commercial-positive")
        assemble("reject-wrong-product", request_name="negative-wrong-product.json", code="product_binding")
        assemble("reject-missing-judgment", judgments_name="negative-missing-judgment.json", code="judgment_coverage")
        assemble("reject-rehashed-source", delivery_name="negative-rehashed-source.json",
                 request_name="negative-rehashed-source-request.json", code="ceb_source_digest")
        assemble("reject-rehashed-state", request_name="negative-rehashed-state-request.json",
                 judgments_name="negative-rehashed-state.json", code="authored_metadata_binding")
        assemble("reject-permission", request_name="negative-permission-request.json", code="authority")
        report = {"scope": "Frozen-input reproduction only; no new assessment, currentness, live propagation or authority",
                  "result": "matching frozen owner outputs and public candidate/report bytes; all five refusals reproduced",
                  "manifest_sha256": MANIFEST_SHA256, "materialized_logical_files": count,
                  "commands": commands, "authority_effect": "none", "allowed": False,
                  "currentness": "not_checked", "project_database_opened": False}
    report["owned_temporary_directory_removed"] = not root.exists()
    if args.report:
        with args.report.open("x") as stream:
            json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
    print(json.dumps({key: value for key, value in report.items() if key != "commands"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
