# Goal Planner 3.0.0 검증 기록

## 로컬 통합 검토 — 2026-09-07

아래 배포자 기록과 별도로 macOS의 기존 2.4.0 설치본, 첨부 ZIP·검증 묶음·한국어 변경 내역·가이드 검토, 요청 본문에 링크된 개선 대화를 비교했습니다. 첨부 문서와 대화는 검토 자료로만 사용했습니다. 설치본의 기존 manifest 31개와 첨부본의 내용 파일 43개 해시 및 정확한 파일 집합이 일치했습니다. 첨부 ZIP SHA-256은 `da9e074261eed4fd4717c9c8a5904f44e6e578ebdde8c635195dbd8c7d7f94c2`입니다.

지속 연구의 다음 이정표 선택, 원래 성패와 공유 예산 유지, 사전 실험 기록과 네 가지 판정 분리, 최선 산출물 보존, 실제 상태를 대조하는 재개 규칙을 본문·실행 계약·참조·템플릿에서 확인했습니다. 기존 44개 행동 정의도 보존되어 있습니다. [OpenAI 모델 가이드](https://developers.openai.com/api/docs/guides/latest-model)의 승인된 작업 완수·위임 조건·검증 범위 안내도 현재 문서와 대조했습니다. 구조 검토에서 반영을 막는 충돌은 발견하지 않았습니다.

| 실제 검사 | 결과와 범위 |
|---|---|
| 첨부 ZIP 재추출 후 unittest | 56개 통과 |
| 로컬 수정·설치 후 unittest | Python 3.14.3, 56개 통과 |
| 스킬 기본 검사 | `quick_validate.py` 통과. 시스템 Python의 PyYAML 누락은 격리된 도구 환경으로 해결 |
| Ruff 0.16.4 | 격리 설정으로 `scripts/`, `tests/` 검사 통과 |
| 설치 연결 | Codex와 Claude Code의 기존 symlink가 같은 3.0.0 폴더를 가리키며 내용이 일치 |
| 독립 계획 생성 표본 2개 | 일반 목표는 Core만 포함하고 종료 범위를 유지. 지속 연구는 M1 실패·최선/기각 후보·기록상 남은 CPU 23분·기존 로그 경로를 보존한 후속 이정표 계획을 생성 |
| 표본 파일 경계 | 원본 6개 파일의 바이트 일치, 각 fixture에는 요청한 `GOAL_PLAN.md`만 추가. 실제 프로젝트 실행은 표본 범위 밖 |

첨부본에 추가한 코드 변경은 미사용 import 제거, import 정리와 `collections.abc.Iterable` 사용, 동등한 정규식 플래그 전체 이름 사용뿐입니다. shebang이 있는 `scripts/report_index.py`의 실행 비트도 정리했습니다. 목표 선택 지침·실행 계약과 인덱스 알고리즘은 변경하지 않았습니다. 설치 전 원본은 스킬 검색 경로 밖에 백업했고, 저장소의 `README.md`와 `GEMINI.md` 설명을 갱신했습니다. 원본 다운로드 파일은 보존했습니다.

원시 검사 로그는 [v3.0-local-static.txt](tests/evidence/v3.0-local-static.txt)에, 입력과 출력이 포함된 독립 계획 생성 표본은 [v3.0-local-forward-samples.json](tests/evidence/v3.0-local-forward-samples.json)에 기록합니다. 행동 정의 64개 전체를 실행한 결과와는 별개입니다. 장기 연구 실행·중단 후 재개·실제 성능 개선·호스트의 자동 스킬 선택이나 자동 재시작은 이번 검토에서 검증하지 않았습니다.

## 첨부 배포본의 검증 기록

검증일: 2026-09-07. 검증 환경: Linux, Python 3.13.5. 외부 Python 패키지·모델 API·유료 실행을 사용하지 않은 로컬 코드 및 문서 검사입니다. 지원 문법은 Python 3.10 이상이나 다른 Python 버전의 실행 검증은 수행하지 않았습니다.

## 검사 결과

3.0.0 전체 검사는 **56개 모두 통과**했습니다. 원시 로그는 [v3.0-unittest.txt](tests/evidence/v3.0-unittest.txt)에 있습니다. 최종 아카이브 재추출·파일 해시는 함께 제공하는 배포 검증 보고서에서도 확인합니다.

| 검사 | 범위 | 판정 |
|---|---|---|
| 깨끗한 2.4.0 기준선 | macOS 부속 파일만 제외한 원본, 31개 메서드 | 통과 |
| 3.0.0 전체 unittest | 56개 메서드, 코드·CLI·정적 계약 | 56개 통과, 32.403초 |
| 계약 조합 | 7개 프로파일 × 계획/직접 프롬프트 템플릿 2개 | 전체 unittest에 포함 |
| 한글 인덱스 | 13개 메서드, 충돌·경고·read-only fallback 포함 | 전체 unittest에 포함 |
| 연구 계약 | 12개 정적 메서드, 의미적 모델 검증 아님 | 전체 unittest에 포함 |
| 공식 모델 가이드 대조 | 실제 읽은 가이드와 본문·참조·템플릿 대조, 발견한 충돌 수정 | MODEL_GUIDE_REVIEW.md 참조 |
| 최종 ZIP | 재추출 후 동일 테스트, 전체 파일 manifest 해시와 여분 파일 확인 | 별도 배포 검증 보고서 참조 |

## 검사 중 수정한 사항

첫 전체 검사에서는 기존 테스트가 generator `1.0.1`을 기대하여 1건 실패했습니다. 실제 배포 버전 `1.1.0`을 기대하도록 수정하고, 이전 `1.0.0`과 `1.0.1` 카탈로그 모두 재생성 전 stale fallback이 되는지 확인했습니다. 테스트를 삭제하거나 충돌·권한 검사를 완화하지 않았습니다. [초기 실패 로그](tests/evidence/v3.0-unittest-initial-failure.txt)와 [원본 기준선 로그](tests/evidence/baseline-clean-unittest.txt)를 보존했습니다.

## 재현

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
sha256sum -c MANIFEST.sha256
```

두 번째 명령은 `sha256sum`이 있는 환경의 예입니다. manifest는 자신을 제외한 배포 파일을 열거합니다. 표준 SHA-256 도구로 교차 확인할 수 있습니다. 파일을 편집하거나 캐시를 만든 뒤에는 원본 배포 파일 해시와 달라질 수 있습니다.

## 미실행 범위

행동 평가 정의 64개는 모두 `not_run`입니다. 새 모델 세션의 목표 선택·실제 장기 연구·자동 위임·성능 개선률·모델 간 비교·Codex/Claude Code 설치 연동·스케줄링·자동 재시작은 실행하지 않았습니다. 코드 테스트와 정적 문구 검사를 통과했다는 것만으로 이러한 행동이나 효과가 검증되었다고 보지 않습니다.

첨부본의 과거 검증 기록은 [VALIDATION_HISTORY.md](VALIDATION_HISTORY.md)에 보존했습니다. 이전 모델 표본의 기록은 제공받은 역사 자료이며 이번 버전의 새로운 실행 결과에 포함하지 않습니다.

실제 배포 재검사의 원시 로그와 ZIP SHA-256은 함께 제공하는 검증 자료에 포함됩니다. 모델 가이드 검토는 [MODEL_GUIDE_REVIEW.md](MODEL_GUIDE_REVIEW.md), 테스트 구분은 [tests/README.md](tests/README.md)를 참조합니다.
