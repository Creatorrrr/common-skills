# Optional preflight: a working cache/no-cache example

이 예시는 성능 연구가 아니라 **문서의 비교군과 실제 생성된 동작이 일치하는지 검사**하는 작동 예제입니다. 특정 모델·데이터셋·프로젝트에 의존하지 않습니다. 실제 코드의 factory를 호출하고 put/get/reset 동작을 확인합니다. 모든 비밀·사용자 데이터 없이 동작합니다.

패키지 루트 `goal-planner/`에서 아래처럼 실행합니다. Python 3.10 이상이 필요하며 외부 패키지는 없습니다. `mktemp` 예시는 macOS/Linux 셸 기준입니다. 임시 출력은 스킬 폴더 밖에 둡니다.

```bash
TMP_DIR="$(mktemp -d)"
python3 -B examples/preflight/demo_runtime.py > "$TMP_DIR/observed.json"
python3 -B scripts/experiment_preflight.py \
  --spec examples/preflight/spec.json \
  --observed "$TMP_DIR/observed.json" \
  --root examples/preflight
```

결과는 `status: consistent`, 종료 코드 0입니다. 다음은 baseline을 잘못 생성하는 결함을 의도적으로 주입합니다.

```bash
python3 -B examples/preflight/demo_runtime.py --fault > "$TMP_DIR/fault.json"
python3 -B scripts/experiment_preflight.py \
  --spec examples/preflight/spec.json \
  --observed "$TMP_DIR/fault.json" \
  --root examples/preflight
```

이 호출은 **의도적으로 종료 코드 1**을 반환합니다. 두 비교군이 모두 캐시를 사용하여 실제 차이가 없어졌다는 `DECLARATION_MISMATCH`와 `CONTRAST_MISMATCH`가 표시됩니다. 이는 점검 도구가 정상적으로 결함을 발견한 것이며 패키지 테스트 실패가 아닙니다. `set -e`를 사용하는 셸이나 CI에서는 이 예제의 예상 코드 1을 명시적으로 처리해야 합니다.

## 프로젝트에 적용

[spec.json](spec.json)을 기존 실험 설정의 표현에 맞게 작성합니다. `arms`의 각 항목은 실제 비교에 중요한 **동일한 사실 키 집합**을 선언합니다. `contrasts`는 후보·비교군과 실제 달라져야 하는 키를 명시합니다. 이름이 아니라 실제 설정/동작으로 관측 파일을 생성하도록 프로젝트의 기존 실행기에 작은 exporter를 연결합니다. 예시 [demo_runtime.py](demo_runtime.py)의 결과를 프로젝트의 결과로 재사용해서는 안 됩니다.

관측 파일에는 동일한 `experiment_id`, 실제 `run_id`, `capture_method`, `arms`, `evidence`가 필요합니다. `runtime-probe`와 `runtime-export`는 exporter의 자기신고이며 도구가 실행 과정을 인증하지는 않습니다. `evidence`는 `--root` 아래의 정규화된 상대 경로와 SHA-256입니다. 관련 실행 소스·설정·평가기 또는 그 식별자를 포함한 작은 증거 manifest를 사용합니다. JSON은 파일당 2 MiB, 증거 해시 대상은 파일당 64 MiB 이하이며 큰 체크포인트 전체를 읽는 도구가 아닙니다. 명시적으로 나열한 증거 파일만 읽습니다.

| 종료 코드 | 의미 |
|---|---|
| 0 | 제공된 사실·대조·해시의 기계적 정합성 통과 |
| 1 | 선언/실제/대조/증거 파일에 불일치 또는 누락 |
| 2 | 잘못된 입력·스키마·경로·크기 또는 읽기 오류 |

`scientific_validity`와 `source_coverage_and_exporter_truth`는 항상 `not_established`입니다. 이 도구는 누락된 혼란변수·거짓 exporter·실행 경로 전체·평가 누출을 자동 발견하지 못합니다. 해시가 같아도 인과적 결론이나 실행 권한을 증명하지 않습니다. 실제 코드·동작 검토를 대신하지 않으며, 모든 작업에 이 파일 형식을 강제하지 않습니다.

CI에서 사용하려면 현재 프로젝트의 승인된 실행기에 **코드 0 이후만 비용 큰 실행을 허용하는 분기**를 직접 연결해야 합니다. 스킬이나 이 도구를 설치하는 것만으로 자동 게이트·권한 격리·스케줄링이 생기지는 않습니다.
