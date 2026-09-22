# OpenAI model-guide review — goal-planner 3.2.0

검토일: 2026-09-22. 요청한 공식 원문: https://developers.openai.com/api/docs/guides/latest-model
현재 조회 내용의 절 제목은 “Using GPT-5.6”입니다. 페이지는 바뀔 수 있으므로 특정 모델명/매개변수를 스킬의 고정 실행 계약에 넣지 않았습니다. 이전 기록은 [MODEL_GUIDE_REVIEW_V3_0.md](MODEL_GUIDE_REVIEW_V3_0.md)에 보존했습니다.

## Applied changes

공식 가이드는 작동하는 설정을 기준으로 한 변경씩 평가하고, 중복 지침을 줄이며, 관련 도구만 노출하고, 명시적인 자율성/승인 경계를 두도록 권고합니다. 이를 선택형 상세 문서와 7개 정규 계약 블록의 단일 조립 경로로 반영했습니다. 일반 계획의 Core는 변경하지 않았고 실험/후보 탐색 규칙만 해당 블록에 넣었습니다.

가이드의 짧은 응답 지침은 근거/결정/주의점 누락과 구분했습니다. 인계문이 길면 활성 규칙을 잘라내지 않고 오류와 대안을 반환합니다. Python으로 확정 가능한 검사·집합 계산·조립은 결정적 도구로 처리하고, 평가 의미·가설·채택 결정은 에이전트의 판단과 실제 증거로 남겼습니다.

## Runtime configuration is separate

현재 승인된 상위/하위 모델과 설정을 보존한 상태에서 대표 과제로 기준선을 측정하고 하나의 설정만 바꿔 비교합니다. 더 높은 effort/pro 또는 여러 에이전트가 무조건 낫다고 가정하지 않습니다. SDK/API와 CLI의 지원 차이를 확인하며 스킬 문구만으로 runtime 설정이 바뀐다고 말하지 않습니다.

직접 API를 통합하는 별도 작업에서는 공식 문서의 Responses API, reasoning 유지/무효화, 완전한 응답 항목 전달, 관련 도구 집합을 검토할 수 있습니다. 이 배포는 API 클라이언트/키 생성/모델 호출을 추가하지 않습니다. 프로그래밍 가능한 도구 호출도 호스트가 실제 지원하고 결정적 일괄 처리가 유리한 때에만 고려합니다. 평가/승인처럼 중간 판단이 필요한 단계까지 무조건 묶지 않습니다.

## What was and was not measured

측정: 정규 블록 1회 포함, 선택되지 않은 계약의 비노출, Unicode byte/character 길이, cap 초과 무출력, JSON/상태 검사와 로컬 회귀 테스트. `build_handoff.py --stats`는 token_count를 `not_measured`로 명시합니다.

미측정: 실제 모델의 계획/실험 수행 성공률, 전후 총 토큰·비용·지연, 신규 연구 성과. 정적 테스트 통과를 모델 지시 준수나 성능 향상으로 표시하지 않습니다. [behavioral-evolution.json](tests/behavioral-evolution.json)의 실제 에이전트 A/B는 `not_run`입니다. 의미 있는 비교는 같은 과제·도구·권한·기준·예산을 사용하고, 요청 결과와 근거가 유지된 경우에만 절약을 개선으로 집계해야 합니다.
