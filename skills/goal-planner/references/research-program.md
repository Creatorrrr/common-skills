# Continuing research programs

Read for `research-program` authoring. The general authority and operation boundary is in [../SKILL.md](../SKILL.md); the portable Program block is in [execution-contract.md](execution-contract.md). These are authoring rules, not an executable scheduler.

## Program envelope

Infer the goal model from the user's intent. A clear request to keep selecting goals while studying a topic delegates succession; a request to repeat trials until one fixed improvement is complete does not. Drafting an envelope is not activation. State the user's authorization basis, mission, invariant requirements, permitted milestone/method choices, exclusions, relevant external-effect boundaries, authorized knowledge paths, shared resources, and pause/end conditions. Apply already-granted permissions without asking again.

Use the current goal template's Program section rather than requiring a new family of plan files. The active `GOAL_PLAN.md` may carry the stable envelope and one current milestone, with compact historical outcome links. Rewrite only its authorized current-milestone portion; preserve the previous criteria and verdict in a versioned entry or approved history before replacing it. No Git commit is implicitly required.

## Three levels

| Level | Defines | Closure |
|---|---|---|
| Program | Mission, scope, authority, resources, and selection policy | User stop, agreed terminal condition, or explicit pause at a real limit |
| Milestone | A finite capability, improvement, or consequential decision | Original criteria adjudicated as pass/fail/blocked/not run; preserve incomplete or invalidated claims |
| Experiment | A versioned hypothesis and discriminating comparison | Run state, validity, verdict, adoption decision, and evidence recorded |

A single milestone passing does not complete the program. A successful experiment does not automatically pass the milestone. A failed experiment need not close it. Candidate rejection within an improvement milestone normally leads to a justified next attempt. When its premise is invalidated or its allocated opportunity is exhausted, close it honestly and choose a better milestone if program authority/resources remain. Do not create trivial milestones or retroactively recast failed improvement as successful inquiry.

## Decision loop

At a meaningful boundary: reconcile observations; adjudicate the current experiment/milestone; update applicable beliefs with conditions and contrary evidence; preserve or promote verified artifacts; then continue the milestone, revise its method, or select a successor.

For successor selection, compare plausible work by mission contribution, key uncertainty reduced, dependencies unlocked, expected cost, delay and recoverability. Do not invent confidence percentages or require a scoring spreadsheet. Choose one current milestone; retain only useful alternatives and their revisit triggers. Information-only goals are appropriate when answering the question genuinely changes a consequential decision. Review whether learning is changing decisions or whether the program is merely accumulating notes.

Include stable continuation and structural alternatives where credible. Both repeated failure and new opportunity evidence can justify bounded exploration. A pivot is not mandatory after an arbitrary number of failures. A radical architecture experiment can be reversible and internal; deletion, production mutation, publication and new spending remain separate authorization questions. If no useful next test or credible direction is available, record the specific information/resource gap and pause; do not fill the gap with random variants or ceremonial research.

## Shared resource accounting

Use real applicable units, such as GPU-hours, experiment runs, monetary spend or an actual host session limit. Honor explicit caps. Charge research, invalid runs, retries, validation and subagents to the same program accounting; milestone allocations are portions of that allowance, not additive new grants. Count each measured cost once. Track in-flight reservations when concurrent work can consume remaining allowance, release them only after completion/cancellation is confirmed, and distinguish actual usage, estimates, reservations and unknowns.

No useful numeric cap can be invented from thin air. If limits are unspecified, document known host limits and a bounded next unit; continue already-authorized reversible work. Ask only before a concrete action whose spending or unattended scope is genuinely unapproved. Unknown accounting is not zero, unlimited permission, or evidence that paid work fits. At a hard cap stop launching dependent work and account for owned tasks using supported controls. Goal renames and restarts retain program identity and expenditure. A user-approved increase must retain prior spend and record the changed authorization.

## Preserve and promote artifacts

Keep the best verified artifact (or a small non-dominated set under a multi-objective goal) distinct from active candidates. Identify code including relevant dirty changes, model/checkpoint, configuration, data and evaluator versions, scope of validated claims, and evidence paths. The latest artifact is not necessarily the best. Apply the agreed objective priority/tie-break rule; do not silently trade quality for speed or discard valid alternatives.

Use an isolated candidate path or existing reversible workflow. Promote only after the fixed comparison and relevant regression criteria hold. A promising pilot may justify further experiments without replacing the best artifact. After an evaluator or environment change, invalidate only affected claims and recompare under that contract before calling a new winner. Never overwrite the sole verified artifact with an unverified experiment. Record what was actually restored; do not claim rollback without checking state.

## Resume state

Prefer the existing authorized log. [../assets/research-state-template.md](../assets/research-state-template.md) is a compact alternative, not a mandatory database or new directory. Record program/milestone/experiment IDs, original criteria and verdicts, active hypotheses with evidence pointers, best and active artifacts, actual workspace/dirty state, evaluator and data IDs, evaluation exposure, owned live tasks, resource usage/reservations/unknowns, and the next decision. Save at meaningful transitions and before expected interruption when possible, not after every command. Keep long history in linked records; do not recursively summarize away contradictory evidence.

Resume by reconciling current files, artifacts, process/task state, versions and actual accounting. An old `running` label does not prove a process is alive. Do not launch duplicate work while a prior task may still be running; inspect available task identifiers first. Never retry a completed costly experiment solely because its final chat message is missing. Preserve partially captured observations and classify missing evidence honestly. Single-writer ownership or the existing atomic/versioned write mechanism avoids partial snapshots; concurrent researchers return to the owner rather than racing to replace the shared state.

Without approved durable storage, keep a compact in-session state and provide a copyable resume summary. This does not block authorized current work, but is not durable cross-session memory. A plan cannot provide scheduling, automatic restarts, or cancellation that the host does not implement.

## Stop and succession boundaries

Program state is `active`, `paused`, `stopped`, or `completed`. `completed` requires the program's agreed terminal condition, not merely a finished milestone. `paused` preserves a concrete blocking gap and resume condition. User stop revokes continuation; finish only supported cleanup needed to account for owned tasks and preserve permitted state, not another research milestone.

Researchers supply evidence and proposals. The main executor checks them and selects successors within the envelope. A research file, lifecycle status, or index entry never expands that envelope. In finite-goal mode, keep unsolicited target uplift disabled. These are scope-specific rules, not contradictory universal stop and continue commands.
