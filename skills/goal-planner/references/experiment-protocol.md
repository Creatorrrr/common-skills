# Hypotheses, experiments, and reliable decisions

Read for consequential empirical tests in either goal model. Use the portable Experiment block from [execution-contract.md](execution-contract.md). Reuse an existing experiment runner, logger and evaluator; this protocol does not require a new framework, schema service, or report per shell command.

## Before running

Give each material experiment a stable `Experiment ID` linked to `Hypothesis ID` and `Milestone ID` (and `Program ID` when applicable). Use one short entry or [../assets/experiment-template.md](../assets/experiment-template.md). State the claim and its scope, strongest plausible competing explanation, intervention and comparator, predicted observations, conditions for support/refutation/inconclusive results, validity checks, practical adoption rule, stopping rule and resources. Identify implementation/config/data/evaluator versions, seeds or repetitions when relevant, and raw output locations without storing secrets.

Preserve the pre-run entry before results exist. Amend prospectively with a version/reason; keep old predictions and observations. A pilot can legitimately change a later confirmatory design, but mark its results exploratory. In read-only knowledge mode, use a timestamped or ordered in-session entry rather than implying a saved preregistration. Do not claim preregistration if it was reconstructed afterward.

Record testable claims, observable predictions and concise decision rationale, not a private chain of thought or an exhaustive reasoning transcript. Only fill relevant fields. A deterministic bug reproduction does not need confidence intervals or a statistical power calculation. For a stochastic comparison, choose repetitions and uncertainty treatment that can resolve a practically meaningful effect within resources. Do not invent a universal minimum number of seeds or a threshold after seeing results. If precision is insufficient, report that rather than claim equivalence.

## Verify comparison meaning before costly runs

Apply [empirical-verification.md](empirical-verification.md) when a comparison informs adoption, a structural pivot, or an important empirical claim. Use runtime configuration plus small behavioral probes to reconcile the written variants with actual implementations, their state/reset boundaries, versions, initialization and observation/update order where applicable. Keep a small claim-to-contrast table, not a universal infrastructure requirement.

Separate `exploration`, `diagnosis`, and `promotion-confirmation`. After a failed development gate, diagnosis must identify a remaining question, result-dependent next decisions, a minimal discriminating comparison and the shared allowance. It cannot bypass a required gate, justify deployment, relabel a failed milestone, or introduce unauthorized cost. Preserve the failure and amend prospectively; no blanket reapproval is needed for diagnosis already inside the delegated scope.

## Independent judgments

| Field | Values | Meaning |
|---|---|---|
| Run status | planned / running / completed / aborted / not_run | What was actually executed |
| Validity | pending / valid / invalid | Whether the intended comparison supports interpretation |
| Hypothesis verdict | supported / refuted / inconclusive / not_tested | What evidence says about the scoped hypothesis |
| Adoption | adopt / reject / defer / not_applicable | Whether to incorporate this candidate |
| Milestone outcome | pending / pass / fail / blocked / not_run | Original milestone criteria, independent of experiment usefulness |

`pending` is an interim state, not success. The enclosing milestone owns its final outcome; an experiment entry links the current adjudication rather than inventing another completion criterion. Supported/refuted verdicts require valid, claim-relevant observations. An invalid run is normally `not_tested`; a valid but insufficient comparison is `inconclusive`. A completed process can still produce an invalid experiment. An interrupted run may support a separately identified completed subtest, not unfinished metrics.

An infrastructure failure or OOM does not refute an unrelated scientific mechanism. When feasibility under a memory/resource limit was itself the predeclared claim and the limit measurement is valid, exceeding it can refute that feasibility claim and reject the candidate. Keep this evidence distinct from unknown accuracy or learning effects.

A candidate can support a hypothesis yet be rejected for cost or regressions. A counterexample can refute a hypothesis and complete a decision-only milestone without delivering a performance improvement. An ablation can explain a cause without producing a deployable candidate. Several changes tested together support a joint-effect claim, not each component's causal contribution without further evidence.

## Observation, interpretation, and record integrity

Separate measured observations, cited external claims, inference, and unperformed checks. Retain failed seeds/runs, deviations, counterevidence, and conditional improvements; do not select only favorable outcomes. Link raw evidence, exact commands, versions and comparison scope so another session can check the claim. Avoid claiming universal truth from local support. Where direct artifacts cannot be retained, record the limitation and sanitized access-controlled reference.

Freeze completed entries; append an amendment with provenance for corrected measurements or interpretation. Reuse a question log rather than duplicate reports. Preserve a minimal transient record before retry, then batch detailed cleanup at a meaningful boundary. Write only within existing persistence authority; otherwise return equivalent evidence in-session.

## Evaluation across repeated selection

Specify the metric direction, baseline, target population/workload, practical acceptance threshold, constraints, and evaluator version before final comparison. Separate data used for exploration/selection from independent confirmation where the claim needs it. Across milestones, log evaluation access and which observations influenced candidate selection. A holdout repeatedly used to choose candidates is no longer untouched confirmation merely because thresholds stayed fixed.

Do not automatically demand new datasets. Reuse available protected splits or existing replication paths; when no independent confirmation is available, label results exploratory or limit the generalization claim. Add a stronger check only when it can change a material decision. Confirm important promotions independently or in a clean environment when warranted by their impact and uncertainty, not every local edit.

An evaluator fix is a separate versioned change with rationale and test evidence. Preserve prior results under their original version. Re-evaluate both baseline and candidate under the revised contract before attributing a score change to product improvement. Do not hide easier tests, removed failures, data leakage, warm-cache differences, shared-GPU contention or changed hardware behind the same metric name.

## Evidence-first review and scope of contribution

For an important promotion or causal claim, provide original criteria and raw evidence to a verifier before author conclusions where practical. Record the review's actual independence, source limits, contrary evidence and required smallest check. Use [../assets/verification-template.md](../assets/verification-template.md) only when useful. Do not require a second model or fresh session for every edit or claim independence when only self-review occurred.

Identify the changed mechanism and the directly tested capability. Distinguish a learned component from preprocessing, caching, rules, calibration, runtime optimization or external assistance as relevant to the project. Diagnostic privileged inputs or simplified workloads do not prove the deployed input path. Choose metrics that test the promised capability, with a meaningful simple baseline; a proxy passing alone does not establish user benefit. For probability outputs, good calibration alone does not establish discrimination or usefulness; compare appropriate predictive scores to a base-rate predictor when that is the claim.

## Research memory versus passed reports

A material experiment record is warranted by the decision it informs, including refutation, inconclusive outcomes and invalid runs requiring recovery. It does not have to qualify for a passed report. Use an existing log or a note under an already-approved research path, linked to source evidence. Experiment records and research notes remain outside the execution-report catalog.

The three closed passed-report qualifications in [execution-knowledge.md](execution-knowledge.md) remain unchanged. Apply them to the adjudicated milestone after all of its final criteria pass. A still-running research program may contain completed qualifying milestones and many non-qualifying experiments. Record honest intermediate learning without manufacturing milestone success.

## Machine keys and language

For bundled report-index interoperability, keep stable English field labels and enum values; translate free-text values/prose. Only documented lifecycle-status aliases are normalized. The indexer supports documented Korean aliases for common legacy routing/lifecycle fields, not arbitrary translations. Research and experiment fields are not automatically indexed by that execution-report tool. Existing project formats may remain if their semantics are preserved; do not impose a migration just to run a small test.
