# 온디바이스 AI 에이전트 시스템: 시스템 블루프린트 (Blueprint) - [최종 합의: CPU-Only 통합본]

## 1. 개요
본 블루프린트는 시니어 아키텍트, 연구원, 프로젝트 매니저 3인의 합의를 거쳐 **NVIDIA GPU가 없는 인텔 랩탑(CPU-Only) 환경**에서도 100% 프라이버시가 보장되는 AI 에이전트를 가장 쾌적하게 구동하기 위해 설계된 마스터 청사진입니다. 하드웨어 스로틀링과 OOM을 원천 봉쇄하는 "Zero-Overhead 기조"와 "방어적 자원 통제"가 핵심입니다.

## 2. 핵심 비전 (Core Vision)
*   **완전한 프라이버시(True On-Device)**: 외부 통신 일절 차단. 문서 파싱부터 벡터 연산, 보안 필터링까지 100% 오프라인 처리.
*   **초고효율 Code-Agent 도입**: `SmolAgents`를 채용하여 7~8B 급 모델(`Qwen2.5-Coder` 등)이 JSON 파싱 에러 없이 "파이썬 코드" 자체로 사고/행동을 쥐어짜 내도록 유도.
*   **CPU 마비 방어 (병목 통제)**: 에이전트 대화(채팅) 중에는 LightRAG의 무거운 문서 Ingestion을 강제로 동결시키는 **Thread-Lock(스레드 락)** 메커니즘을 적용하여 시스템 프리징 타파.
*   **파이썬 최적화 보안 샌드박스**: 언어 호환성이 안 맞는 Deno 대신, 호스트 OS를 보호하는 파이썬 네이티브 격리 환경인 **`uv run --isolated`** (또는 WebAssembly Pyodide)를 채택하여 0% 해킹 리스크와 100% 언어 호환성 동시 달성.

## 3. 핵심 모듈 구성 (Core Modules)

### 3.1 LLM 오프로딩 엔진 및 CPU 가속기 (Inference & Acceleration)
*   **핵심 스택**: `Ollama` (CPU 전용 모드 구동, `llama.cpp` AVX2 명령어 최적화).
*   **최적화 파이프라인**: 
    1.  `Semantic Caching (GPTCache)`: 중복 질문 0.1초 즉시 병합. CPU 연산 코스트 제로화.
    2.  `KV Cache 유지`: 문맥 상태를 텐서로 System RAM에 유지시켜 대기시간 10배 단축.
    3.  `지능형 스케일 다운`: Phase 1에서 토큰 생성 속도(TPS)가 5 미만일 경우 `Phi-3.5-mini` 등 3B 모델로 즉각 강등하는 자동화 룰.

### 3.2 오케스트레이션 및 코드 에이전트 브레인 (Code-Agent Brain)
*   **스택**: FastAPI 서버 + `SmolAgents`. (스트리밍 SSE 중심)

### 3.3 복합 지식망 검색 엔진 (Knowledge & LightRAG Engine)
*   **스택**: `LanceDB` (In-process 벡터/그래프 보관) + `LightRAG`.
*   **파이프라인 통제**: CPU 스레드 충돌을 막기 위해 백그라운드 태스크(Celery/BackgroundWorker)로 분리하고, 채팅 API 호출 시 `Lock`을 걸어 자원을 양보함. 문서 파서는 `Docling` 로컬 파서 활용.

### 3.4 무결점 보안 및 실행 샌드박스 (Security & Python Sandbox)
*   **보안 방어 (Red Teaming)**: `ProtectAI/deberta-v3-base-prompt-injection-v2` (초경량 300MB 로컬 필터)가 악의적 프롬프트 선제 방어.
*   **파이썬 샌드박스**: 파이썬 코드를 읽도록 강제된 에이전트의 산출물을 **`uv` 워크스페이스 격리 스크립트** 혹은 `Pyodide` 임베디드 공간에 던져 호스트 PC 디렉토리 손상 리스크 완전 소멸.

### 3.5 프론트엔드 대시보드 및 리소스 관제 (Frontend & Observation)
*   **스택**: `Next.js`, `shadcn/ui`, `Zustand`.
*   **모니터링 대상**: VRAM 게이지를 완전히 삭제하고, **CPU 스로틀링(온도/점유율) 및 System RAM 잔여량**을 1순위로 시각화하여 노트북 쿨링 타임을 유저에게 알림.

## 4. 시니어 위원회(PM, Arch, R&D)의 결정사항 요약
*   문서 처리(LightRAG)와 채팅(추론)은 절대 랩탑에서 동시 실행 불가함을 천명.
*   모델은 7B 규모 파이썬 특화 모델(`Qwen2.5-Coder`)을 Base로 삼되, 5 TPS(Tokens Per Second) 미달 시 즉시 3B 급으로 롤백.
*   가장 비용(Cost)이 저렴하고 이식성이 높은 파이썬 초고속 패키지 매니저 `uv`를 활용한 샌드박스 체제로 일원화.
