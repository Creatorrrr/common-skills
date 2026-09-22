# Goal Planner 3.1.0 검증 기록

## 로컬 통합 검증 — 2026-09-22

첨부 ZIP을 현재 설치된 3.0.0 및 개발 대화의 마지막 개선안과 대조했습니다. 아래는 macOS 27.0 arm64의 실제 로컬 결과이며, 뒤쪽의 제공된 Linux 배포 기록과 구분합니다.

| 검사 | 결과 | 근거와 범위 |
|---|---|---|
| 첨부 ZIP | SHA-256 `bfee16b07d36b77deb2cd0e7aee0541c63d0b9c6c232d50f345cb439468c4523`; CRC·경로·파일 집합 및 manifest 60개 일치 | 원본 다운로드 보존, manifest 자체 제외 |
| 원본 3.1.0 재실행 | Python 3.14.3에서 96개 통과 | [원시 로그](tests/evidence/v3.1-local-upstream-unittest.txt) |
| 로컬 보완본 | Python 3.14.3에서 **99개 통과, 실패·건너뜀 0** | [원시 로그](tests/evidence/v3.1-local-unittest.txt) |
| 이전 Python의 새 도구 | Python 3.12.13에서 35개 통과 | [점검 도구 로그](tests/evidence/v3.1-local-python312-preflight.txt); 전체 패키지의 다중 버전 검증은 아님 |
| 정적 검사 | skill-creator `quick_validate.py` 통과; Ruff 0.16.4 통과 | [Ruff 로그](tests/evidence/v3.1-local-ruff.txt), [정적 점검 및 예제 결과](tests/evidence/v3.1-local-static.json) |
| 설치 후 확인 | 계약 테스트 28개 통과, 연결 경로의 VERSION 3.1.0 및 파일 집합·해시 일치 | 정적 점검 기록의 `installation`·`installed_contracts` 항목 |
| 실제 factory 예제 | 정상 코드 0, 의도적 결함 코드 1 | 두 군 모두 캐시가 켜진 결함에서 선언·대조 불일치 검출 |
| 보존·참조 | 기존 인덱스 코드·64개 행동 정의·3.0 검증 문서 바이트 동일, 내부 문서 링크 유효 | 과거 결과를 이번 실행으로 재분류하지 않음 |
| 별도 세션 표본 | E01·E04·E10 세 사례의 검토/계획 평가 통과 | [입력·출력·명령·판정 기록](tests/evidence/v3.1-local-forward-samples.json) |

원본에서 5,000자리 정수 및 NUL 문자가 든 증거 경로를 넣으면 JSON 없이 종료 코드 1과 traceback이 발생했습니다. [수정 전 재현](tests/evidence/v3.1-local-edge-before.json)을 보존했습니다. 네이티브 JSON/경로의 `ValueError`와 이전 Python의 경로 순환 `RuntimeError`를 입력 오류로 처리하여 코드 2와 오류 JSON을 반환하도록 수정했습니다. 세 회귀 테스트는 큰 정수·NUL 경로·순환 심볼릭 링크를 실제 CLI로 확인합니다. 정상/불일치 판정 및 실행 계약은 바꾸지 않았습니다.

행동 표본은 부모 대화 이력을 복제하지 않은 `gpt-6-astra` 세 세션에 각각 스킬과 한 사례의 입력만 제공했습니다. E01은 두 군이 모두 `MemoryCache`라는 모순을 찾고 캐시 효과 해석을 보류했으며, E04는 기존 실패와 20 CPU분 한도를 보존하는 진단·결정 분기를 작성했습니다. E10은 오타 한 건에 필요한 간단한 계획만 작성했습니다. 실제 도구 기록은 지정 파일의 읽기뿐이며 입력 해시도 변하지 않았습니다. 초기에 검증 준비 과정의 경로 오류로 세 세션이 입력을 찾지 못해 중단한 기록을 보존했고, 경로만 바로잡은 뒤 같은 세션에서 이어갔습니다. 이를 스킬의 행동 실패나 추가 성공 표본으로 세지 않았습니다.

이는 세 개의 선택된 검토/계획 표본이며, 80개 전체 행동 평가·3.0 대비 비교 실험·구현 실행·장기 자율 연구의 검증이 아닙니다. 같은 모델 계열의 별도 세션을 통계적으로 독립적이라고 주장하지 않습니다. 정의 파일의 `not_run`은 그대로 두고 실제 결과를 별도 기록했습니다.

로컬 설치는 `/Users/chasoik/Projects/common-skills/skills/goal-planner`에 반영했습니다. Codex의 `~/.agents/skills/common-skills`와 Claude Code의 `~/.claude/skills/goal-planner`가 이 저장소를 가리키는 연결 경로를 확인했습니다. 기존 3.0.0은 검색 경로 밖인 `/Users/chasoik/.codex/backups/goal-planner/2026-09-22T142248+0900/goal-planner`에 보존했습니다. 파일 연결 확인과 별도 표본의 명시적 스킬 로딩은 일반 호스트의 자동 탐색·재시작 검증과 구분합니다. 기존 프로젝트 계획은 자동 갱신되지 않습니다.

---

## 제공된 배포본의 검증 기록 — 아래 원문 보존

검증일: 2026-09-22. 환경: Linux, Python 3.13.5. 사용자 제공 3.0.0 패키지를 복사한 별도 작업본에서 수정·검사했습니다. 원본 프로젝트, 원본 압축 파일, 사용자의 실제 설치 경로는 수정하지 않았습니다. 선택적 도구는 Python 3.10 이상 문법으로 작성했으며, 이번 실행 검증은 아래 환경 한 종류입니다.

## 실제 수행 결과

| 검사 | 결과 | 범위 |
|---|---|---|
| 제공된 3.0.0 기준선 | 56개 통과 | 기존 자동 테스트 |
| 3.1.0 기존 테스트 | 56개 통과 | 인덱스·복구·한글·기존 계약 |
| 새 preflight 테스트 | 32개 통과 | 실제/선언 불일치, 초기 조건, reset, 평가기, 해시, 입력·경로·읽기 전용 CLI |
| 새 정적 계약 테스트 | 8개 통과 | 실행 인계·템플릿·경량 경로·행동 fixture 정의 |
| 3.1.0 전체 메서드 | **96개 통과, 실패 0, 건너뜀 0** | 모듈별 실행 결과 합계 |
| 작동 예제 | 정상 구성 코드 0, 의도적 결함 코드 1 | 실제 factory와 put/get/reset probe; 자동 코드 테스트에도 포함 |
| 원본 행동 정의 | 64개 바이트 동일, 모두 `not_run` | 과거 정의 보존; 새 모델 실행 아님 |
| 추가 행동 정의 | 16개, 모두 `not_run` | 실행 가능한 입력 fixture와 평가 기준만 준비 |

전체 테스트를 한 번에 실행한 호출 2개는 작업 환경의 호출 시간 제한으로 완료되지 않았습니다. 이를 통과로 세지 않고 모듈별로 나눠 **96개 전부를 완료**했습니다. 새로운 기준선이나 완화된 테스트로 교체하지 않았습니다. 기존 테스트의 동작은 보존했으며 버전 기대값만 3.1.0으로 갱신했습니다. 새 정합성 도구가 발견하는 의도적 오류와 테스트 자체의 실패는 구분합니다.

모듈별 원시 로그는 [v3.1-unittest.txt](tests/evidence/v3.1-unittest.txt), 코드·원본 보존·범용성 정적 확인은 [v3.1-release-checks.json](tests/evidence/v3.1-release-checks.json)에 기록합니다. 기존 `report_index.py`와 기존 행동 정의는 내용이 변경되지 않았습니다.

## 도구가 증명하는 범위

`experiment_preflight.py`의 코드 0은 **제공된 선언·관측 사실·대조·파일 해시의 기계적 정합성**입니다. `scientific_validity` 및 `source_coverage_and_exporter_truth`는 언제나 `not_established`입니다. 도구는 대상 프로젝트를 import하거나 실행하지 않으며, 실제 exporter의 정직성·모든 실행 소스의 포함·누락된 혼란변수·평가 누출을 검증하지 않습니다. 권한 격리나 실행 게이트도 자동 설치하지 않습니다.

정상/오류 예제는 작은 범용 캐시 구현의 구성·동작 검사입니다. 이를 새로운 연구 성과나 성능 향상 실험으로 표현하지 않습니다. 실제 예제 출력은 [v3.1-preflight-demo.json](tests/evidence/v3.1-preflight-demo.json)에 있습니다.

## 미실행 범위

총 80개 행동 정의를 새 에이전트 세션으로 평가하지 않았습니다. 실제 모델의 계획 품질·오류 발견률·장기 무감독 연구·성능 향상·자동 위임·재시작·Codex/Claude Code 설치 연동은 **미검증**입니다. 별도 모델 세션의 독립성이나 모델 간 우열도 실험하지 않았습니다. 자동 코드 테스트와 문구 계약 검사는 이런 효과를 대신 증명하지 않습니다.

실제 행동 평가는 [BEHAVIORAL_EVAL.md](tests/BEHAVIORAL_EVAL.md)에 입력·출력·도구 기록·판정 근거를 남기는 절차로 구분했습니다. 이번 검증에서 모델 API, 외부 유료 실행, 대상 프로젝트 실험은 사용하지 않았습니다. 설치 경로·호출은 공식 문서로 확인했지만 기기별 실설치 시험은 수행하지 않았습니다.

## 재현

패키지 루트에서:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
```

호출 시간이 제한된 환경에서는 테스트 파일별로 실행할 수 있습니다. 예를 들어:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_experiment_preflight.py' -v
```

Python 캐시는 패키지의 청결 검사와 배포 해시에 영향을 주므로 위 옵션을 유지합니다. 선택적 예제의 전체 명령과 예상 종료 코드는 [examples/preflight/README.md](examples/preflight/README.md)에 있습니다.

`MANIFEST.sha256`은 자신을 제외한 모든 배포 파일을 열거합니다. `sha256sum -c MANIFEST.sha256` 또는 동등한 SHA-256 도구로 확인할 수 있습니다. ZIP을 재추출한 파일 집합과 해시도 배포 과정에서 대조합니다. 사용자 수정 이후 원본 배포 해시와 달라지는 것은 정상입니다.

## 과거 기록

3.0.0의 검증 문서는 [VALIDATION_V3_0.md](VALIDATION_V3_0.md), 더 오래된 기록은 [VALIDATION_HISTORY.md](VALIDATION_HISTORY.md)에 보존했습니다. 과거 모델 표본·macOS 설치·Ruff 실행·모델 가이드 검토를 이번 버전의 새 실행 결과로 재분류하지 않았습니다.
