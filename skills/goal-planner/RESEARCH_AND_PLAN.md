# 연구 근거 → 개선 계획 → 구현

검토일: 2026-09-22. 이 문서는 스킬 변경의 근거와 한계를 기록하며 매 작업에서 읽는 지시문이 아닙니다.

| 근거 | 관찰/한계 | 반영 |
|---|---|---|
| ASI-Evolve 논문 §2, §5.3 | 문헌 지식과 실험 분석을 구분; 원 배치 과제에서 제거 실험 | 조건부 교훈·반대 설명·근거 연결, 전체 과제로 일반화하지 않음 |
| ASI-Evolve 샘플링 비교 | UCB1과 다양성 방식의 효과가 조건에 따라 다름 | 단일 알고리즘 강제 대신 task-specific 선택; helper는 단순 Pareto/계열 참고 |
| ASI-Forge bootstrapper.py | 영역 이해→지식→제약→프롬프트→실험 환경→검증 자동화 | 목적/인터페이스/평가/권한의 영역 계약; 자동 생성 평가기에 독립 대조 필요 |
| AlphaEvolve 논문 §2 | 코드 변이, 다목적 평가, 단계별 저비용 검사, 비동기 실행, 다양성 | 평가 cascade, 비교군/단계 분리, 격리와 자원 예약, 최선 후보 별도 보존 |
| Klarna Engineering 현장 보고 | 늦은 결정성 제약·규모 전환·장기 정체·모델별 유효 코드율 | 사전 제약·규모별 재비교·정체 판단·모델 변경 전 실측 비교 |
| OpenAI latest-model | 중복 지침 감소, 작업별 도구, 승인 경계, 같은 평가로 최적화 | Core 그대로, 필요한 블록만 1회 조립, 크기 통계와 잘림 거부 |

## 원본 감사

첨부본은 이미 3.1.0이며 가설 사전등록, 반대 설명, 비교 사전점검, 네 종류 판정, 공유 예산/예약, best/active 분리, 기존 상태 재개와 권한 경계를 갖췄습니다. 이를 새로 구현한 것으로 보고하지 않습니다. 원본 99개 테스트를 실제 실행해 기준선으로 보존했습니다.

보완 대상은 영역/평가기 설정 단계의 독립 확인, 비용 cascade와 **단계별 수치 분리**, 의미 있는 계열 참고, 재사용 가능한 조건부 교훈, 정체의 사전 의사결정, 인계문 결정적 조립입니다. 전체 프레임워크를 통째로 이식하거나 추가 에이전트를 필수화하지 않았습니다.

## 실제 변경

`references/evolution-design.md`: 필요한 때만 읽는 연구 탐색 설계.
`references/execution-contract.md`: 기존 Experiment/Direction/Program 안에 실행에 필요한 핵심을 추가; Core 및 7개 이름 유지.
`assets/search-plan-template.md`: 기존 계획을 보완하는 선택형 표.
`scripts/research_portfolio.py`: 형식·단계·비교군·제약·중복·Pareto·선언상 확인·자원 잔액의 읽기 전용 계산.
`scripts/build_handoff.py`: 정확한 7개 정규 계약 파서, 선택 조립, 무음 잘림 방지.
`tests/behavioral-evolution.json`: 실제 모델 A/B용 사례 정의; not_run 유지.

직접 개발한 보조 도구는 진화 탐색 엔진 자체를 구현하지 않습니다. 모델 호출, 안전 샌드박스, 실제 스케줄러, UCB1/MAP-Elites 알고리즘, 실제 증거 파일 검증 또는 연구의 인과 분석은 제공하지 않습니다. 이러한 기능은 기존 승인된 실행 환경을 사용합니다.

## 구현 중 재검토

초기 helper 설계는 후보당 하나의 metrics 묶음을 사용했습니다. 코드 검토에서 pilot과 confirm의 수치 출처가 섞일 수 있음을 확인하고, 출시에 앞서 `measurements[stage]`로 바꿨습니다. 단계별 순위가 다르게 나오는 테스트와 pilot을 confirm으로 재사용할 수 없다는 테스트를 추가했습니다. 원래 계획의 '같은 비교 조건' 기준을 완화하지 않은 수정입니다.

## 자료

- ASI-Evolve: https://arxiv.org/abs/2603.29640 ; https://github.com/GAIR-NLP/ASI-Evolve
- ASI-Forge: https://github.com/photodoc1960/ASI-Forge ; `pipeline/specialization/bootstrapper.py`
- AlphaEvolve: https://arxiv.org/abs/2506.13131
- 실제 사용자 보고: https://medium.com/klarna-engineering/beyond-prompting-how-algorithmic-evolution-doubled-our-training-speed-8f874af3080d
- 공식 모델 가이드: https://developers.openai.com/api/docs/guides/latest-model

수치/사용률/공개 범위의 상세 비교는 [한국어 조사 보고서](RESEARCH_REPORT_KO.md)를 참고하세요. 저자/기업 보고와 이번 로컬 테스트를 구별하며, 별·포크를 실사용자 수로 해석하지 않습니다.
