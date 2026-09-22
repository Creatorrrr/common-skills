# GPT-6 Astra guide review — goal-planner 3.2.1

검토일: 2026-09-22. 지정 모델: `gpt-6-astra`.

## 로컬 재확인

2026-09-22 로컬 통합에서는 공식 문서 MCP의 검색 후 페이지 가져오기로 [Astra 가이드](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra)의 실제 Markdown 본문과 [모델 명세](https://developers.openai.com/api/docs/models/gpt-6-astra)를 확인했습니다. 다섯 행동 조정 영역과 선택형 API 호환성 안내가 해당 문서와 일치합니다. 이번에는 가이드 본문 조회가 성공했으며, 아래 첨부 원본의 검색 색인 기반 확인 한계와 구분합니다. API 호출기·모델 설정은 변경하지 않았습니다. 실제 검증 범위는 [VALIDATION.md](VALIDATION.md)를 따릅니다.

## 이전 버전 정정

3.2.0의 실제 검토 파일에는 “Using GPT-5.6”을 읽었다고 기록되어 있었다. 원문을 [MODEL_GUIDE_REVIEW_V3_2.md](MODEL_GUIDE_REVIEW_V3_2.md)에 그대로 보존했다. 공통 설계 원칙이 일부 겹쳐도 이를 Astra 전용 검토로 소급하지 않는다. 이번 배포는 공식 문서의 **Using GPT-6 Astra** 절을 확인하고 현재 동작 지침을 대조한 수정이다.

## 출처 확인과 접근 한계

요청 URL: https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra

공식 모델 페이지: https://developers.openai.com/api/docs/models/gpt-6-astra

쿼리 URL 직접 열기는 이 환경에서 Cache miss였고, 매개변수 없는 URL의 직접 열기는 지난달 GPT-5.6 캐시를 반환했다. 이를 Astra 문서라고 간주하지 않았다. 같은 공식 URL의 최신 검색 색인 본문에서 “Using GPT-6 Astra”, 다섯 가지 prompting 하위 절, migration 항목을 확인했고, 공식 Astra 모델 페이지의 ID·추론 수준을 교차 확인했다. 전체 원문 HTTP 다운로드나 쿼리 URL의 성공적인 직접 로딩을 주장하지 않는다. [확인 메타데이터](tests/evidence/v3.2.1/source-verification.json)에 이 차이를 기록했다.

## 이번 변경의 근거와 범위

공식 Astra 안내는 불필요한 질문·중단, skill 지침에 대한 민감성, 장황한 표현, 위임 빈도, 작은 변경의 과도한 테스트를 조정할 대상으로 든다. 기존의 사용자 지시 우선·권한·증거 원칙은 유지하고 아래 부족한 부분을 보완했다.

| 보완 | 실제 적용 위치 |
|---|---|
| 자연어 행동 요청과 단순 검토 구분; 일상적인 빈칸으로 멈추지 않음 | SKILL.md, Core, runtime-prompts |
| 중단뿐 아니라 요청에서 이탈할 때도 실제 skill과 짧은 해당 문장을 설명 | SKILL.md, Core |
| 유효한 독립 구현·검증도 기존 권한·역할 안에서 분담 | SKILL.md, Core; Research 소유권 표현 정리 |
| 저영향 수정의 자기복제 테스트를 피하고 필요한 검사 통과 후 마무리 | SKILL.md, Core |
| 결과 중심 문장·정상 띄어쓰기; 완료 작업을 보존하는 요구 변경 처리 | SKILL.md, Core, runtime-prompts |
| Astra API 조건은 일반 실행 계약에 섞지 않음 | references/gpt-6-astra.md |

새로운 여덟 번째 계약이나 실행 엔진은 만들지 않았다. 기존 7개 블록, 실험·평가 절차, 보고서 자격, 읽기 전용 도구를 유지했다. Core가 변경되어 기존에 만든 독립형 계획에는 새 설치만으로 자동 반영되지 않는다.

## 확인 수준

로컬 검사는 계약 전달·선택·회귀를 확인한다. 실제 Astra를 호출한 전후 A/B는 `not_run`이며 총 토큰·비용·지연 및 성공률은 `not_measured`이다. 모델별 설정을 사용자 대신 변경하지 않았고 SDK/API 기능도 구현하지 않았다. 최종 검사 결과는 [VALIDATION.md](VALIDATION.md), 사용·변경 안내는 [ASTRA_UPDATE_KO.md](ASTRA_UPDATE_KO.md)에 기록한다.
