---
name: goal-planner
description: Create or review a Codex /goal objective before long-running work. Use when the user asks to write a goal-mode plan, generate a copyable /goal prompt, review a plan for Codex goal mode, or asks in Korean such as "goal 작성", "목표 설정", "계획 검토", or "성능 목표를 /goal로 만들기". Do not use for ordinary project execution or generic planning unless the user explicitly wants a Codex /goal prompt.
---

# Goal Planner

Use this skill to help the user create a copyable Codex `/goal` prompt that is safe, concrete, measurable, and plan-first.

Your job is not to implement the project. Your job is to produce one of these outputs:

1. Clarifying questions needed to create a plan.
2. A plan review against the rubric below.
3. A complete plan.
4. A final copyable `/goal` prompt.
5. For long goals, a `GOAL_PLAN.md` body plus a short copyable `/goal` line that points Codex at that file.

Respond in the user's language. If the user writes Korean, respond in Korean.

## Core rules

- Do not start coding, editing project files, running migrations, or performing the target task while this skill is active unless the user explicitly asks you to install or edit this skill.
- A final `/goal` prompt must be plan-first. If no sufficient plan exists, create or request the plan before writing the final goal.
- If a plan already exists, review it before writing the final goal.
- Do not enable self-directed target increases unless the user explicitly opts in.
- Make every completion condition verifiable. Prefer commands, tests, benchmarks, generated artifacts, screenshots, reports, or exact acceptance criteria.
- If a numeric performance target is impossible to know from the prompt, define a baseline-measurement step and target-selection rule rather than inventing unsupported numbers.
- Bound the work. "Do not stop until achieved" means continue through reasonable verification and repair loops, but pause and report evidence if blocked by missing credentials, destructive actions, approval requirements, unsafe changes, external service failures, or targets that appear infeasible under the stated constraints.

## Detect whether a usable plan exists

Treat the user as having a usable plan only if the provided content includes all of the following:

- Overall objective or desired outcome.
- Work stages or checkpoints.
- Stage-level target spec or performance level for every stage.
- Final target spec or performance level.
- Verification method for stage targets and final target.
- Constraints, non-goals, or boundaries.

If any required element is missing, treat the plan as incomplete and either ask focused questions or propose a patched plan.

## Mandatory clarification when no sufficient plan exists

Ask only for missing information that materially changes the goal. Keep questions grouped and concise. Prefer at most 7 questions.

Always include this opt-in question unless the user has already answered it:

> 필수 성능/품질 목표를 달성한 뒤, Codex가 스스로의 판단으로 최대 3회까지 성능 목표를 상향하고 추가 개선을 진행하도록 할까요? 허용한다면 상향 가능한 지표와 금지 범위도 알려주세요.

Useful questions to ask when missing:

- 작업 대상: 어떤 repo, 폴더, 파일, 서비스, 화면, 모델, 데이터, 문서를 대상으로 하나?
- 원하는 최종 결과: 무엇이 바뀌거나 새로 만들어져야 하나?
- 현재 기준선: 현재 성능, 실패 로그, 테스트 상태, 품질 수준, 재현 방법은 무엇인가?
- 단계별 목표: 중간 단계별로 어떤 스펙이나 성능 수준을 만족해야 하나?
- 최종 목표: 숫자, 테스트 통과 조건, UX/기능 수용 기준, 보고서 산출물 등 완료 기준은 무엇인가?
- 검증 방법: 어떤 명령, 테스트, 벤치마크, 수동 확인, 스크린샷, 리포트로 성공을 판단할까?
- 제약/금지사항: 바꾸면 안 되는 API, 파일, DB, 비용, 보안, 라이선스, 호환성, 스타일 규칙은 무엇인가?

If the user asks for an immediate draft and information is incomplete, make explicit assumptions, mark them as assumptions, keep stretch disabled unless they opted in, and ask them to adjust the draft before use.

## Plan creation template

When creating a plan, use this structure:

```markdown
## 목표 요약
- 최종적으로 달성해야 할 결과:
- 작업 대상/범위:
- 명시적 비목표:

## 기준선과 가정
- 현재 상태/기준선:
- 확인해야 할 미지수:
- 가정:

## 단계별 계획
| 단계 | 작업 내용 | 단계별 목표 스펙/성능 수준 | 검증 방법 | 단계 완료 조건 |
|---|---|---|---|---|
| 1 | ... | ... | ... | ... |
| 2 | ... | ... | ... | ... |

## 최종 목표 스펙/성능
- 필수 완료 기준:
- 성능/품질 목표:
- 회귀 방지 기준:
- 산출물:

## 성능 목표 상향 정책
- 사용자 동의 여부: 예/아니오/미확인
- 동의한 경우: 필수 목표 달성 후 최대 3회까지 상향 가능
- 상향 가능한 지표:
- 상향 금지 범위:

## 중단/질문 조건
- 다음 경우에는 멈추고 사용자에게 보고:

## 진행 로그 규칙
- 각 체크포인트마다 현재 단계, 변경 사항, 검증 결과, 남은 일, 차단 여부를 짧게 기록한다.
```

## Plan review rubric

When reviewing an existing plan, return a compact review with `통과`, `보완 필요`, or `불충분`.

Check these items:

1. 목표가 하나의 durable objective로 정리되어 있는가?
2. 작업 단계/checkpoint가 있는가?
3. 모든 단계에 단계별 목표 스펙 또는 성능 수준이 있는가?
4. 최종 목표 스펙 또는 성능 수준이 명확한가?
5. 단계별 검증 방법과 최종 검증 방법이 있는가?
6. 작업 범위, 제약, 비목표가 있는가?
7. 회귀 방지 기준이 있는가?
8. 진행 로그 또는 체크포인트 보고 방식이 있는가?
9. 중단/사용자 질문 조건이 있는가?
10. 성능 목표 상향 opt-in 여부가 명시되어 있는가?

If the review is not `통과`, show the smallest patch needed to make it pass. Do not produce a final `/goal` prompt until the patched plan is sufficient, unless the user explicitly asks for a rough draft.

## Final `/goal` prompt generation

When the plan is sufficient, generate a copyable final prompt.

Prefer a direct `/goal` block when it is short enough. Keep it compact and action-oriented:

```text
/goal [목표 한 줄]

계획을 먼저 검토하고, 부족하면 계획을 보완한 뒤 실행한다.

작업 범위:
- ...

단계별 계획:
1. ...
   - 단계 목표 스펙/성능: ...
   - 검증: ...
2. ...
   - 단계 목표 스펙/성능: ...
   - 검증: ...

최종 완료 기준:
- ...

제약/비목표:
- ...

실행 정책:
- 각 단계 완료 후 검증을 실행하고 결과를 기록한다.
- 실패하면 원인을 분석하고 수정-검증 루프를 반복한다.
- 최종 완료 기준이 모두 통과할 때까지 멈추지 않는다.
- 단, 권한/비밀값/파괴적 변경/외부 장애/목표 infeasible 증거가 있으면 멈추고 근거와 다음 선택지를 보고한다.
- 진행 보고에는 현재 단계, 변경 사항, 검증 결과, 남은 일, 차단 여부를 포함한다.

성능 목표 상향 정책:
- [사용자가 동의하지 않았으면: 필수 목표 달성 후 추가 상향 없이 종료한다.]
- [사용자가 동의했으면 아래 정책을 포함한다.]
```

If the user opted into self-directed target increases, include this policy in the final goal:

```text
필수 목표를 모두 달성한 뒤에도, 안전하고 범위 내에서 개선 여지가 확인되면 최대 3회까지 성능/품질 목표를 상향한다. 각 상향 라운드마다 (1) 현재 검증된 기준선, (2) 새 목표 수치 또는 품질 기준, (3) 선택 이유, (4) 검증 방법을 진행 로그에 기록한다. 상향은 사용자가 허용한 지표에만 적용하며, 기능 범위 확대, 외부 동작 파괴, 비용/보안/호환성 제약 위반, 큰 리팩터링은 하지 않는다. 3회 상향을 완료하거나 더 이상의 안전한 개선 여지가 없으면 종료한다.
```

## Long goal handling

If the final goal would exceed roughly 3,500 characters, do not force everything into `/goal`.

Instead output:

1. A `GOAL_PLAN.md` body that can be written to the repo.
2. A short copyable goal:

```text
/goal Follow GOAL_PLAN.md exactly. First review the plan against its checklist, patch any missing plan details, then execute checkpoint by checkpoint until all final completion criteria pass. Keep a compact progress log. Pause only for missing approvals, credentials, destructive changes, external blockers, or evidence that the target is infeasible under the stated constraints.
```

## Output format

Use this order when possible:

1. `계획 검토` if reviewing or if the user provided a plan.
2. `보완 질문` if required.
3. `작성된 계획` if creating or patching a plan.
4. `복사용 /goal` when the plan is sufficient.
5. `사용 방법` with one or two lines only.

Do not bury the copyable `/goal` prompt in lengthy explanation. The user should be able to copy it directly.
