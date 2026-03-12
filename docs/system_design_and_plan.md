# 온디바이스 AI 에이전트 시스템 최종 설계 및 계획 (고도화 버전)

## 1. 개요
본 문서는 `gpt-oss-20b` 수준의 오픈소스 대형 언어 모델(LLM)을 온디바이스 환경에서 구동하며, RAG(검색 증강 생성) 및 다중 타스크를 처리하는 다중 에이전트(Multi-Agent) 시스템의 아키텍처 및 개발 계획을 정의합니다. 앞서 제안된 모든 확장 기능(메모리, 샌드박스, 다중 에이전트, 모니터링)을 기본 요구사항으로 통합하였으며, 성능 향상과 최신 트렌드를 반영한 최적의 기술 스택을 선별했습니다. 모든 작업의 논의 및 의사결정 과정은 이 본 문서 및 `docs` 하위 디렉토리에 철저히 기록됩니다.

## 2. 고도화된 시스템 아키텍처 및 최적 기술 스택

기존의 기본 구상을 바탕으로, 실제 온디바이스 환경에서의 성능(속도 및 VRAM 최적화)과 프리미엄급 사용자 경험(UX)을 확보하기 위해 스택을 전면 업그레이드했습니다.

### 2.0 온디바이스 모델 구동 플랫폼 (고도화)
*   **핵심 추론 엔진**: `vLLM` 또는 `llama.cpp` (PyTorch 생태계 연계)
    *   단순 `Transformers` + `bitsandbytes` 조합은 다중 요청 처리나 토큰 생성 속도에 한계가 있습니다. 메모리 관리 기법(PagedAttention)이 적용된 **vLLM**(PyTorch 기반)을 우선 고려합니다.
    *   *Windows 환경 고려 사항*: 로컬 Windows 환경에서는 vLLM 구동이 까다로울 수 있으므로, GGUF 양자화 포맷을 활용하는 **llama.cpp (llama-cpp-python)** 기반 서버를 구축하는 것이 가장 현실적이고 강력합니다. RAG 및 에이전트 엔진은 PyTorch와 연계합니다.
*   **서빙 API**: `FastAPI` + `SSE (Server-Sent Events) / WebSocket`
    *   에이전트의 사고 과정(Thought Process)과 답변을 끊김 없이 실시간 스트리밍합니다.

### 2.1 추론 및 프론트엔드 인터페이스 (UI)
*   **프론트엔드 프레임워크**: `Next.js 14+ (App Router)` + `TypeScript`
*   **UI/UX 디자인 디자인 시스템**: `Tailwind CSS` + `shadcn/ui` + `Framer Motion`
    *   초기 프로토타입용 Gradio/Streamlit은 에이전트의 사고 흐름, 도구 사용 액션, VRAM 사용량 등을 동시에 우아하게 시각화하기 어렵습니다.
    *   따라서 세련되고 직관적인 현대식 프리미엄 디자인을 위해 **shadcn/ui** 컴포넌트를 베이스로 맞춤형 대시보드를 구축하고, **Framer Motion**으로 부드러운 애니메이션을 가미합니다.
*   **상태 관리**: `Zustand` 및 `React Query` (채팅 상태 및 실시간 데이터 페칭)

### 2.2 프레임워크 및 에이전트 오케스트레이션
*   **오케스트레이션 코어**: `LangGraph` + `PyTorch`
    *   단일 LangChain의 ReAct를 넘어, 상태(State) 기반의 순환형 파이프라인 제어가 가능한 **LangGraph**를 도입합니다.
*   **다중 에이전트 아키텍처 (Multi-Agent System)**:
    1.  **Supervisor**: 사용자의 요청을 분석하고, 어떠한 에이전트(검색, 코딩 등)를 호출할지 결정하는 오케스트레이터.
    2.  **RAG Agent**: 드라이브 및 로컬 문서에서 적절한 정보를 검색해오는 전담 에이전트.
    3.  **Coder Agent**: 복잡한 수학, 로직 처리를 위해 파이썬 코드를 작성하고 샌드박스로 전송하는 에이전트.

### 2.3 RAG (문서 및 Google Drive 연동) 최적화
*   **데이터 파싱 및 수집 (Ingestion)**:
    *   최신 트렌드인 `LlamaParse` 또는 `Unstructured` 모듈을 도입해 텍스트 뿐만 아니라 PDF 내의 표, 차트 등을 정확히 추출합니다.
    *   Google Drive OAuth2 연동으로 백그라운드에서 동기화되는 로더 구성.
*   **오픈소스 임베딩**: PyTorch 기반 `SentenceTransformers` (`BGE-m3` 등 한국어 및 다국어 지원이 탁월한 최신 오픈소스 모델 로컬 구동)
*   **벡터 데이터베이스**: `ChromaDB` 또는 `Qdrant` (로컬)
    *   순수 코사인 유사도 검색을 넘어, 키워드 검색(BM25)을 결합한 **Hybrid Search**와 결과 순위를 재조정하는 **Cross-Encoder Re-ranking** 기법을 적용해 RAG의 답변 퀄리티를 대폭 상향시킵니다.

### 2.4 코드 실행 샌드박스 (Code Sandbox)
*   **실행 환경**: `Docker` 컨테이너 또는 `Jupyter Kernel Sandbox`
    *   Coder Agent가 생성한 Python 코드가 온디바이스의 호스트 OS에 손상을 주지 않도록 격리된 컨테이너 내부에서 실행 후 표준 출력(stdout) 결과만 가져오는 안전망을 설계합니다. (PyTorch 등의 기초 라이브러리가 포함된 베이스 이미지 활용).

### 2.5 장단기 메모리 시스템 (Memory Management)
*   **구현 방법**: 컴포넌트 간 메모리 분리
    *   단기: 현재 채팅 세션의 메시지 히스토리는 LangGraph의 `Checkpointer`를 통해 SQLite에 기록.
    *   장기: 대화 간 사용자의 정보를 요약 추출하고, 이를 벡터화하여 데이터베이스에 적재 후 다음 세션 시작 시 Context로 끌어옵니다. (Ex: "내 이전 프로젝트 이름이 뭐였지?"에 답변 가능).

### 2.6 로깅 및 리소스 하드웨어 모니터링
*   **로깅 시스템**: `Loguru` + `SQLite` 로컬 추적
    *   에이전트의 모든 의사결정 이력, API 속도, 토큰 소모량을 파일과 DB로 기록하여 디버깅 근거를 남깁니다.
*   **하드웨어 관제**: Python `pynvml` (NVIDIA GPU 상태 측정) 및 `psutil` (CPU/RAM 추적)
    *   UI 상단에 VRAM 점유 시간 및 현재 사용량을 실시간 위젯으로 띄워, RAG나 대량 토큰 추론 시 터질 수 있는 OOM(Out of Memory) 현상을 사용자가 사전에 인지할 수 있도록 돕습니다.

---

## 3. 세부 워크플로우 (Phase Plan)

아키텍처 변경점을 고려하여 다음과 같이 단계별 워크플로우를 최적화했습니다.

*   **Phase 1: 기반 엔진 빌드 및 하드웨어 모니터 시스템**
    *   목표 모델(20B)의 양자화 버젼 구동 환경(vLLM/llama.cpp) 구성.
    *   FastAPI 인프라 구축 및 pynvml 기반 리소스 모니터링 모듈 개발 시작.
*   **Phase 2: RAG 기초 컴포넌트 및 로컬 DB 연동**
    *   PyTorch 기반의 임베딩 모델(SentenceTransformers) 통합.
    *   로컬/구글 드라이브 파싱 시스템 및 Qdrant/Chroma 벡터 저장소 아키텍처 구현 (Re-ranking 포함).
*   **Phase 3: LangGraph 다중 에이전트 및 기능 확장**
    *   Supervisor, Coder, RAG 에이전트 워크플로우 작성.
    *   Docker를 활용한 코드 샌드박스 기능 툴(Tool)로 연동 배포.
    *   장단기 메모리 기록 로직 구현.
*   **Phase 4: 전체 시스템 로깅 및 Backend 통합 테스트**
    *   Loguru를 통해 LangGraph의 매 Checkpoint와 Action을 DB화.
    *   RAG 정확도와 에이전트 툴 사용(CodeSandbox) 안정성 검증.
*   **Phase 5: 프리미엄 UI (Next.js) 프로덕션 개발**
    *   React, shadcn/ui 기반 대시보드 구축 및 SSE(스트리밍) 엔드포인트 연동.
    *   사용자 화면에 체이닝 과정과 하드웨어 지표 시각화 처리.
