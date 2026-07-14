---
name: goal-planner
description: Create or review outcome-first long-running /goal prompts and GOAL_PLAN.md files for Codex or Claude Code. Use when the user asks for goal mode, a durable execution plan, plan review, or a measurable performance/implementation goal. Keep user-visible or product outcomes ahead of verification, bound validation-only work, apply risk-proportional evidence, and prevent tests, documents, or verifier infrastructure from replacing the requested result. Do not use for ordinary execution or generic planning unless the user explicitly wants a long-running agent goal.
---

# Goal Planner

Create or review a plan-first goal that produces the result the user asked for. Treat verification as evidence for the result, not as the result itself.

Produce one of these outputs:

1. Up to three blocking clarification questions.
2. A compact plan review and the smallest needed patch.
3. A complete plan.
4. A copyable runtime-specific `/goal` prompt.
5. For a multi-session goal, a `GOAL_PLAN.md` body plus a short launch prompt.

Respond in the user's language.

## Select the target runtime

- Use the runtime named by the user.
- Otherwise use the active harness: Codex in Codex, Claude Code in Claude Code.
- Ask only when the runtime materially changes the requested output and cannot be inferred.
- Keep planning logic runtime-neutral. Runtime differences belong only in the final prompt and evidence wording.
- Read [references/runtime-prompts.md](references/runtime-prompts.md) only when producing a copyable final prompt. Do not load it for clarification or plan review alone.

## Outcome-first contract

Apply this priority order:

1. The user's requested product, behavior, decision, or deliverable.
2. Implementation or investigation that creates that outcome.
3. The cheapest direct evidence that the outcome works.
4. Additional confidence checks when proportional to risk.

For a build or change goal:

- Name the primary product artifact or behavior near the top of the plan.
- Require actual product/code/output change in the completion criteria.
- Do not allow tests, documents, fixtures, schemas, manifests, reviewers, or verifier infrastructure alone to satisfy the goal unless one of them is itself the requested product.
- Define what counts as progress and what does not.
- After at most one setup/baseline checkpoint, require every checkpoint to produce a product delta, user-facing artifact, measured candidate result, or binding implementation decision.

For analysis or report goals, keep the requested explanation or decision as the product. Do not invent implementation work.

## Bound verification work

- Choose one minimal, direct verification method for each completion criterion. Add more only for a distinct material risk.
- Do not create two consecutive verification-only checkpoints.
- Use focused checks during iteration. Reserve broad regression, clean-environment reruns, or independent review for meaningful stage boundaries or final verification.
- Before adding an evaluator, schema, manifest, fixture framework, journal, service, or new artifact family, state which mandatory criterion cannot be checked with existing paths. Do not add it if an existing path is sufficient.
- If proposed verification would exceed implementation work, introduce an external/time-based blocker, or require a new service or data campaign, stop and ask before expanding the plan.
- Do not add prospective waiting periods, live samples, manual review panels, or production traffic as mandatory gates unless the user asked for deployment/readiness or the requested claim cannot be made without them.
- Record failures honestly, then return to the product cause. Do not respond to a failed product metric by expanding the verifier unless the measurement itself is demonstrably wrong.

## Select verification strength by impact

Use the lowest level that protects the actual outcome:

- **Analysis/report:** source-backed evidence and direct review of the requested artifact.
- **Ordinary implementation:** focused tests or direct runtime check plus relevant regression coverage.
- **Performance/optimization:** frozen baseline, identical comparison conditions, bounded search, chronological OOS or holdout when applicable, and one final-candidate verification. Do not change thresholds after seeing candidate results.
- **High-impact external change:** independent or clean-environment final verification for deployment, destructive migration, authentication/security boundary changes, payments, real orders, or other external-state mutations.

Offline research in a high-stakes domain is not automatically a high-impact external change. Keep live activation and production readiness as a separate stage unless the user includes them in scope.

An independent verifier must re-check the existing final and regression criteria. It must not introduce new success criteria, redesign the product, or start another verification program. Run this pass once at the end unless a found product defect requires repair and re-check.

## Keep goals bounded

- Default to at most six stages and eight final completion criteria. Exceed these limits only when the user's outcome genuinely has more independent parts, and state why.
- Bound candidate or repair iterations. If the plan cannot set a useful numeric budget, require a stop after repeated failures under the same fixed conditions and report evidence.
- Keep automatic target uplift disabled by default. Do not ask about stretch goals unless the user requests continued improvement after the mandatory target.
- If a numeric target is unknown, add a baseline-measurement step and a target-selection rule. Do not invent a number.
- Separate `blocked` external evidence from failed implementation. Do not let a nonessential external blocker stop in-scope product development.
- Preserve user work and require approval for destructive actions, credentials, paid services, deployment, production mutations, or material scope changes.

## Decide whether a plan is usable

A plan is usable when it contains:

- The original user outcome and primary deliverable.
- Scope and explicit non-goals.
- A current baseline or a bounded step to establish it.
- Stages whose outputs advance the requested outcome.
- Minimal direct verification for those outputs.
- Final criteria that cannot pass without the requested result.
- A verification budget or risk level.
- Bounded failure and stop conditions.
- A compact progress rule.

Do not require a stage-level performance number when that stage only produces a necessary implementation artifact or decision. Do not mark a plan incomplete merely because it lacks a separate independent-verification section at low or medium impact.

## Ask only material clarifications

Ask no more than three concise questions, and only when the answers materially change the outcome, scope, irreversible behavior, or success criteria.

Useful topics include:

- What must exist or behave differently when the goal finishes?
- Which baseline, target, or compatibility boundary is authoritative?
- Is deployment, live traffic, migration, or another external mutation in scope?

If the user asks for an immediate draft, make conservative assumptions, label them, keep stretch disabled, and continue.

## Plan template

Use only the sections needed by the task. Prefer this compact structure:

```markdown
## 목표와 실제 산출물
- 원래 사용자 요청:
- 최종 제품/결과:
- 범위:
- 비목표:

## 진척 계약
- 진척으로 인정:
- 진척으로 인정하지 않음:
- 검증-only 작업 상한:

## 기준선과 미지수
- 현재 기준선:
- 확인할 미지수:
- 고정 비교 조건 또는 가정:

## 실행 단계
| 단계 | 실제 산출물/동작 변화 | 최소 직접 검증 | 완료 조건 |
|---|---|---|---|
| 1 | ... | ... | ... |
| 2 | ... | ... | ... |

## 최종 완료 기준
- 제품/사용자 결과:
- 성능 또는 품질 기준:
- 회귀 방지:
- 꼭 필요한 산출물:

## 검증 수준과 예산
- 위험 수준:
- 반복 중 focused 검증:
- 최종 검증:
- 검증 확장 전 질문 조건:

## 중단 조건과 진행 로그
- 중단하고 질문할 조건:
- 실패 iteration 한도:
- 로그 형식: product delta -> direct evidence -> remaining product gap -> blocker
```

For a pure analysis/report goal, replace `제품/동작 변화` with `분석 산출물/결정` and omit irrelevant performance sections.

## Review rubric

Return `통과`, `보완 필요`, or `불충분`, then show the smallest patch needed.

Check:

1. Does the plan preserve the original user request as its primary outcome?
2. If the user asked to build or change something, can the goal pass only after that product behavior or artifact exists?
3. Does each post-setup stage create a real deliverable, product delta, measured candidate, or binding decision?
4. Is each verification item the minimum direct evidence for a stated risk or criterion?
5. Are verification-only work, new infrastructure, artifacts, and documentation bounded?
6. Has the plan avoided adding unrequested external or long-duration gates?
7. Are iteration limits, failure handling, and stop conditions bounded?
8. Is final verification proportional to external impact, without allowing the verifier to expand scope?

Treat failures in items 1-4 as `불충분`. Do not make a plan longer merely to satisfy formatting.

## Generate the final prompt

- Use a direct `/goal` when the plan is short and can remain clear within the runtime limit.
- Use `GOAL_PLAN.md` for multi-session goals or plans that would make the launch prompt unwieldy.
- When a `GOAL_PLAN.md` already exists, treat its current scope and validation budget as authoritative. Repair only contradictions or execution-blocking omissions. Ask before expanding scope, completion criteria, or verification strength.
- Read [references/runtime-prompts.md](references/runtime-prompts.md), select only the matching runtime section, and adapt it without copying irrelevant variants.
- Keep the copyable prompt close to the top or end of the response, not buried in commentary.

Use this output order when applicable:

1. `계획 검토`
2. `보완 질문` only if blocking
3. `작성된 계획` or smallest patch
4. `복사용 실행 프롬프트`
5. One or two usage lines

Do not execute the target project while using this skill unless the user explicitly asks to edit this skill itself or to write the resulting plan into project files.
