# 온디바이스 AI 에이전트 시스템: 인프라 아키텍처 (Infrastructure Architecture) - [최종 합의: CPU-Only 통합본]

## 1. 개요
본 문서는 시니어 위원회 합의 사항을 반영, Code-Agent 파이프라인과 파이썬 호환성 100% 샌드박스(`uv` 격리), 그리고 `Thread-Lock` 통신 메커니즘이 노트북(CPU-Only)에서 병목 없이 동작하기 위한 논리/물리 구조를 정의합니다.

## 2. 시스템 자원 분배 전략 (Hardware Allocation)
모든 무거운 백그라운드 서버(Docker 등)를 완전히 제거하고 시스템 메모리(RAM)를 철저히 분할해야만 노트북 팬 소음과 시스템 셧다운을 방어할 수 있습니다.

*   **System RAM 사용량 (최소 16GB 권장)**: 
    *   약 `4.5~6GB` : `Ollama` 7B~8B 모델 가중치 및 KV Cache.
    *   약 `0.8GB` : `ProtectAI` 프롬프트 방어 모듈 + `sroberta` 다국어 임베딩 처리.
    *   약 `8GB+` : 순수 OS, 렌더링, 샌드박스 및 LightRAG 인제스천 버퍼 확보 (Zero-Docker/Zero-Qdrant 전략).

## 3. 핵심 레이어 포트 배정 및 아키텍처 다이어그램

| 레이어 | 프로세스 / 기술 | 통신 규격 | 보안 및 리소스 특징 |
| :-- | :--- | :--- | :--- |
| **Presentation Tier** | `Next.js` Server | HTTP `3000` | UI 라우팅 및 CPU 상태(%) 관제 위젯 |
| **Security Intercept**| `ProtectAI` Deberta | In-Process | LLM 탑승 전 사용자 프롬프트 악의성 CPU 연산 (0.1초 컷) |
| **Orchestration Tier** | `FastAPI` (Code-Agent) | HTTP `8000` | **[중요]** 전역 Thread-Lock State 공유 메모리 배정 |
| **Model Serving Tier**| `Ollama` Daemon | REST `11434` | **CPU 전용 텐서 연산** (물리 코어 수에 맞춰 `num_thread` 제한) |
| **Knowledge Tier** | `LanceDB` (LightRAG) | `0` (내장) | FastAPI 워커 프로세스 안에 내장. DB 서버 부하 완전 소멸 |
| **Code Execution Sandbox**| `uv run --isolated` | OS CLI 직결 | 파이썬 생태계(Pandas, Numpy 등) 100% 지원 및 OS 파일 접근 차단 |

## 4. 컴포넌트별 아키텍처 상세 (Decision Make & Risk)

### 4.1 오케스트레이션(FastAPI) 및 스레드 락(Thread-Lock) 전략
*   **결정사유 원리**: 노트북 CPU 한계를 극복하기 위한 필수 안전장치.
    *   Background 스케줄러(RAG Ingestion Queue)가 문서 파싱과 요약을 진행할 때, 유저의 API `GET /chat/stream`이 들어오면 Background Task에 `Event.wait()` 혹은 `Lock`을 걸어 멈춥니다.
    *   채팅 응답이 종료되어 LLM 자원이 반환되면 다시 락을 해제하여 문서 굽기를 재개하는 소프트웨어 스위치를 둡니다.

### 4.2 보안 실행 환경 (Code Execution): 파이썬 생태계 통합
*   **결정사유 및 최적화**: 기존 `Deno`는 JS/TS 특화라 파이썬 코드를 쏟아내는 Agent와 궁합이 맞지 않는 리스크가 컸습니다. 
*   **해결책**: 백엔드 시스템과 같은 Python 체계지만, 호스트 OS 환경변수를 전혀 물려받지 못하는 `uv run --isolated` 명령어 래퍼를 호출하여 에이전트의 계산식을 독립 실행 후 문자열 출력(STDOUT)만 회수합니다.

### 4.3 DB 인프라: In-Process Database (LanceDB + LightRAG) 
*   **장점 극대화**: Qdrant나 Neo4J 등 무거운 컨테이너를 없앤 LanceDB 구조는 랩탑에서 램(RAM) 자원을 방어하는 최선책입니다.
