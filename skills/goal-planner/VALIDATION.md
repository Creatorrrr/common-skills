# goal-planner 3.2.1 검증 기록

## 로컬 통합 검증 — 2026-09-22

첨부 ZIP과 현재 설치된 3.1.0, 연결된 개발 대화의 3.2.0/3.2.1 개선 의도를 대조했습니다. 아래는 macOS 27.0 arm64의 실제 로컬 결과이며, 뒤쪽의 첨부 배포 기록과 구분합니다.

| 확인 | 실제 결과 | 근거 |
|---|---|---|
| 첨부 ZIP | SHA-256 `0d9591ec1b6d24680bcc114fcdb29f3238984342d6a8a347b122fb9205ac6e09`; CRC·안전한 경로·manifest 110개 및 파일 집합 일치 | [정적 기록](tests/evidence/v3.2.1-local/static-checks.json), 원본 다운로드 보존 |
| 원본 재실행 | Python 3.14.3에서 171개 통과 | [원본 로그](tests/evidence/v3.2.1-local/upstream-unittest.txt) |
| 보완본 전체 검사 | Python 3.14.3에서 **176개 통과, 실패·건너뜀 0** | [전체 로그](tests/evidence/v3.2.1-local/unittest.txt) |
| 후보 도구의 다른 Python 확인 | Python 3.12.13에서 47개 통과 | [로그](tests/evidence/v3.2.1-local/python312-portfolio.txt); 전체 패키지의 다중 버전 검증은 아님 |
| 구조·정적 검사 | skill-creator quick_validate 통과, Ruff 0.16.4 통과 | [Ruff 로그](tests/evidence/v3.2.1-local/ruff.txt) |
| 실제 보조 CLI | pilot/confirm 후보 점검·선택 계약 조립은 코드 0; 작은 길이 한도는 부분 출력 없이 코드 2 | 정적 기록의 `cli_examples` |
| 기존 보완 보존 | 기존 인덱스·사전 점검 코드와 그 회귀 테스트, 기존 행동 정의는 바이트 동일; 3.1 검증 문서도 원문 보존 | 정적 기록의 보존 항목 |
| 공식 Astra 문서 | 실제 가이드 Markdown 및 모델 명세를 검색 후 가져와 대조 | [모델 가이드 재확인](MODEL_GUIDE_REVIEW.md); API 설정 변경·요청은 없음 |
| 별도 세션 표본 | 한정된 계획 파일 수정·읽기 전용 후보 탐색 인계 두 사례 통과 | [입력·출력·명령·변경·판정](tests/evidence/v3.2.1-local/forward-samples.json) |
| 설치 후 재확인 | 실제 설치 경로에서 계약 검사 36개 통과; 파일 해시·실행 권한·두 스킬 연결 확인 | [설치 후 로그](tests/evidence/v3.2.1-local/installed-contracts.txt), 정적 기록의 `installation` |

원본 후보 도구는 같은 지문·비교군의 확증 판정이 `pass`와 `fail`로 상충해도 충돌을 표시하지 않고 유리한 기록을 선언상 확증 목록에 포함했습니다. [수정 전 재현](tests/evidence/v3.2.1-local/original-bugs.json)을 보존했습니다. 수행된 확증 판정과 산출물/평가기 연결까지 대조해, 충돌 묶음은 재조정 전 참고·확증 목록에서 제외하도록 고쳤습니다. 확증 미수행 사본 및 판정·연결이 같고 증거 참조만 다른 기록은 정상 병합되는 대조 사례도 확인했습니다.

추가로 큰 정수나 유효하지 않은 Unicode 입력의 네이티브 예외가 traceback과 코드 1로 종료되지 않도록, 기존 CLI 계약인 오류 JSON과 코드 2로 처리했습니다. 회귀 5개를 추가했고 입력을 수정하지 않는지 확인했습니다. ZIP에서 사라진 shebang 파일 5개의 실행 권한을 복구하고 새 파일의 import·정규식 표기·테스트 정적 검사 지적을 정리했습니다. 기존 두 보조 도구의 구현과 실행 계약은 이 로컬 보완에서 변경하지 않았습니다.

부모 대화 이력을 복제하지 않은 `gpt-6-astra` 두 세션에 스킬과 최소 합성 자료만 제공했습니다. 첫 표본은 “고쳐줄 수 있나?”를 실제 행동 요청으로 처리해, 허용된 계획의 링크 한 곳만 고쳤습니다. 두 번째는 단계별 후보와 합성 선언·실제 채택을 구분하고, 예산 장부 불일치·미해결 메모리 개선을 보존했습니다. 선택한 다섯 계약을 한 번씩 포함한 인계문을 응답으로 작성했으며 실제 실험·외부 호출·파일 수정은 하지 않았습니다. 두 사례의 도구 기록과 전후 파일 해시를 검토했고 정의 파일은 바꾸지 않았습니다.

도구의 코드 0은 입력 기록의 분석/조립 성공이며 실제 연구 결과·채택·실행 권한의 증명이 아닙니다. 두 custom 표본을 전체 108개 행동 정의의 실행이나 3.1 대비 A/B로 세지 않습니다. 장기 자율 연구 성과, 비용·토큰·지연 개선, API/SDK 통합, 일반 호스트의 자동 탐색·재시작은 이번 검증으로 주장하지 않습니다. 같은 모델 계열의 별도 세션을 통계적으로 독립적인 검증이라고 표현하지 않습니다.

기존 3.1.0은 스킬 검색 경로 밖인 `/Users/chasoik/.codex/backups/goal-planner/2026-09-22T184029+0900/goal-planner`에 전체 백업했습니다. 기존 폴더의 Finder `.DS_Store`도 백업에 보존하며 새 패키지에는 포함하지 않습니다. 현재 모델 설정·다른 프로젝트의 계획·실험·예산·기록은 이 스킬 업데이트의 변경 대상이 아닙니다. 이전 계획에 복사된 계약은 설치만으로 갱신되지 않습니다.

검토·보완한 3.2.1을 `/Users/chasoik/Projects/common-skills/skills/goal-planner`에 반영했습니다. `~/.agents/skills/common-skills/goal-planner`와 `~/.claude/skills/goal-planner`가 모두 이 설치 경로와 버전 3.2.1을 가리키는지 확인했습니다. 저장소의 README와 GEMINI 안내 버전도 맞췄습니다. 기존처럼 목표 작성과 진행을 함께 요청할 수 있으며, 적용 가능한 실행 권한·도구·자원 범위에서 계획 작성 후 진행합니다.

---

## 첨부 배포본의 검증 기록 — 아래 원문 보존

검증일: 2026-09-22. 이전 배포 검증은 [VALIDATION_V3_2.md](VALIDATION_V3_2.md)에 원문 보존했다.

## 실제 실행

```text
python -B -m unittest discover -s tests -v
Ran 171 tests in 44.075s
OK
```

[전체 로그](tests/evidence/v3.2.1/unittest.txt). 기존 166개와 새 인계/패키지 회귀 5개가 포함된다. 원래 테스트의 의미는 바꾸지 않았으며 기존 파일의 변경은 VERSION 기대값 3.2.0 → 3.2.1 한 곳이다. 새 테스트는 모델이 실제로 지침을 따르는지 평가하는 검사가 아니다.

변경 전 기준선 실행을 먼저 시도했으나 호출 도구의 20초 상한으로 중단되었다. [중단 로그](tests/evidence/v3.2.1/baseline-attempt-interrupted.txt)를 보존했다. 이를 통과로 집계하지 않는다. 이후 수정된 패키지의 전체 스위트를 실제로 완료했다. 과거 배포의 로그와 이번 실행 기록을 혼합하지 않는다.

## 실제 인계 출력과 호환성

[Core 출력](tests/evidence/v3.2.1/handoff-core.md) · [Core 통계](tests/evidence/v3.2.1/handoff-core-stats.json) · [연구 출력](tests/evidence/v3.2.1/handoff-research.md) · [연구 통계](tests/evidence/v3.2.1/handoff-research-stats.json)

동일 예제에서 Core 인계는 6,845 bytes / 2,888 characters, 6블록 연구 인계는 28,607 bytes / 12,090 characters다. 이전 동일 예제 Core는 5,318 bytes였으므로 문구 보완으로 길이가 증가했다. 이것을 토큰 절약으로 표시하지 않는다. compiler의 token_count는 not_measured다.

[호환성 기록](tests/evidence/v3.2.1/compatibility.json): 기존 4개 scripts 구현은 원본과 바이트 단위로 동일하다. 7개 블록 중 Core와 Research만 변경했고 나머지 5개는 그대로다. 이전 모델 검토 문서는 원문 그대로 보존했다. 선택되지 않은 계약·API 문서가 자동으로 인계되지 않으며, 필수 조건을 길이 상한에 맞춰 잘라내지 않는다.

## 미실행/미측정

[behavioral-astra.json](tests/behavioral-astra.json)의 12개 사례는 실제 호스트 A/B를 위한 정의이며 모두 not_run이다. 이전 행동 사례도 실행 결과로 바꾸지 않았다. 실제 Astra 요청, 다운스트림 연구, SDK/API 통합, Windows/다른 Python 버전 검증은 이번에 수행하지 않았다. LLM 성공률·총 토큰·비용·지연은 not_measured다.

이번 배포는 스킬/인계 지침 수정이다. 모델 선택, effort, 역할 배분, 실행 중 프로젝트의 상태나 사용자 설치를 바꾸지 않았다. ZIP의 구조·SHA-256·압축 무결성과 추출본 CLI를 별도로 점검한다.
