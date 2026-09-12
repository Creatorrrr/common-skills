# GPT Pro Codebase Analysis v2.0.0

코드베이스 분석용 기존 스킬을 개선한 교체 패키지입니다. `SKILL.md`의 이름은 `gpt-pro-codebase-analysis`로 유지했고, Responses API와 ChatGPT Web 수동 전달 경로를 모두 유지했습니다.

핵심 변경은 **검토한 입력 범위와 실제 전송 내용을 일치시키고, 생성 완료와 분석 검증 완료를 구분하는 것**입니다. 2026-09-12 공식 문서 확인 기준으로 기본 모델은 `gpt-6-astra`, 추론 강도는 API가 지원하는 최댓값 `max`입니다. 이 설정 변경 자체가 분석 품질 향상을 입증하지는 않습니다.

## 적용 방법

이 저장소에서는 `skills/gpt-pro-codebase-analysis`가 v2.0.0의 원본입니다. 저장소에 연결된 스킬 설치는 이 폴더의 변경을 그대로 사용합니다. 별도 설치를 업데이트할 때는 기존 폴더를 백업한 뒤 교체하고, 도구에서 새 `SKILL.md`가 인식되는지 확인합니다.

기존 v1 `manifest.json`은 사용하지 않습니다. 아래 준비 도구로 v2 스냅샷을 다시 만듭니다. 기존 API/Web 실행 결과는 비교용으로 보존하되 새 입력 검증을 우회하는 데 사용하지 않습니다.

에이전트에 전달할 요청 예:

> `$gpt-pro-codebase-analysis`로 이 저장소의 결제 처리 흐름과 오류 경로를 분석해줘. 전체 허용 텍스트 범위를 유지하고 코드 수정은 하지 마. 보고서는 한국어로 작성해줘. 외부 실행 경로는 Responses API를 사용하고, 실제 전송 대상과 보관 조건을 확인한 뒤 진행해줘.

이는 사용 예이며 실제 사용자 승인 기록을 대신하지 않습니다. 기존 대화에서 실행 경로·범위·조건이 이미 명확하면 다시 질문하지 않도록 설계되어 있습니다.

## 로컬에서 먼저 확인하기

Python 3.10 이상과 Git을 사용합니다. 준비·수동 Web 패키징·dry-run·단위 테스트에는 외부 Python 패키지나 API 키가 필요하지 않습니다. 실제 API 실행에는 지원 API를 제공하는 공식 `openai` SDK와 호스트에 안전하게 설정한 `OPENAI_API_KEY`가 필요합니다. SDK의 실제 서비스 연동 검증은 별도입니다.

```bash
SKILL_DIR="/absolute/path/to/gpt-pro-codebase-analysis"
REPO_DIR="/absolute/path/to/your-repository"

python -m unittest discover -s "$SKILL_DIR/tests" -v

# 사용자 목표와 실제 경로로 examples/request-contract.json을 수정한 사본을 먼저 준비합니다.
python "$SKILL_DIR/scripts/prepare_analysis_context.py" \
  --root "$REPO_DIR" \
  --out-dir "$REPO_DIR/.codex-analysis/context" \
  --contract "$REPO_DIR/.codex-analysis/request-contract.json" \
  --mode full

# 실제 전송하지 않는 로컬 검증입니다. 정확한 API 토큰 계산도 이 단계에서는 하지 않습니다.
python "$SKILL_DIR/scripts/run_gpt_pro_analysis.py" \
  --manifest "$REPO_DIR/.codex-analysis/context/manifest.json" \
  --dry-run
```

실제 API 실행은 [API 실행 안내](references/responses-api.md), 수동/승인된 자동화 전달은 [Web 안내](references/chatgpt-web-handoff.md)를 따릅니다. 승인 기록에는 예시 문구가 아니라 실제 사용자의 지시와 범위 검토 결과를 사용해야 합니다.

## 달라진 기본 동작

| 항목 | v2 동작 |
|---|---|
| 모델 | `gpt-6-astra` 기본, `gpt-5.6-sol` 명시 선택 지원 |
| 추론 모드 | `auto`; Sol은 Pro로 해석하고 Astra에는 mode 필드를 보내지 않음 |
| 추론 강도 | `max` (공식 API 지원 최댓값) |
| 응답 길이 | verbosity `medium`; 사용자 언어·형식·깊이를 계약으로 전달 |
| 실행 | foreground, `store=false` 기본 |
| 새 Files/Vector Stores | 기본 정리 + 1일 만료 보조장치, 명시 승인 시 보관 가능 |
| `--scope` | 부분 문자열 힌트가 아니라 실제 포함 가능한 파일/디렉터리 경계 |
| `full` | 준비 단계의 전체 포함 목록 유지, 오류·크기 초과 시 자동 축소하지 않음 |
| 외부 전송 | 스냅샷·선택 범위·사용자 계약·실행 조건과 일치하는 승인 기록 필요 |
| 실행 성공 | 응답 완료와 입력 검증을 의미; 분석 내용 검증·로컬 확인은 별도 pending |

`full`은 비밀 파일·Git 무시 파일·바이너리까지 무조건 업로드한다는 뜻이 아닙니다. 검토한 포함/제외 정책을 적용한 텍스트 집합을 손실 없이 유지한다는 뜻입니다. 민감정보 필터는 휴리스틱이며 전송 전 사람 또는 권한 있는 에이전트의 검토가 필요합니다.

## 주요 파일

| 파일 | 용도 |
|---|---|
| `SKILL.md` | 에이전트의 판단·승인·분석·검증 흐름 |
| `scripts/prepare_analysis_context.py` | 한글 경로 처리, 범위/민감정보 검사, 스냅샷과 해시 생성 |
| `scripts/context_integrity.py` | 스냅샷·선택 집합·승인 일치 검증 |
| `scripts/analysis_contract.py` | API와 Web이 공유하는 분석 요청 계약 |
| `scripts/authorize_analysis.py` | 이미 얻은 실제 승인을 로컬 기록으로 저장 |
| `scripts/model_profiles.py` | 모델별 추론 옵션과 토큰 한도 검증 |
| `scripts/api_resources.py` | 검색 입력 정규화, 수집 확인, 재사용 검증, 소유 리소스 정리 |
| `scripts/run_attempt.py` | 실행 잠금, 이전 결과 보존, 현재 실패 상태 기록 |
| `scripts/run_gpt_pro_analysis.py` | 승인된 API 실행과 정확한 입력 토큰 검사 |
| `scripts/run_chatgpt_web_assisted.py` | 전송하지 않는 Web 패키지 생성 |
| `CHANGELOG.ko.md` | 상세 변경 사항과 이전 버전 대비 주의점 |
| `validation/VALIDATION.md` | 수행한 검증, 로그, 미검증 영역 |
| `evals/scenarios.jsonl` | 실제 모델 비교용 시나리오; 이번 제작에서 실행하지 않음 |

## 검증 범위와 한계

첨부 원본의 오프라인 테스트 80개를 재실행했습니다. 저장소 반영 과정에서 읽기 권한 오류를 바이너리로 잘못 분류해 전체 준비를 성공 처리하는 문제를 수정하고 회귀 테스트를 추가했습니다. Sol Pro 호환성 검사는 명시적인 모델 선택으로 유지합니다. 최종 실행 수와 로그는 [검증 기록](validation/VALIDATION.md)에 있습니다.

공식 OpenAI SDK 3.8.0과 HTTP 모의 전송 계층으로 요청 직렬화·파일 만료·수집·삭제·오류 시 정리를 추가 검증했습니다. 실제 OpenAI API 호출, 계정별 모델 접근, ChatGPT 업로드/브라우저 자동화, 모델 정확도·비용·속도 비교는 수행하지 않았습니다. 로컬 테스트 통과가 실제 서비스 연동이나 모델 품질 개선을 보장하지는 않습니다.

`store=false`는 모든 형태의 무보관을 뜻하지 않습니다. 삭제 응답도 공급자 전체 시스템의 즉시 영구 삭제를 입증하지 않습니다. 강제 종료·통신 중단으로 식별자를 받지 못한 리소스는 자동 정리가 불가능할 수 있어, 만료 정책과 로컬 저널을 보조 수단으로 사용합니다. 세부 근거는 [공식 자료 및 모델 설정](references/model-profiles.md)에 정리했습니다.
