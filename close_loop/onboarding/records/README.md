# Frozen Expense #3 evidence

[RUN.json](RUN.json) indexes the bounded delivery. [MANIFEST.json](MANIFEST.json)
binds 96 logical files to saved paths, lengths, SHA-256 and Git blob identities.
The manifest SHA-256 is
`3fe8867bbf343916a15e89d193f9ccb49b327af0d41bc57c5d189eecd37f8994`.
This README is a locator outside that frozen inventory.

The producer source is `57fa2b3551a0e8f9243241cb2604d03ca09b19d8`, tree
`a08a4629a990a708af56a11efa292a41c2b6cf14`. Later evidence/replay commits retain
that source ancestor and do not relabel these runs as executions of a later
artifact head.

## Actual material and judgments

- [observations-A.json](observations-A.json): actual local Darwin/Python 3.11
  invocation; 39 raw observations and five execution-carrier records.
- [observations-B.json](observations-B.json): actual Linux/Python 3.12 CI
  invocation at the same source. [Push run 41640672264](https://github.com/choreoatlas/Expense-Approval/actions/runs/41640672264),
  job `125933074273`, attempt 1. The original artifact `13233051334` ZIP and
  digest receipt are retained under `provider/` and `checks/`.
- [assessments-A.json](assessments-A.json) and
  [assessments-B.json](assessments-B.json): two separate sets of seven explicit
  Controller-authored candidate condition judgments. Their raw observation,
  execution, condition, source, scope and limits bindings remain distinct.
- [function-result-A.json](function-result-A.json) and
  [function-result-B.json](function-result-B.json): each retains the predeclared
  condition/composition basis and candidate `scope_limited` result. Pure
  Management outputs are separate `composition-owner-*.json` files.
- [change-effects-input.json](change-effects-input.json) and
  [change-effects-owner.json](change-effects-owner.json): 29 dependency
  `requires_rejudge`, seven composition `stale` and one unchanged dependency
  `revalidated` calculation. This is offline causal replay between two actual
  bases, with B explicitly selected as context; it is not a query for global
  current state or persistent propagation.

The actual CEB delivery, independent validation and frozen-original export
replay are retained. The installed Commercial public entry produced a
976,383-byte candidate with SHA-256
`3b994f606cc010d00bb412c831f135aa3209060c72b0a7418b169a8772183566`;
an independent replay produced identical candidate/report bytes. Seven outer
states remain `not_rejudged`; the selected path is
`candidate_pilot_result_attached`. Original eight path scopes and the nested B
pilot record are preserved verbatim.

Five exact negative inputs remain in the inventory: wrong product, missing
judgment, rehashed changed source, rehashed changed statement metadata, and
permission escalation. Actual refusals were respectively `product_binding`,
`judgment_coverage`, `ceb_source_digest`, `authored_metadata_binding`, and
`authority`, with exit 1 and no output artifacts.

`checks/` preserves actual commands/stdout/stderr, source/push-CI identity and
24-test evidence. The initial provider HTTP 500 and initial caller symlink-path
validation failure remain alongside the successful retry/canonical-path run.
They were not deleted or converted into semantic failures.

## Restore and reproduce offline

For a material, select its `logical_path` in the manifest, read `path`, verify
the saved length/SHA-256/Git blob, decode gzip when `encoding` says `gzip`, then
verify `raw_bytes` and `raw_sha256`. Restore using the logical filename.
Relative assessment/composition/authoring references resolve beneath this
restored root. `original_path` is provenance, not a required path on a new
computer. `acquired.json` is already preserved within the delivery's `acquired`
object; the manifest records its extraction recipe.

The small [offline replayer](../replay.py) performs this materialization in an
owned temporary directory and calls the original owners. Prerequisites are
explicit, already-prepared local environments and Git objects:

- CEB Git commit `5a19e9af830f4f326a8000fd022994bc0b5daf96`.
- Management Git commit `9156f6d4bb9f26e9c6fc8db9a685d5d9b79b42e8`.
- A trusted owner Python with `rfc8785==0.1.4` and `jsonschema==4.25.1`;
  Python 3.11.15 was used for the recorded owner calculations.
- A trusted consumer Python with the public Commercial entry installed from
  `d78d138a3b0180eeec907aead73e281a58c520a1`. Its independently pinned producer
  request remains part of the frozen input.

```sh
python close_loop/onboarding/replay.py \
  --ceb-repository /chosen/local/CEB-git-repository \
  --management-repository /chosen/local/Management-git-repository \
  --owner-python /chosen/owner-environment/bin/python \
  --consumer-python /chosen/consumer-environment/bin/python \
  --report /chosen/existing-directory/new-replay-result.json
```

Preparation may require obtaining Git objects/installing dependencies; the
replay itself uses no provider token or network. It exports exact Git objects
into canonical temporary paths, excluding dirty/untracked owner files. The
Management snapshot uses its recorded import closure. Child environments are
restricted and existing owner path guards remain enabled. The replayer
verifies original source origins, compares pure owner `.output` values and
exact public delivery/candidate/report bytes, and replays the five refusals.
It does not execute the saved assessment-authoring scripts or create judgments.

These are project-local evidence and candidate Function records. Their
reproduction grants no source authentication, new Function validity, current
Governance acceptance, A1 designation/admission, canonical/relation writes,
pilot activation, effective state or downstream permission. `allowed=false`,
`currentness=not_checked` and `authority_effect=none` remain explicit.
