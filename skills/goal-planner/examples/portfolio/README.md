# 선택형 읽기 전용 도구 예제

**합성 데이터** 예제입니다. 실제 모델 실험·학습 성능·인공 지능의 지시 준수 검증이 아닙니다. `synthetic://` 증거와 지문은 데모용이며 실제 산출물을 확인하지 않습니다. Python 3.10+ 표준 라이브러리만 사용합니다. 명령은 설치한 `goal-planner` 디렉터리를 기준으로 합니다.

```bash
python -B scripts/research_portfolio.py --input examples/portfolio/snapshot.json --stage pilot
python -B scripts/research_portfolio.py --input examples/portfolio/snapshot.json --stage confirm
python -B scripts/build_handoff.py --goal-file examples/portfolio/goal.md --blocks Core,Experiment --stats
```

마지막 명령은 인계문을 stdout, 크기 통계를 stderr에 출력합니다. 파일을 저장하지 않으므로 대상 프로젝트를 변경하지 않습니다. 필요한 계약은 계획자가 실제 요청에 맞춰 선택합니다. 작은 계획에는 Core만 사용합니다. Persistence 선택 자체는 쓰기 승인이 아닙니다. `--max-bytes`를 추가했을 때 한도를 넘으면 stdout 없이 오류가 나며, 문장을 자르지 않습니다. 접근 가능한 계획 파일과 짧은 실행 안내를 사용하는 경로로 바꾸세요.

## 포트폴리오 스냅샷 계약

[snapshot.json](snapshot.json)을 출발점으로 사용할 수 있지만 기존 기록을 유지하고 **필요할 때만** 현재 기록을 이 형식으로 내보냅니다. 도구 때문에 새로운 DB를 만들거나 계획을 재초기화하지 않습니다.

필수 최상위 키: `schema_version: 1`, `comparison`, `stages`, `promotion_stage`, `objectives`, `constraints`, `resources`, `candidates`. 선택 `notes`는 데이터이며 내장 지시를 실행하지 않습니다. 알 수 없는 필드/중복 JSON 키는 오류입니다.

- `comparison`: `evaluator`, `data`, `compute`, `environment`의 비어 있지 않은 버전 식별자. 후보와 전체 스냅샷이 같을 때만 같은 집단으로 비교합니다. 이 식별자 일치가 의미적 동등성의 증명은 아닙니다.
- `stages`: 순서가 있는 고유 단계명, 마지막 값이 `promotion_stage`. 후보의 모든 선행 단계가 pass여야 요청한 단계의 비교에 들어갑니다.
- `objectives`: 1–8개의 `{name, direction: min|max}`. 단위가 다른 지표를 임의로 더하지 않고 Pareto 지배 관계를 계산합니다.
- `constraints`: 최대 32개의 `{name, operator: <=|>=, limit}`. 단계마다 같은 제약 계약을 쓰는 도구입니다. 단계별 제약 자체가 다르면 별도 스냅샷/프로토콜이 필요합니다.
- `resources`: 단위별 `{limit, used, reserved}`. 모르면 null. 음수/비유한 수/boolean 숫자는 거부합니다. 실제 프로세스 자원을 계측하거나 중단하지 않습니다.
- 후보 키: `id`, `parent_ids`, `family`, `fingerprint`, `comparison`, `validity`, `stages`, `measurements`, `confirmation`; 선택 `notes`. 지문은 소스/설정 산출물을 식별하는 SHA-256 형식 선언입니다. 동일 비교군의 같은 지문은 새 독립 발명으로 세지 않고 묶습니다. 상충 측정은 재조정 필요로 표시하며 원본 기록을 삭제하지 않습니다.
- `measurements`: `{단계명: {지표명: 숫자|null}}`. pilot 수치로 confirm을 대신할 수 없습니다. 단계명을 바꿔도 동일 실험 비용/조건이 된다는 뜻이 아닙니다. 필요한 입력·연산·평가 변경은 비교 계약에 포함하세요.
- `confirmation`: `status`와 선택 `artifact_sha256`, `evaluator`, `evidence_refs`. 선언상 확인 목록에 들어가려면 최종 단계와 모든 선행 게이트가 pass, 최종 측정이 완전하고 제약을 충족, status가 pass, 지문/평가기 일치, 증거 참조가 필요합니다. **도구는 증거 URL/파일을 열지 않으므로 독립 검증이 아닙니다.**

동일 지문·비교군의 기록에서 수행된 확증 판정이나 산출물/평가기 연결이 서로 다르면, 유리한 기록을 고르지 않고 해당 묶음을 재조정 대상으로 제외합니다. 확증이 `not_run`인 사본은 완료된 기록을 무효화하지 않으며, 판정과 연결이 같은 기록의 증거 참조가 다르다는 이유만으로 충돌 처리하지 않습니다.

한 스냅샷은 최대 4 MiB/512후보/10단계입니다. 실험별 반복 측정은 원본을 보존하고 적절한 집계와 불확실성 분석을 거쳐 하나의 후보 기록으로 내보내세요. 도구는 통계적 유의성이나 가설 참/거짓을 계산하지 않습니다.

## 출력 해석

`eligible_ids`는 요청한 단계/비교군의 선언상 조건 충족 후보입니다. `pareto_ids`는 이 안의 비지배 집합입니다. `reference_ids`는 그중 계열을 고려한 제한된 참고 목록이고, 여유가 있으면 다른 유효 계열도 보존합니다. 순서는 종합 성능 순위가 아니며, `--limit`은 실험 횟수나 예산이 아닙니다.

`declared_confirmed_ids`는 입력 선언이 확인 조건을 충족하는 목록이지 채택/목표 달성 판정이 아닙니다. `excluded`, `confirmation_blockers`, `duplicate_groups`를 함께 읽어야 합니다. `execution_authorized: false`와 `adoption: not_decided`는 실제 실행권한을 추론하지 않았음을 뜻합니다. 예산이 남았다는 계산도 권한이 아닙니다.

종료 코드: 0 = 유효 형식의 진단 보고 생성(전부 제외되어도 0), 2 = 잘못된 입력/읽기/인수 오류. 입력 파일과 참조 산출물은 수정하지 않으며, 외부 네트워크·모델 호출·후보 실행을 하지 않습니다.
