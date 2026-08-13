# Runtime Prompt Variants

Read this file only when producing a copyable final prompt. Select one target runtime and omit the other variant from the response.

## Shared direct-goal template

Adapt this template to the user's language and task. Remove empty sections rather than filling them with process boilerplate.

```text
/goal [사용자가 실제로 얻어야 하는 결과 한 줄]

이 목표에서 가장 중요한 결과:
- [제품, 동작, 분석 산출물 또는 의사결정]

진척 계약:
- 진척으로 인정: [실제 산출물, product delta 또는 측정된 후보 결과]
- 진척으로 인정하지 않음: [테스트·문서·검증 인프라만 증가한 상태]
- 초기 setup 이후 검증-only 작업을 두 번 연속 수행하지 않는다.

실행 단계:
1. [실제 산출물]
   - 최소 직접 검증: [...]
2. [실제 산출물]
   - 최소 직접 검증: [...]

최종 완료 기준:
- [요청 결과가 실제로 존재하거나 동작함]
- [필수 성능/품질 기준]
- [관련 회귀 방지]

범위와 검증 예산:
- 기존 실행·검증 경로를 우선 재사용한다.
- 새 verifier, schema, artifact 또는 service는 필수 기준을 기존 경로로 확인할 수 없을 때만 추가한다.
- 사용자 요청에 없는 외부·장기 검증을 완료 blocker로 추가하지 않는다.
- 자동 목표 상향은 비활성이다.

실행 지식:
- 시작·재개 시 전체 `failed-reports`/`passed-reports`의 current index(있을 때)와 원문을 함께 검색하고, exact signature·경로·환경·접근법 관련도순 후보에서 전문은 조회당 최대 5건만 읽는다. 현재 증거를 우선하며 stale 항목은 양방향 갱신한다.
- material failure는 재시도 전에 통합한다. 성공은 최종 기준 통과 후 실패 해결·기본안 실패 뒤 비자명한 대안·필수 재현 절차 중 하나일 때만 목표당 기본 1건 기록한다.
- 보고서·로그의 비밀·민감·고객/개인정보를 제거하고 필요하면 제한된 증거를 참조한다. 보고는 checkpoint나 진척이 아니며 최종 경로만 남긴다.

중단 조건:
- 권한, credential, 파괴적 변경, 외부 상태 변경 또는 실질적 범위 확대가 필요하면 근거와 선택지를 보고한다.
- 고정 조건에서 제한된 구현 iteration이 실패하면 기준을 완화하거나 검증기를 확장하지 말고 미달성 근거를 보고한다.
```

## Codex adaptation

For Codex, add this execution and final-evidence clause when relevant:

```text
- 반복 중에는 focused 검증을 사용하고, 위험에 비례한 최종 검증을 한 번 수행한다.
- 최종 보고에는 실제 산출물, 변경 파일, 실행한 핵심 검증과 결과, 완료 기준별 pass/fail, 남은 위험을 포함한다.
```

## Claude Code adaptation

Claude Code's `/goal` evaluator judges transcript-visible evidence. Add this clause:

```text
- 각 체크포인트의 product delta와 직접 검증 결과를 transcript에 간결하게 남긴다.
- 최종 transcript에는 실제 산출물, 변경 파일, 실행 명령과 결과 또는 exit code, 완료 기준별 pass/fail, 남은 위험을 포함한다.
- 파일에만 존재하고 transcript에 제시되지 않은 증거에 의존해 완료를 주장하지 않는다.
```

Keep the complete Claude Code `/goal` condition under 4,000 characters. If `/goal` is unavailable, omit the command prefix and identify the text as a plain execution prompt.

## Long-goal launch prompts

Use these only after creating or reviewing a complete `GOAL_PLAN.md`.

### Codex

```text
/goal Treat GOAL_PLAN.md as the authoritative outcome-first execution plan. Preserve its scope, progress contract, validation budget, completion criteria, and full execution-knowledge contract. Search the current report index when present plus all raw reports; rank exact relevance before recency and read at most five full reports per retrieval by default. Current evidence wins. Sanitize stored evidence, update stale or resolved reports and any active derived catalog in the same change, record material failures before retry, and create at most one qualified reusable success by default only after all final criteria pass. Reporting is not product progress or a separate checkpoint. After setup, advance through product or measured-result checkpoints, use focused verification during iteration, and run one risk-proportional final verification. Do not add verification programs or external gates unless the plan requires them or a real product defect makes them necessary. Ask before any material scope or validation expansion.
```

### Claude Code

```text
/goal Treat GOAL_PLAN.md as the authoritative outcome-first completion plan. Preserve its scope, progress contract, validation budget, completion criteria, and full execution-knowledge contract. Search the current report index when present plus all raw reports; rank exact relevance before recency and read at most five full reports per retrieval by default. Current evidence wins. Sanitize stored evidence, update stale or resolved reports and any active derived catalog in the same change, record material failures before retry, and create at most one qualified reusable success by default only after all final criteria pass. Reporting is not product progress or a separate checkpoint. After setup, each checkpoint must produce a product delta or measured result. Do not add verification programs or external gates unless required by the plan or a real product defect. The final transcript must show the resulting artifact or behavior, direct verification evidence, completion-criteria pass/fail, report paths, and remaining risks. Ask before material scope or validation expansion.
```
