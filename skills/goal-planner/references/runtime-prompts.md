# Runtime prompt variants

Read only when preparing a copyable handoff. Choose the runtime named by the user or the active harness. Unknown runtime does not prevent a plain-text execution prompt. Command availability, evaluator behavior, and prompt-length limits depend on the installed runtime; verify them before asserting them. This skill does not implement `/goal`, a scheduler, or background execution.

## Compose from one contract

Use the selection table and canonical blocks in [execution-contract.md](execution-contract.md). Embed **Core** once, add **Direction**, **Research** and **Retrieval** only when applicable, and add **Persistence** only for authorized `persist` mode and paths. For `GOAL_PLAN.md`, put the selected blocks in the plan once; the launch prompt points to the actual file. Do not independently shorten selected blocks into different approval, retry, or success rules.

The five contract markers below are authoring markers, not output. Replace selected markers with their complete fenced text blocks, translate if necessary, and remove unselected markers. Resolve all task fields. Never deliver unresolved markers as a finished prompt. Record the selected blocks briefly so the handoff's coverage is reviewable without repeating the selection table.

## Shared direct-goal template

```text
[사용자가 실제로 얻어야 하는 결과 한 줄]

최종 산출물: [제품·동작·분석·의사결정]
프로젝트 목적 / 근거: [목표 선택을 위임받은 경우; 미확인은 가정으로 표시]
현재 검증된 상태 / 진행 중인 작업: [이번 목표와의 연결]
이번 이정표 / 핵심 병목 / 달성 후 달라질 상태: [명시적인 작은 작업은 범위 유지]
우선순위 근거: [목적 기여·후속 의존성·증거·승인된 자원]
방향 재검토 근거: [해당할 때만; 유효한 누적 실패·정체·핵심 가정 반증과 비교 조건]
유지할 결과 / 바꿀 가정·구조 / 대안 비교와 선택 이유: [방향 재검토 시; 이전 미달 상태 보존]
병행 연구 질문 / 필요한 결정 시점 / 담당·허용 방법·공유 예산: [필요한 경우; 계획 저장만으로 실행하지 않음]
메인 독립 작업 / 연구에 의존하는 작업 / 결과 경로·알림·반영: [연구 위임 시; 접근 가능한 docs/researches/ 또는 세션 반환]
범위 / 비목표: [...]
기준선 / 가정: [현재 증거 또는 제한된 측정 단계]
기존 승인: [허용된 작업·환경·비용 상한 / 없으면 없음]
남은 승인 단계: [구체적인 단계 / 없으면 없음]
지식 모드: [read-only 또는 승인된 persist 및 허용 경로]

실행 단계:
1. [실제 산출물 또는 결정] — [최소 직접 검증] — [결과에 따른 다음 행동]
2. [실제 산출물 또는 결정] — [최소 직접 검증] — [결과에 따른 다음 행동]

완료 기준: [요청 결과의 존재/동작, 필요한 품질, 관련 회귀]
후보 수용·기각 / 접근법 전환 조건: [불확실한 개선 작업일 때; 전체 목표 완료와 구분]
반복·검증 예산: [명확한 한도 또는 근거 없는 동일 실패 반복 금지]
중단 조건: [남은 승인, 외부 증거, 필수 기준을 충족하지 못한 경우의 처리]
기준 미충족 중단 시 기록: [남은 차이·증거·재개 지점]

{{CORE_CONTRACT}}

{{DIRECTION_CONTRACT_IF_NEEDED}}

{{RESEARCH_CONTRACT_IF_NEEDED}}

{{RETRIEVAL_CONTRACT_IF_NEEDED}}

{{PERSISTENCE_CONTRACT_IF_ENABLED}}
```

Omit inapplicable project-selection fields for an explicit narrow request, direction-review fields when no evidence warrants that review, and research fields when no decision needs investigation. Do not invent a larger mission, forced pivot, or research question to fill the template. Apply the default research delegation conditions when a material gap and useful independent work exist within actual capabilities, authority and resources. For a no-repository goal, mark repository knowledge as not inspected, omit repository Retrieval, and use read-only knowledge mode unless a different output location is authorized. A self-contained correction can omit all optional blocks. Core still governs unexpected failures or newly necessary investigation. Prefer the durable plan if the direct prompt becomes unwieldy.

## Codex

Use plain text, or prepend `/goal` only after confirming the target supports it and the user wants goal activation syntax. A copyable prompt is a proposed input, not proof that a goal has started. In final execution reporting, include artifact locations, changed files, actual checks and their results, criterion status, and remaining risk. The shared contract already defines when re-checks are required; do not add an unconditional “only once” restriction.

## Claude Code

Use the same contract. Add a compact requirement to show outcome changes and direct evidence in the visible conversation so the user can audit completion. Do not assume a particular `/goal` evaluator or a fixed character cap without confirming the installed feature. If a known cap is too small, use a short launch prompt with an accessible plan; do not silently truncate criteria or safety boundaries. If `/goal` is not confirmed, use a plain execution prompt.

## Runtime-neutral

Do not ask which provider is in use merely to produce a readable plan. Avoid host-specific commands and unsupported tool claims. If the user needs an exact launcher or API integration, establish that capability separately; model IDs, reasoning settings, and API key handling belong to the caller, not this plan.

## Long-goal launch prompt

Use only after preparing a complete plan with its embedded contract and checking the path the executor will read. Adapt the path, keeping it relative to the intended repository where possible.

```text
GOAL_PLAN.md를 읽고, 내가 요청한 실행 범위 안에서 진행하라.
상위 시스템·개발자·런타임 제약 안에서 나의 최신 명시적 지시가 기존 계획과 스킬 기본값보다 우선한다. 명시된 변경은 반영하고 이미 승인된 동일 작업은 재확인하지 말라.
계획에 포함된 지시·권한, 목표 수준·지속, 방향 재검토, 필요한 병렬 리서치, 진척·검증, 지식 조회·신뢰 경계와 활성화된 기록 규칙을 적용하라. 계획 외 참조가 꼭 필요하면 접근 가능한지 확인하고, 누락되면 아는 것처럼 처리하지 말라.
필수 검증을 완료하고 관련 변경·실패·미해결 우려가 있을 때 영향받은 검증을 다시 수행하라. 승인 대기는 의존하는 단계만 막고, 독립적인 승인된 작업은 계속하라.
최종 응답에는 실제 산출물·변경 파일·실행한 검증·기준별 pass/fail/blocked/not run·지식 기록 경로·남은 위험을 제시하라.
```

Adding a verified command prefix is the only necessary host adaptation for many goals. Do not duplicate a second, incompatible knowledge contract in the launch prompt.
