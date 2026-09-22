# Evidence-first empirical verification

Read for a consequential comparison or important adoption/causal claim. This is domain-neutral: variants may be software configurations, algorithms, models, services or process changes. Use only fields relevant to the claim. A simple understood correction still uses the light path; no manifest tool, new database or separate review team is mandatory.

## 1. Compare implementation, not labels

Before spending the costly part of an experiment, reconcile the written variants with the actual construction path and a minimal behavior probe. Planning/review-only requests propose these checks; they do not authorize target execution. For authorized execution, use existing read-only inspection or bounded dry runs and capture applicable facts:

| Fact | Examples of what needs checking |
|---|---|
| Active implementation | Actual class/function/service/version after flags and factory branches resolve |
| Changed and fixed work | Trainable/frozen parameters, enabled stages, rules, cache and numeric settings |
| State and reset scope | Per request/session/worker/global sharing; which states persist or are cleared |
| Initial conditions | Source snapshot including dirty state, artifact/checkpoint, warm/cold state, paired replication design |
| Input and evaluation path | Population/workload, preprocessing, evaluator/version, information available before an output |
| Time contract | Publish/observe/score/update order, latency boundary, data available at each decision |

Do not fill observed facts by copying intended configuration. Test the actual factory branch; state/reset claims require relevant behavior, not just a class name. Record source identity, exact probe and evidence. Redact secrets and unnecessary private data. A stubbed probe establishes only the covered construction/behavior, not full runtime validity.

If declaration and observation disagree, stop only the affected costly comparison; continue useful authorized diagnosis. For historical runs, consult their actual sealed source/artifacts rather than assuming today's source was used. Preserve measurements separately from interpretation; append corrections rather than erase the old record.

## 2. Make the contrast and claim explicit

Use a compact existing table: `claim -> candidate -> comparator -> actual differences -> controls -> supported scope`.

An isolated-change claim needs a contrast isolating that change under the relevant controls. Joint changes support a joint-effect claim. A common fixed benchmark can compare entire candidates even when their initializations differ; it is not automatically a matched causal ablation. Resetting two state components does not identify either component alone. A null/no-op intervention is not a failed test of an intervention that never happened.

Choose the least expensive discriminating comparison or narrow the claim. Do not automatically launch all combinations. An unchanged result is not evidence of equivalence without adequate sensitivity. Grouping several changes under one friendly label does not make them a single independent cause.

## 3. Failed gates: diagnosis is not promotion

Record purpose as exploration, diagnosis or promotion-confirmation. After a failed required gate, do not silently run the same full confirmation again. A useful diagnosis states the unresolved question, alternatives, possible observations and resulting next decisions, minimum workload, shared allowance and stop condition. Preserve the failed gate. Change protocol prospectively with a reason; do not reinterpret the old milestone as passed.

Diagnosis already inside the delegated development scope needs no ceremonial new approval. Changes to agreed criteria, scope, spending or external effects follow existing authority. A gate that forbids a dependent action still forbids it. Diagnostic evidence can guide a later eligible candidate; it does not bypass that candidate's required confirmation. If no possible outcome changes a decision, reuse existing evidence or pick a different question.

## 4. Evidence before the author's interpretation

For an important claim, an available verifier first receives the question and original criteria, source/configuration identity, actual variant facts, raw results and limitations. It gives its own narrow assessment and counterevidence before reconciling the author's conclusion. Do not hide failed seeds, safety constraints or data needed to evaluate validity. This is ordering evidence to reduce anchoring, not withholding contrary evidence.

Use a separate session when available and authorized. The same model in another session is not necessarily statistically independent; a second vendor does not prove independence either. When only sequential self-review is available, say so. Reading code and a small falsifying test can be more useful than another prose review. Record unresolved disagreement and the smallest test that would resolve it. Never ask for hidden chain-of-thought; concise claims and evidence suffice.

The optional [verification template](../assets/verification-template.md) is a scaffold, not an extra mandatory report. Review authority is read-only by default. Keep evaluator code/data/criteria outside ordinary candidate editing where feasible; hashes detect a change but do not prevent one. An evaluator revision needs provenance and re-evaluation of both sides, as in [experiment-protocol.md](experiment-protocol.md).

## 5. Scope, metrics and memory

For each outcome, name what changed and what capability was directly tested. Distinguish learned representation, readout, preprocessing, rules, cache, calibration, runtime changes or external assistance where relevant. Privileged diagnostic inputs and simplified workloads do not prove the full target path.

Choose evidence for the promised capability, not a convenient proxy alone. A well-calibrated probability can still be uninformative; predictive usefulness needs an appropriate score or decision measure against a meaningful simple baseline. Similarly, faster throughput with incorrect outputs is not a valid speed improvement under a correctness requirement. Keep original acceptance criteria; adding a future stronger claim does not retroactively change a completed test.

When narrowing to a subsystem, retain unresolved mission claims, contrary evidence and revisit triggers in existing state. Preserve baseline identity without permanently duplicating active code. Separate new measured work/cost from inherited lineage while respecting all existing limits.

## 6. Optional mechanical preflight

[scripts/experiment_preflight.py](../scripts/experiment_preflight.py) compares a declared spec with an observed facts file and hashes explicitly listed small evidence files under a supplied root. It reads only; it does not import target code, run probes, spend API credits, enforce permissions or decide scientific truth. Export observed facts from the actual target path using its own adapter. An existing equivalent check is sufficient.

See [the working cache example](../examples/preflight/README.md). The spec uses schema 1, an experiment ID, expected facts per arm and explicit contrasts. Observed output binds the same ID, a run ID, declared capture method, actual facts and evidence paths/hashes. Fact names are project-defined flat keys; use one independently meaningful fact per key, and explicit control values. Composite JSON values are allowed but do not prove that the grouping is causally atomic.

For the tool, `isolated-change` means exactly one declared differing fact; `joint-change` means two or more; `system-comparison` makes no component attribution. Expected differences must match the actual differences exactly. The tool cannot discover omitted confounders, dishonest exports, evaluator leakage or whether a hash-listed file covers the executed code. Those remain source/behavior review tasks. A `consistent` exit proves only the mechanical checks. Example fixtures, automated unit tests and real fresh-session agent behavior are separate evidence classes.
