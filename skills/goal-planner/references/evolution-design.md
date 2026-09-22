# Evaluator-first evolutionary research (conditional)

Read for repeated candidate search, expensive staged evaluation, uncertain domain adaptation, or a measured plateau. Do not load it for a routine review/edit. This reference informs planning; it does not start a research engine. Existing authority, state and reporting rules remain in the selected portable contracts.

## 1. Establish the domain contract before searching

Use the existing plan/log and evaluator where possible. Record the desired capability and final operating regime, the candidate interface and evolvable files/components, hard invariants, protected evaluator/data/fixtures, baseline, allowed resources, and what the score does **not** demonstrate. A concise domain description is not a reliable evaluator. When generating an initial program or evaluator, validate them separately before optimizing against them.

Calibrate a new or materially changed evaluator with a known-valid baseline, a known-invalid or deliberately worse case, and relevant boundary/metamorphic checks. Examples: a deliberately wrong answer must not earn full accuracy; a nondeterministic shortcut must not satisfy a determinism requirement; a no-op must not count as learning. Use the smallest checks that target actual risks, not a mandatory test campaign for every edit. Keep raw errors separate from scores; missing/NaN/timeout is not zero-quality valid evidence.

A candidate should not be able to alter the judge, protected holdout, baseline or pass threshold to improve its own result. File permissions, isolated workspaces and external evaluators are stronger than a prompt instruction when the host supports them. Existing explicit local development authority still applies; a legitimate evaluator repair receives a new version and matched baseline/candidate rerun, not an unrecorded exception.

## 2. Cascade evaluations, not conclusions

Design the cheapest sufficient path: parse/interface/invariants → small operational probe → comparable development evaluation → proportionate confirmation → integration/regression. Omit irrelevant stages. Before running, define each stage's question, input/regime, pass/reject conditions, evidence and incremental resource allowance. Cheap validity failures should not consume the entire training budget.

A stage name is not evidence. Keep **per-stage measurements** and record which source/configuration/scale produced them. Never rank pilot scores against full-scale scores, or reuse pilot metrics as confirmation. At a scale, data, precision, reset, hardware or evaluator change, identify the new comparison cohort and retest the promising candidate with the relevant baseline. Preserve the old small-scale result; do not pretend it was wrong merely because transfer failed.

Stopping an unpromising candidate is distinct from ending a finite improvement goal or an authorized research program. Diagnosis after a failed stage remains possible with the existing prospective decision fork, but it does not promote the candidate. Required confirmation can be bounded and proportional; absence of a holdout limits claims rather than automatically authorizing new data collection.

## 3. Keep a portfolio, not just the latest winner

Retain the best verified artifact separately from the active proposal, and preserve the raw history. For genuine open-ended search, consider a small set of high-performing comparable parents plus a materially different mechanism or informative negative result. Choose this only when the alternative can change a decision; no fixed beam size or number of parallel agents is universal.

Distinguish exact source/configuration duplicate detection from semantic/mechanism similarity. A new name, LLM explanation or embedding distance is not novelty. A repeated artifact may be a deliberate replication: retain it as evidence, not a new independent invention. Conflicting records need reconciliation, not silent selection of the convenient score.

For multiple objectives use hard feasibility constraints first, then a declared preference or Pareto comparison within the same measurement regime. Do not invent a weighted sum between arbitrary units or let an LLM novelty score offset failed safety/correctness/quality constraints. Maintain a family tag or descriptor only if it represents a meaningful mechanism. MAP-Elites/islands, UCB1, greedy and random policies have different costs; select using matched task evidence, not a universal recommendation. Our optional helper is **family-aware Pareto reference selection**, not a reimplementation of MAP-Elites/UCB1.

A composite proposal can be useful, but report its combined effect. When a mechanism claim matters, schedule the cheapest discriminating ablation or simplify the claim. Simpler candidates may become better at a larger scale; perform deletion/simplification tests when complexity no longer earns its cost.

## 4. Translate outcomes into compact, revisable lessons

Maintain separate evidence types: external prior, observed local result, interpretation/hypothesis, and not-tested prediction. A reusable lesson records: scope/conditions; actual change or semantic delta; predicted versus observed effect; evidence pointer; alternative explanation; confidence **basis**; counterevidence; and the next discriminating check. Do not demand fabricated numerical confidence.

Use a lifecycle such as provisional / supported-within-scope / contradicted / superseded. Preserve contradictory or superseded lessons with provenance; do not destructively remove a previous result. Retrieve a few relevant lessons and linked code/evidence on demand, including applicable counterexamples. Do not resend every full historical program, nor replace retrievable source with an ungrounded summary. A summary is an index to evidence, not a new source of truth.

No shared vector service or new database is required. Existing logs/files and bounded text retrieval are sufficient until their limits are observed. The reference selector cannot infer causal lessons, trustworthiness or scientific validity from declared records.

## 5. Make stagnation a decision boundary

Before an expensive campaign, define task-appropriate indicators for diminishing returns: comparable feasible improvement per measured cost, valid-candidate rate, duplicate rate, mechanism diversity, unresolved information and deployment constraints. An optional plateau threshold must be selected prospectively for that campaign; never apply someone else's fixed number globally.

At a meaningful plateau, compare: refine the current direction; test a different representation or family; expand the evolvable code boundary **within authorized scope**; revise the evaluator only to correct an evidenced defect; simplify the candidate; or pause the affected search because no justified next experiment remains. Preserve original criteria and the best verified artifact. This is not permission to rename a failed goal, buy more compute, increase model effort indefinitely, or reset the budget.

Represent remaining resources per unit with measured use, in-flight reservation and unknowns. Parallel candidate evaluation can improve throughput only if writes and measurements are isolated and shared limits include all workers. Keep one owner per mutable target; avoid simultaneous GPU workloads contaminating latency measurements. Store work IDs and source versions for crash-safe reconciliation; never claim this skill itself provides locking, sandboxing, recovery daemons or cancellation.

## 6. Match role structure to the task

The useful separation is proposer / executor / evaluator / analyzer and preserved memory, not an obligation to create four new agents. Deterministic tests should be code; consequential ambiguous findings benefit from evidence-first review; a single authorized coding agent can perform the rest sequentially. Preserve any configured upper-planner/lower-worker profile, review sequence, supported tools and delegation limit. Do not silently choose a new worker/provider. Ask only for a genuinely unresolved runtime choice needed for the next delegated call.

Use a more capable proposer where valid-candidate yield or hypothesis quality justifies cost, and a lighter process for deterministic bookkeeping. Benchmark against the existing configuration before changing model/effort. Distinguish a failed parser/tool call from a disproved hypothesis; retries must fix an identified cause or use a different supported approach.

## 7. Optional read-only helpers

[scripts/research_portfolio.py](../scripts/research_portfolio.py) validates a supplied snapshot, reports stage/cohort exclusions, Pareto references, duplicate conflicts, declared confirmation binding and separate resource balances. It does not read the referenced artifacts or run evaluators; its output explicitly says `supplied_records_only`, `adoption: not_decided`, `execution_authorized: false`. Exit 0 means the report could be computed, not the goal passed.

[scripts/build_handoff.py](../scripts/build_handoff.py) compiles selected existing contract blocks once. Default is Core only; optional block selection does not authorize its actions. It refuses unresolved markers and a too-small byte cap rather than silently dropping rules. Output is stdout; saving it uses ordinary host write authority.

See the [worked helper guide](../examples/portfolio/README.md) and [optional search-plan scaffold](../assets/search-plan-template.md). Both are optional, not new acceptance gates.
