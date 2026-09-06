# Goal Planner 2.1.0

장기 실행 목표, `GOAL_PLAN.md`, 계획 검토, 실행용 프롬프트를 작성하는 스킬입니다. 원래의 결과 우선 설계와 실패·성공·연구 지식 재사용을 유지하고, 지시 우선순위·작업 경계·승인·재검증 규칙을 정리했습니다.

**스킬 이름은 계속 `goal-planner`입니다.** 2.1.0은 스킬 패키지 버전이며 특정 모델 버전이 아닙니다. 목표 선택을 위임받으면 프로젝트 목적과 현재 진행 상황을 바탕으로 중요한 병목·역량 부족·기술적 결정을 해소하는 이정표를 정합니다. 계획 파일 작성과 프로젝트 실행은 구분됩니다. 이 패키지는 모델·API·유료 서비스를 자동으로 호출하거나 목표를 백그라운드에서 실행하지 않습니다.

## 설치

압축을 풀면 나오는 `goal-planner/` 폴더 **전체**를 사용하는 도구의 스킬 경로에 넣습니다. `SKILL.md`만 교체하면 새 참조 파일이 빠지므로 정상적인 인계 규칙을 사용할 수 없습니다.

| 도구 | 프로젝트별 설치 | 사용자 전체 설치 | 호출 예 |
|---|---|---|---|
| Codex CLI / IDE | `.agents/skills/goal-planner/` | `~/.agents/skills/goal-planner/` | `$goal-planner` |
| Claude Code | `.claude/skills/goal-planner/` | `~/.claude/skills/goal-planner/` | `/goal-planner` |

기존 폴더는 스킬 검색 경로 밖에 백업한 뒤 교체합니다. 같은 이름의 구·신 스킬이 여러 위치에서 발견되지 않도록 확인합니다. **프로젝트의 `docs/failed-reports`, `docs/passed-reports`, `docs/researches`는 삭제하거나 덮어쓰지 않습니다.** 기존 사용자 정의가 있다면 [CHANGELOG.md](CHANGELOG.md)를 기준으로 병합합니다.

설치 경로와 호출 형식은 2026-09-05 확인한 [OpenAI 스킬 문서](https://developers.openai.com/codex/skills/) 및 [Claude Code 스킬 문서](https://code.claude.com/docs/en/skills)를 기준으로 작성했습니다. 실제 설치된 호스트에서 이 패키지를 로드하는 연동 검증은 이번에 수행하지 않았습니다. `/goal` 자체의 제공 여부는 별도 기능이므로 현재 런타임에서 확인하도록 설계했습니다.

## 사용 예

### 계획 검토만

```text
$goal-planner
현재 GOAL_PLAN.md를 검토하고 최소 수정안을 보여줘.
저장소 파일이나 보고서는 수정하지 마.
```

### 계획 파일만 작성

```text
$goal-planner
[달성할 결과와 제약]을 위한 GOAL_PLAN.md를 작성해줘.
실제 구현은 하지 말고, 보고서·연구 디렉터리도 초기화하지 마.
```

### 장기 실행용 지식 기록까지 준비

```text
$goal-planner
[달성할 결과와 제약]을 위한 GOAL_PLAN.md를 작성해줘.
실행 시 지식 모드는 persist로 하고, docs/failed-reports,
docs/passed-reports, docs/researches에 기록하는 것을 허용한다.
해당 디렉터리와 누락된 템플릿도 초기화하되 기존 파일은 보존해줘.
프로젝트 실행은 아직 하지 마.
```

Claude Code에서는 첫 줄을 `/goal-planner`로 바꾸면 됩니다. 사용자 언어로 결과를 작성하며, 개인용 보조 스킬이나 특정 상·하위 모델을 요구하지 않습니다. 실제 실행을 같은 요청에서 명확히 승인한 경우에는 계획 완료 후 해당 실행 흐름으로 넘기며 동일 승인을 다시 요구하지 않도록 했습니다.

## 주요 파일

| 파일 | 역할 |
|---|---|
| [SKILL.md](SKILL.md) | 진입점: 적용 범위·지시 우선순위·모드·계획/검증 규칙 |
| [references/execution-contract.md](references/execution-contract.md) | 직접 프롬프트와 계획에 삽입할 공통 실행 규칙 |
| [references/execution-knowledge.md](references/execution-knowledge.md) | 조회·기록·신뢰 경계·생명주기 상세 |
| [references/runtime-prompts.md](references/runtime-prompts.md) | Codex·Claude Code·일반 텍스트 실행 인계 |
| [references/report-index.md](references/report-index.md) | 기존 인덱스 사용·도입 조건·오류 복구·업그레이드 |
| [assets/goal-plan-template.md](assets/goal-plan-template.md) | 계획 작성용 골격; 완성본에서는 삽입 표식을 실제 규칙으로 치환 |
| `assets/*report-template.md`, `assets/research-*.md` | 승인된 보고서·연구 저장에 사용하는 템플릿 |
| `scripts/report_index.py` | 표준 라이브러리만 사용하는 선택적 인덱스 도구 |
| [tests/README.md](tests/README.md) | 자동 검사와 실제 모델 행동 평가의 구분 |
| [CHANGELOG.md](CHANGELOG.md) / [VALIDATION.md](VALIDATION.md) | 수정 사항 / 실제 검증 결과와 한계 |

## 기존 사용 시 달라지는 점

“권장하는 방향으로 목표 작성하고 진행해줘”처럼 목표 선택과 실행을 맡기면 프로젝트 목적 → 이번 이정표 → 실행 단계를 연결합니다. 목표의 크기는 달성 후 달라질 상태로 판단합니다. 첫 후보의 실패만으로 개선 목표를 종료하지 않고 근거와 승인된 예산이 남으면 같은 목표 안에서 다음 접근을 수행하도록 인계합니다. 명시적인 작은 작업·분석 전용 요청과 시간·비용 상한은 유지합니다. 빠르게 기준을 충족하면 완료하고, 개선에 실패한 결과를 가설 연구 성공으로 바꾸지 않습니다.

기본 지식 모드는 `read-only`입니다. 사용자 요청이나 이미 승인된 저장소 작업 흐름이 기록을 포함할 때 `persist`로 설정합니다. **조회 권한, 기록 권한, 초기화 권한을 구분합니다.** 기존 보고서가 있다는 이유만으로 새 기록을 승인한 것으로 간주하지 않습니다.

실패 직후에는 증거와 다음 시도 차이를 최소 기록하고, 정식 보고서는 다음 의미 있는 체크포인트 또는 종료 시 정리합니다. 같은 체크포인트에서 테스트와 lint를 연속 실행할 수 있습니다. 관련 코드를 수정했다면 최종 검증을 이미 했더라도 영향받은 검증을 다시 수행합니다.

새로 만드는 계획은 필요한 공통 실행 규칙을 내장합니다. 기존 `GOAL_PLAN.md`나 이미 복사해 둔 실행 프롬프트는 스킬 폴더 교체만으로 바뀌지 않습니다. 기존 계획은 이 스킬로 재검토하여 충돌 문구를 수정해야 합니다.

## 인덱스 업그레이드

카탈로그 스키마는 `1`을 유지하며 generator는 `1.0.0`에서 `1.0.1`로 변경했습니다. 원문 보고서와 필드 이름을 마이그레이션할 필요는 없습니다. 이전 generator의 카탈로그는 stale로 판정되어 원문 검색으로 복구됩니다.

프로젝트에 인덱스가 이미 설치되어 있고 교체·재생성이 승인되어 있다면, 이 패키지의 `scripts/report_index.py`를 기존 저장소 도구 위치에 반영한 다음 실행합니다.

```bash
python3 docs/report-index/report_index.py sync --root .
python3 docs/report-index/report_index.py check --root .
```

`sync`가 파일을 썼다는 것과 생명주기까지 유효하다는 것은 다릅니다. `check`의 성공을 확인합니다. 검토만 요청했거나 쓰기가 불가하면 이 명령을 실행하지 않고 원문 검색을 유지합니다. 인덱스가 없는 소규모 프로젝트에 설치할 필요는 없습니다.

## 테스트

인덱스 도구와 테스트는 Python 3.10 이상을 대상으로 작성했습니다. 버전별 실제 검증 환경과 결과는 [VALIDATION.md](VALIDATION.md)에 기록합니다. 계획 작성만 할 때 Python 실행은 필수가 아닙니다.

```bash
cd goal-planner
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
```

자동 검사는 인덱스 코드와 정적 패키지 구조를 확인합니다. 행동 평가 정의는 26개이며 자동 검사로 실행되지 않습니다. 별도 계획 생성 표본과 실제 장기 실행·호스트 연동·모델 간 비교는 구분하여 [VALIDATION.md](VALIDATION.md)에 기록합니다.
