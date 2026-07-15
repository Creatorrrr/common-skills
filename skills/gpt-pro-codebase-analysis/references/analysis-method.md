# Repository analysis method

Use this method when the user did not provide a stricter review framework.

## Map the relevant system

Summarize only what is needed for the goal:

- repository purpose
- goal-relevant modules and ownership
- entrypoints
- UI, transport, domain, persistence, job, and external-integration boundaries
- affected build, test, and deployment surfaces

Avoid turning the report into a directory listing.

## Trace concrete workflows

Trace one to three end-to-end paths that materially affect the goal, for example:

- request -> validation -> domain logic -> persistence -> side effects -> response
- UI event -> state transition -> API -> backend effect -> visible outcome
- scheduler -> worker -> retry or failure path -> observability

For each path, check happy path, failure path, retry or duplicate behavior, state ownership, and existing tests.

## Prioritize review lenses

Unless the goal says otherwise, use this order:

1. correctness and failure handling
2. workflow and use-case validity
3. missing implementation and hidden assumptions
4. test quality and missing cases
5. structural ownership and refactoring
6. performance and scalability
7. deprecated, duplicate, dead, or unused logic
8. security and authorization where relevant
9. observability and rollout risk
10. documentation and configuration drift

## Evidence rules

Each finding must contain:

- severity
- confidence
- claim
- evidence
- impact
- recommendation
- validation

Use `path:line` only when line information is stable. Otherwise cite the path and symbol, class, function, configuration key, or document section. Never manufacture precision.

Negative claims require broader proof:

- `unused`: inspect definitions, direct and indirect references, registration, reflection, configuration, and tests
- `missing`: inspect intended contract, wiring, callers, configuration, and related tests or docs
- `duplicate`: compare responsibility, callers, behavior, and migration state
- `deprecated`: establish original responsibility, current owner, active callers, and removal risk

If those checks are incomplete, label the claim unconfirmed and list the missing evidence.

## Test and redesign recommendations

Tie tests to behaviors and failure modes rather than percentages. State the most useful test layer and the behavior it protects.

For redesigns, identify current ownership, desired ownership, migration sequence, compatibility needs, rollback path, and validation gates. Separate quick wins from changes that alter architecture or product behavior.

## Report acceptance

The report must use:

1. Verdict
2. Scope and coverage
3. Prioritized findings
4. Unknowns and missing context
5. Recommended actions

Reject generic advice, unsupported repository-wide statements, unverifiable line references, and absence claims based only on a failed search.
