# Expense workload onboarding

This directory is the project-owned input and observation boundary for
[Expense #3](https://github.com/choreoatlas/Expense-Approval/issues/3).
The bounded target is `FL-general-manager-final-approval`, explicitly a
**condition-assessment pilot** under Management's
[canonical pilot rules](https://github.com/choreoatlas/close_loop_management/blob/9156f6d4bb9f26e9c6fc8db9a685d5d9b79b42e8/AGENTS.md).
It does not change the pilot mode or create a new platform schema/runtime.

## Objects and source ownership

- [objects.json](objects.json) references the existing subject/GN1, five
  implementation carriers and eight Function definitions. Original per-path
  scope and limits remain explicit. Those definitions and their historical
  statuses remain at `close_loop/attempt-1/`; this onboarding does not rewrite
  the original model or invalidate historical results.
- [profile.json](profile.json) is an ordinary `ceb.candidate-workload.v0.1`
  profile. Its source slices establish byte visibility, not execution coverage
  or Function validity. Actual carrier execution records reference raw
  observations separately.
- [conditions.json](conditions.json) declares all seven required conditions of
  the bounded final-review scenario and their source requirements/witnesses.
  Browser, restart, history and revision-binding are supporting conditions;
  the other seven complete Function paths are not newly rejudged here.
- [composition.json](composition.json) is the rule declared before execution
  and assessment. Each selected-function/basis snapshot has exactly one
  explicit assessment per required condition. Two runs keep two separate
  assessment sets and results. A successful command, a matching digest or an
  assembled candidate is not a condition assessment.
- [owners.json](owners.json) binds existing CEB, Management and Commercial
  revisions. CEB owns source/CI acquisition and validation; Management owns
  the existing pure composition/relation calculations; Commercial owns its
  public candidate assembler. No copy of those algorithms lives here.

The application business identity `expense_id + expense_revision`, product
Git revision and platform judgment-basis revisions have separate meanings.
Local `employee`/`approver`/`general_manager` roles are not platform assessors or
governance authority. The original Owner acceptance remains bound to
`c0f01dbf4af0dc9f9201c15f37cf960b925fce0c` and its `reference-sample` scope:
[original decision](https://github.com/choreoatlas/Expense-Approval/issues/1#issuecomment-5571375864).

## Raw application observation

Install the existing declared browser dependency and Chromium in an isolated
environment, then use a full, independently selected source commit and a new
output destination:

```sh
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m close_loop.onboarding.observe \
  --product-revision '<full selected source commit>' \
  --run-id 'expense-local-A' \
  --output '/chosen/independent-directory/expense-local-A.json'
```

The observer requires its own code, all five declarations and the application
support files to be regular tracked blobs in the selected Git tree. An old
source label with a new untracked harness is rejected. It also rejects a
mismatching checkout, changed tracked bytes or an existing destination.
Before allocating application resources it records the
source tree/file identities and hashes of all declarations. Its output records
actual HTTP requests/responses, complete before/after scratch database rows,
Chromium UI/API observations, and application-process restart observations.
It references the five existing carrier identities and records environment
and source origins. `completed=true` means the observation commands finished;
there is no `valid`, assessment or `path_state` output.

All databases and listeners are created beneath this invocation's temporary
directory; the application receives an explicit owned SQLite file and a
loopback/ephemeral port. Application, Git, Playwright driver and browser child
environments exclude ambient provider/cloud/DB credentials. Raw observations
retain resource cleanup facts. Ordinary exceptions produce a partial
`completed=false` document; interruption still unwinds owned resources. This
is not a SIGKILL cleanup guarantee or an OS sandbox.

CI retains the existing tests, executes this observer at its actual checkout
revision, and uploads the raw JSON as `expense-final-approval-<run>-<attempt>`.
Use an exact source-commit **push** run for fresh CEB acquisition; a PR job may
execute a merge checkout. Provider context in raw JSON is recorded context,
not an authentication claim by the observer.

## Cross-repository use and assessment

1. Select the product commit, its actual successful push run/job/attempt and
   this profile's exact bytes independently. Supply those to the original CEB
   acquisition request. Invoke the existing `workload_candidate deliver` and
   independent validator. The original producer owns transport, envelopes,
   digests and errors. Local observer bytes must not be labeled GitHub CI logs.
2. Read the complete original observations and form seven explicit
   actor-authored assessments, each binding its required condition, source,
   execution/evidence revisions, scope, limits and reason. Independently check
   the full condition set and one-assessment cardinality. Only then invoke the
   original Management `compose_condition_states` at the pinned owner version.
   Its pure calculation does not create an A1 designation or governance
   authority. Do not use the A1-specific assessment fingerprint as a general
   project identity contract.
3. Retain the old set/result. Execute a second actual observation event with a
   new execution/evidence basis. Invoke the original normalized-relation owner
   for the declared `depends_on` / `composes` change effects and an unchanged
   dependency control. A new assessment requires reading the new evidence;
   stale/rejudge helper output is not a new judgment or automatic propagation.
4. Assemble all eight Function identities through installed Commercial public
   entry points, with an independent caller request and explicit authored
   statements. The seven nonselected paths stay explicitly not rejudged.
   Preserve original path contracts/scopes as original context. A common
   **assembly/inspection** scope must not replace the original Function scope.

The complete local/CI run evidence, authored assessments and integration
artifacts are delivered separately with immutable source/digest locators.
The observer and profile do not establish source authenticity, current
Governance acceptance, canonical/DB admission, effective state, production
readiness or downstream permission. No target DB, canonical/relation write,
new writer, plugin framework or service is used by this boundary.
