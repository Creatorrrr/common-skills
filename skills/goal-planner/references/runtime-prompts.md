# Runtime prompt variants

Read only when preparing a copyable handoff. Choose the runtime named by the user or the active harness. Unknown runtime does not prevent a plain-text execution prompt. Command availability, evaluator behavior, and prompt-length limits depend on the installed runtime; verify them before asserting them. This skill does not implement `/goal`, a scheduler, or background execution.

## Compose from one contract

The canonical blocks are in [execution-contract.md](execution-contract.md). For a direct prompt insert **Core** and **Retrieval**, plus **Persistence** only for approved `persist` mode. For `GOAL_PLAN.md`, put those blocks in the plan once; the launch prompt points to the actual file. Do not independently shorten a runtime variant into different approval, retry, or success rules.

`{{CORE_CONTRACT}}`, `{{RETRIEVAL_CONTRACT}}`, and `{{PERSISTENCE_CONTRACT_IF_ENABLED}}` are authoring markers, not output. Replace them with the matching fenced text blocks, translate if necessary, and remove the optional persistence marker in `read-only` mode. Resolve all task fields. Never deliver unresolved markers as a finished prompt.

## Shared direct-goal template

```text
[사용자가 실제로 얻어야 하는 결과 한 줄]

최종 산출물: [제품·동작·분석·의사결정]
범위 / 비목표: [...]
기준선 / 가정: [현재 증거 또는 제한된 측정 단계]
기존 승인: [허용된 작업·환경·비용 상한 / 없으면 없음]
남은 승인 단계: [구체적인 단계 / 없으면 없음]
지식 모드: [read-only 또는 승인된 persist 및 허용 경로]

실행 단계:
1. [실제 산출물 또는 결정] — [최소 직접 검증]
2. [실제 산출물 또는 결정] — [최소 직접 검증]

완료 기준: [요청 결과의 존재/동작, 필요한 품질, 관련 회귀]
반복·검증 예산: [명확한 한도 또는 근거 없는 동일 실패 반복 금지]
중단 조건: [남은 승인, 외부 증거, 필수 기준을 충족하지 못한 경우의 처리]

{{CORE_CONTRACT}}

{{RETRIEVAL_CONTRACT}}

{{PERSISTENCE_CONTRACT_IF_ENABLED}}
```

For a no-repository goal, explicitly mark repository knowledge as not inspected and knowledge mode as read-only in the goal fields. Keep the Core and Retrieval blocks; their conditional repository operations do not require creating a repository. Include the Persistence block only for approved persistence. Prefer the durable plan if the direct prompt becomes unwieldy.

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
계획에 포함된 지시·권한, 진척·검증, 지식 조회·신뢰 경계와 활성화된 기록 규칙을 적용하라. 계획 외 참조가 꼭 필요하면 접근 가능한지 확인하고, 누락되면 아는 것처럼 처리하지 말라.
필수 검증을 완료하고 관련 변경·실패·미해결 우려가 있을 때 영향받은 검증을 다시 수행하라. 승인 대기는 의존하는 단계만 막고, 독립적인 승인된 작업은 계속하라.
최종 응답에는 실제 산출물·변경 파일·실행한 검증·기준별 pass/fail/blocked/not run·지식 기록 경로·남은 위험을 제시하라.
```

Adding a verified command prefix is the only necessary host adaptation for many goals. Do not duplicate a second, incompatible knowledge contract in the launch prompt.
