# goal-planner 3.2.0 검증 기록

검증일 2026-09-22. 원본 3.1.0을 기준선으로 보존했다. 이 기록은 실제 로컬 유닛/계약/CLI 검사 결과이며 LLM 행동 평가 또는 자동 연구 성능 검증이 아니다.

## 실행 결과

```text
원본: Ran 99 tests in 57.828s — OK
개선: Ran 166 tests in 74.837s — OK
구성: 기존 99 + portfolio 42 + handoff 17 + evolution contracts 8
```

최초 개선본 전체 스위트 호출은 실행 도구 시간 제한 때문에 중단됐다. 변경 없는 동일 스위트를 240초 상한으로 재실행해 완료했다. 개별 테스트 실패를 성공으로 바꾸거나 원래 기준을 낮추지 않았다.

실제 로그: [원본](tests/evidence/v3.2.0/baseline-3.1-tests.txt), [3.2 전체](tests/evidence/v3.2.0/release-3.2-tests.txt).
호환성: [기록](tests/evidence/v3.2.0/compatibility.json) — Core, report_index.py, experiment_preflight.py는 원본과 동일. 기존 테스트는 버전 기대값만 3.2.0으로 갱신했다.

## 추가 검사 범위

잘못된/비유한/boolean 숫자, 중복 키/식별자, 계보 순환, 코호트 불일치, 선행 게이트 실패, 지표 누락, 제약 실패, 단계별 수치 혼용, 상충 중복, 확증 지문/평가기/근거 누락, 자원 예약/미확인, 입력 무변경을 확인했다. 인계문은 7개 정규 블록, 선택별 1회 포함, Core 필요, 중복/미해결 표식 거부, cap 초과 무출력, 정확한 Unicode 크기를 확인했다.

실제 합성 CLI 출력: [pilot](tests/evidence/v3.2.0/portfolio-pilot.json), [confirm](tests/evidence/v3.2.0/portfolio-confirm.json).
인계 크기: [통계](tests/evidence/v3.2.0/handoff-sizes.json). 같은 합성 목표에 Core 5,318 bytes, Core+Experiment 12,207 bytes, 6블록 연구 프로필 27,008 bytes. 이는 서로 다른 프로필 간 길이이며 이전 버전 대비 모델 토큰/비용 절약 실험이 아니다.

## 미검증 항목

실제 LLM의 계획 품질/권한 준수, 연구 성공률, 총 token·cost·latency, 라이브 외부 통합과 다운스트림 프로젝트 성능은 검증하지 않았다. 기존 행동 사례 80개와 [신규 16개](tests/behavioral-evolution.json)는 정의만 있으며 모두 not_run이다. [실제 행동 평가 프로토콜](tests/EVOLUTION_EVAL.md)을 제공한다. 코드/정적 검사 통과를 행동 평가로 바꾸지 않는다.

보조 도구가 출력하는 declared_confirmed는 증거 파일을 검증한 것이 아니며, 가족 라벨은 신규성 증명이 아니고, helper는 UCB1/MAP-Elites 엔진이 아니다. 새 실행/쓰기/비용 권한을 생성하지 않는다.

## 재검사

```bash
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -v
```

과거 원본 검증은 [VALIDATION_V3_1.md](VALIDATION_V3_1.md)에 보존했다. 최종 파일 목록과 해시는 MANIFEST.sha256을 사용한다.
