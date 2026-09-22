# goal-planner 3.2.1 — GPT-6 Astra 안내 반영

3.2.0이 GPT-5.6 가이드를 기준으로 검토된 점을 정정하고, Astra의 행동 지침을 실제 SKILL과 인계 계약에 반영했다. [변경·사용 안내](ASTRA_UPDATE_KO.md) · [검토 근거](MODEL_GUIDE_REVIEW.md) · [검증 결과](VALIDATION.md)

이번 수정은 현재 모델·역할·예산·프로젝트 상태를 바꾸지 않는다. 기존 스킬은 검색 경로 밖에 백업하고 폴더 단위로 교체한다. 이미 생성된 계획은 필요한 계약만 병합한다. 아래 3.2.0과 3.1.0 절은 기능 이력이며, 모델별 최적화 상태는 현재 검토 문서를 따른다.

로컬 통합본은 후보 확증 기록의 충돌 처리와 CLI 입력 오류를 보완했고 자동 테스트 176개를 통과했습니다. 첨부본 결과와 로컬 보완·실제 검증 범위는 [검증 기록](VALIDATION.md)에 구분합니다.

---

# goal-planner 3.2.0 업데이트 (이력)

첨부 v3.1의 기능을 유지하면서 **평가기 우선 후보 탐색 계획**과 선택형 읽기 전용 도구를 추가했습니다. 일반 목표에는 후보군·다중 에이전트·새 DB를 강제하지 않습니다.

[새 기능 사용법](USAGE_V3_2.md) · [전체 조사 보고서](RESEARCH_REPORT_KO.md) · [연구 근거와 개선 계획](RESEARCH_AND_PLAN.md) · [현재 검증 기록](VALIDATION.md) · [모델 가이드 검토](MODEL_GUIDE_REVIEW.md)

아래 기존 안내도 계속 적용됩니다. 이 스킬은 목표/계획/인계 작성 도구이며 자동 연구 실행 엔진은 아닙니다.

---

# Goal Planner 3.1.0

연구·개발 에이전트가 수행할 목표와 실행 계약을 작성·검토하는 스킬입니다. **연구 프로그램 → 유한한 이정표 → 가설·실험**을 구분하여, 성과와 실패를 정직하게 확정하면서 승인된 범위 안에서 다음 연구 목표를 선택하도록 설계했습니다.

스킬 이름은 계속 `goal-planner`입니다. 3.1.0은 패키지 버전이며 특정 모델 버전이 아닙니다. 이 패키지는 실행기·스케줄러·자동 재시작 서비스가 아닙니다. 계획 작성과 프로젝트 실행의 승인은 별개이며, 실제 반복 실행·위임·세션 재개는 사용하는 호스트의 기능과 권한에 따릅니다.

## 3.1.0의 핵심 변경

중요 비교에서 선언된 비교군과 실제 구성·동작을 대조하고, 단일 요인·결합 효과·시스템 비교의 결론을 구분합니다. 실패 뒤 최소 진단과 후보 승격 확증을 분리하며, 중요한 판단에는 원시 증거를 먼저 보는 검토를 적용합니다. 보조 구성의 개선과 최종 목적의 능력을 연결하고, 미해결 주장과 실제 비용/상속 계보를 보존합니다. 본문뿐 아니라 실행자에게 복사되는 계약·템플릿에도 적용했습니다.

작은 수정에는 기존 Core 경로를 유지합니다. 새 도구·별도 모델·데이터베이스는 필수가 아니며, 특정 프로젝트·아키텍처·모델에 의존하지 않습니다. 복사해서 쓸 마이그레이션·연구·검증 프롬프트는 [USAGE.md](USAGE.md)에 있습니다.

## 설치와 이전 버전 교체

압축의 `goal-planner/` 폴더 **전체**를 아래 경로 중 하나에 넣습니다. `SKILL.md`만 교체하면 새 계약과 템플릿이 빠집니다.

| 도구 | 프로젝트별 경로 | 개인 경로 | 명시적 호출 |
|---|---|---|---|
| Codex CLI / IDE | `.agents/skills/goal-planner/` | `~/.agents/skills/goal-planner/` | `$goal-planner` |
| Claude Code | `.claude/skills/goal-planner/` | `~/.claude/skills/goal-planner/` | `/goal-planner` |

기존 폴더는 스킬 검색 경로 **밖에** 백업한 뒤 교체합니다. 프로젝트의 실패·성공·연구 기록과 현재 계획은 삭제하지 않습니다. 동일 이름의 구·신 버전이 여러 경로에 남지 않도록 확인합니다. 기존 사용자 정의와 이미 생성한 `GOAL_PLAN.md`는 [MIGRATION.md](MIGRATION.md)에 따라 필요한 부분만 병합합니다.

경로·호출은 2026-09-22 확인한 [OpenAI 스킬 문서](https://developers.openai.com/codex/skills/)와 [Claude Code 스킬 문서](https://code.claude.com/docs/en/skills)를 기준으로 작성했습니다. 이 배포본을 사용자의 실제 호스트에 설치해 실행한 검증은 수행하지 않았습니다. `/goal` 제공 여부는 별도 런타임 기능으로 확인해야 합니다.

## 두 가지 목표 모델

| 목표 모델 | 선택 조건 | 이정표가 끝나면 |
|---|---|---|
| `finite-goal` | 하나의 합의된 결과를 달성하는 일반 목표; 기본값 | 원래 기준으로 결과를 확정하고 종료 |
| `research-program` | 특정 주제의 지속 연구와 범위 안의 다음 목표 선택을 위임한 요청 | 결과·증거·사용 자원을 보존하고 유용한 다음 이정표 선택 |

한 목표를 위해 여러 실험을 반복하는 것만으로 다음 목표 선택까지 허용되지는 않습니다. 반대로 명확히 지속 연구를 맡겼다면 별도 모드 선언이나 같은 재승인을 반복해서 요구하지 않습니다. 지식 기록은 별도 `read-only` / `persist` 설정이며, 지속 연구 모드가 자동으로 저장소 변경이나 과금 권한을 주지 않습니다.

## 사용 예

### 계획 검토만

```text
$goal-planner
현재 GOAL_PLAN.md를 검토하고 필요한 수정안을 보여줘.
저장소 파일을 수정하거나 프로젝트 실행을 시작하지 마.
```

### 지속 연구용 목표 작성

아래 예시의 연구 주제·프로젝트 제약은 실제 상황에 맞게 바꿉니다. 이미 주어진 맥락은 다시 요구하지 않도록 설계되어 있습니다.

```text
$goal-planner
현재 연구/개발 주제와 기존 실험 결과를 바탕으로 지속 연구용 GOAL_PLAN.md를 작성해줘.
프로젝트 목적과 명시된 요구사항은 유지하고, 진행 결과에 따라 다음 이정표를 선택하는 것을 위임한다.
가설 수립, 리서치, 설계, 구현, 테스트, 결과 분석을 반복하도록 해줘.
기존 접근의 안정적 개선과 핵심 가정을 바꾸는 구조적 대안을 증거에 따라 선택하게 해줘.
기존에 승인한 개발 권한과 자원 한도를 적용하고, 새 목표에서 예산을 초기화하지 마.
실행 시 docs/researches와 기존 진행 로그에 실험 결과·재개 상태를 기록하는 것을 허용한다.
정식 실패·성공 보고서는 기존 승인 경로와 자격 규칙을 따른다.
이번에는 계획만 작성하고 실제 프로젝트 실행은 시작하지 마.
```

실제 실행까지 맡길 때는 마지막 문장을 “계획 작성 후 이미 승인된 범위에서 실행도 진행해줘”처럼 바꿀 수 있습니다. 이 경우 지원되는 실행 흐름으로 인계하되, 스킬 자체가 백그라운드 실행이나 세션 종료 후 재호출을 제공하는 것은 아닙니다. Claude Code는 첫 줄을 `/goal-planner`로 바꾸면 됩니다.

### 특정 개선 목표만 수행하도록 계획

```text
$goal-planner
현재 병목을 개선하는 단일 목표를 작성해줘.
처음 시도한 가설이 실패해도 근거와 승인된 자원이 남으면 다른 접근을 시도하도록 해줘.
단, 이 목표를 끝낸 뒤 별개의 새 목표를 자동으로 시작하지 마.
실제 구현은 아직 시작하지 마.
```

## 핵심 동작

이정표는 달성 가능한 제품 결과 또는 중요한 의사결정으로 정의합니다. 각 실험은 실행 전 예측·비교·유효성·판정 기준을 남기고 실행 후 관측과 연결합니다. `Validity`, `Hypothesis verdict`, `Adoption`, `Milestone outcome`은 별도로 기록합니다. 유효한 반증도 연구 기억에 남지만, 미달인 성능 개선 목표가 성공으로 바뀌지는 않습니다.

가장 최근 후보와 검증된 최선 산출물을 분리합니다. 큰 내부 구조 전환은 승인된 가역적 개발 범위에서 가능하지만 운영 변경·외부 데이터 삭제 권한과 같지 않습니다. 공유 자원·평가 노출·실패 이력은 목표나 세션이 바뀌어도 이어집니다. 재개 시 실제 파일·실행 상태와 기록을 대조하고 중복 실험을 피합니다.

실행 인계는 Core를 항상, Program·Experiment·Direction·Research·Retrieval·Persistence는 적용 조건에 따라 포함합니다. 필요한 블록은 계획 안에 한 번씩 전문을 넣어, 실행자가 스킬 내부 경로를 몰라도 핵심 계약을 받도록 합니다. 작은 수정에 연구 프로그램·대규모 검증·별도 데이터베이스를 강제하지 않습니다.

중요한 정보 공백이 있고 독립 작업·지원 도구·권한·공유 자원이 있을 때 제한된 연구 위임을 사용합니다. 역할·쓰기 소유권·결과가 필요한 시점·위임 깊이를 명시하고, 재하청 금지 등 호출자의 제약을 따릅니다. 위임 기능이 없으면 순차 조사로 대응합니다.

## 주요 파일

| 파일 | 역할 |
|---|---|
| [SKILL.md](SKILL.md) | 적용 범위, 목표 선택, 권한, 필요한 문서만 읽는 진입점 |
| [references/research-program.md](references/research-program.md) | 지속 연구, 다음 이정표, 공유 예산, 최선 산출물, 복구 |
| [references/experiment-protocol.md](references/experiment-protocol.md) | 가설·사전 예측·실험 판정·평가 신뢰성 |
| [references/empirical-verification.md](references/empirical-verification.md) | 실제 비교 의미·실패 뒤 진단·증거 우선 검토 |
| [assets/verification-template.md](assets/verification-template.md) | 중요한 결론의 선택적 검토 양식 |
| [scripts/experiment_preflight.py](scripts/experiment_preflight.py) | 선택적 읽기 전용 JSON·대조·해시 점검 |
| [examples/preflight/README.md](examples/preflight/README.md) | 실제 factory를 검사하는 범용 캐시 예제 |
| [USAGE.md](USAGE.md) | 설치·계획 갱신·지속 연구·검증 사용 예 |
| [references/execution-contract.md](references/execution-contract.md) | 7개 선택적 실행 계약 블록 |
| [references/execution-knowledge.md](references/execution-knowledge.md) | 조회·연구·보고서·기록 권한 |
| [references/runtime-prompts.md](references/runtime-prompts.md) | 계획 파일 또는 직접 실행 프롬프트 조합 |
| [assets/goal-plan-template.md](assets/goal-plan-template.md) | 계획 골격 |
| [assets/experiment-template.md](assets/experiment-template.md) | 실행 전 계획과 실행 후 결과가 분리된 실험 기록 |
| [assets/research-state-template.md](assets/research-state-template.md) | 세션 재개용 최소 상태 |
| [references/report-index.md](references/report-index.md) | 선택적 인덱스와 정확한 한글 호환 범위 |
| [CHANGELOG.md](CHANGELOG.md), [MIGRATION.md](MIGRATION.md) | 변경 내역, 이전 버전 적용 방법 |
| [MODEL_GUIDE_REVIEW.md](MODEL_GUIDE_REVIEW.md) | 이전 3.0.0의 가이드 검토 기록; 3.1.0의 새 검토 결과는 아님 |
| [VALIDATION.md](VALIDATION.md), [tests/README.md](tests/README.md) | 검증 결과·재현 명령·한계 |

변경 이력·가이드 검토·검증 문서는 배포 검토용입니다. 에이전트가 매번 모든 문서를 읽어야 하는 실행 요구사항은 아닙니다.

## 선택적 인덱스 업그레이드

표준 라이브러리 기반 `scripts/report_index.py`의 generator는 `1.1.0`, catalog schema는 기존 `1`입니다. 이전 generator의 카탈로그는 원문 검색으로 복구하며 보고서 전체 재작성은 필요하지 않습니다. 새 기록은 영어 기계 키·열거 값을 유지하고 자유 서술은 한국어로 작성할 수 있습니다. 문서화한 한글 키·상태 별칭도 지원하되, 임의 번역이나 모순된 상태를 추측해 정상 처리하지 않습니다.

인덱스가 이미 있고 교체·기록 권한이 있을 때만 저장소 사본을 갱신한 후 실행합니다.

```bash
python3 docs/report-index/report_index.py sync --root .
python3 docs/report-index/report_index.py check --root .
```

`sync`의 쓰기 완료와 `check`의 정합성 통과는 별개입니다. 조회만 허용되면 `query` 또는 원문 검색을 사용합니다. 연구·실험 노트는 실행 보고서 카탈로그에 자동 편입되지 않습니다.

## 검증

```bash
cd goal-planner
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
```

선택적 도구와 테스트는 Python 3.10 이상 문법을 사용하고 외부 패키지·API 키가 필요하지 않습니다. 실제 확인 환경은 [VALIDATION.md](VALIDATION.md)에 기록합니다. 계획 작성만 하는 데 Python은 필요하지 않습니다.

로컬 통합본의 자동 검사는 기존 56개에 구성 점검 35개와 새 계약/평가 정의 검사 8개를 추가한 총 99개 테스트 메서드입니다. 첨부 원본의 96개에 CLI 경계 입력 회귀 3개를 추가했습니다. 기존 행동 정의 64개와 새 실증 검증 fixture 16개는 정의 파일에서 `not_run`을 유지하며, 별도 세션 평가 결과는 정의와 분리해 기록합니다. 작동 예제와 자동 검사는 장기 연구 성과, 호스트 연동, 모델별 성능 향상을 입증하지 않습니다. 실제 실행 결과와 한계는 [VALIDATION.md](VALIDATION.md)에 있습니다.
