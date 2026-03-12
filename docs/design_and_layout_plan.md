# 온디바이스 AI 에이전트 시스템: 디자인 및 레이아웃 계획 (Design & Layout Plan)

## 1. 개요
단순한 채팅(Chat) UI를 넘어서, 에이전트의 사고 흐름과 온디바이스 리소스 최적화 상태를 사용자에게 투명하면서도 프리미엄하게 시각화하기 위한 Next.js, shadcn/ui 기반 프론트엔드 디자인 기획 문서입니다.

## 2. 디자인 시스템 및 테마 컨셉
*   **테마 콘셉트**: `미래 지향적 워크스페이스 (Futuristic Workspace)`
*   **베이스 컬러**: 진한 회색(Dark Graphite) 베이스에 프론머티리얼(Glassmorphism) 블러 효과.
*   **포인트 컬러**: 에이전트 액티브 상태는 형광 연두(Neon Green/Cyan), 시스템 오류나 경고(VRAM 초과 등)는 부드러운 주황/빨강으로 명확한 색채 대비.
*   **폰트**: 메인 인터페이스 `Inter`(가독성 확보), 코드/로그 표기 `JetBrains Mono` 및 한국어 본문 텍스트 렌더링에 최적화된 `Pretendard`.

## 3. 핵심 화면 레이아웃 분할

대화형 애플리케이션 화면은 크게 3개의 패널(Panel)로 쪼개어 구성하는 `Three-Pane Layout`을 제안합니다.

### 3.1 왼쪽 패널 (Left Sidebar) - 글로벌 네비게이션 & 메모리
*   **채팅 히스토리 (Sessions)**: 사용자의 이전 대화 세션 목록, 날짜별 자동 그룹화.
*   **기억 관리 탭 (Memory Vault)**: 시스템이 요약하여 가지고 있는 사용자의 장기 기억 파편 리스트 확인 및 직접 삭제/수정 UI 제공.
*   **시스템 설정 (Settings)**: 톱니바퀴 아이콘. LLM 파라미터(Temperature 조정 등) 및 구글 드라이브 인증 버튼 포함.

### 3.2 중앙 패널 (Center Main View) - 인터랙티브 AI 워크스페이스
*   **상태 위젯 (Top Header)**: 현재 작동 중인 오케스트레이터 표시. (예: `🚀 Supervisor Agent Running...`)
*   **채팅 영역 (Chat History Stream)**:
    *   **User Bubble**: 깔끔한 텍스트 래핑 뷰포트.
    *   **Agent Process Accordion (Thought Chain)**: 최종 답변 전 "에이전트가 생각 중입니다..."라는 접힐 수 있는(Collapsible) UI 요소를 제공.
        *   클릭하여 열면: "Tool 호출: Qdrant Search", "Tool 결과 확인", "Tool 호출: Docker Coder 실행" 등 내부 과정(ReAct Thoughts)이 트리에 배치되어 노출됨. (Framer Motion으로 부드럽게 목록이 늘어남)
    *   **Agent Answer Bubble**: 마크다운, 표, 코드가 모두 Syntax Highlighting 처리된 최종 답변 출력 스트리밍 공간.
*   **입력창 (Input Footer)**: 파일 드래그 앤 드롭 첨부(클립 아이콘) 및 다중 프롬프트 입력이 가능한 텍스트 공간 (엔터 전송 기능).

### 3.3 오른쪽 패널 (Right Sidebar) - 하드웨어 & 에코시스템 관제
*   이 패널은 온디바이스 특수성을 살려 다른 웹 기반 챗봇과 차별화되는 핵심 뷰포트입니다.
*   **리소스 대시보드 (Hardware HUD)**:
    *   **VRAM Gauge**: 도넛 구형(원형) 차트로 실시간 점유 VRAM 표시 (`10.5 GB / 16 GB`). 로드가 걸릴 시 맥박 치는 듯한 잔잔한 애니메이션 배정.
    *   **Token Speed**: LLM 토큰 생성 속도(Tx/s)를 작은 스파크라인(Sparkline) 그래프로 표시.
    *   **CPU/RAM 텍스트 지표**: 현재 시스템의 무거움을 체크.
*   **RAG 출처 조사기 (Source Inspector)**:
    *   중앙 화면에서 AI가 문서를 참조했을 때, 관련된 원본 문서 출처 정보(드라이브 내의 파일명, 로컬 파일 경로) 버튼들이 위치.
    *   특정 출처 카드를 클릭 시 우측 패널 하단에 문서의 추출된 원문 청크(Chunk)를 팝업 형태로 미리 볼 수 있는 뷰 제공.

## 4. UI 컴포넌트 프레임워크 활용 전략
*   모든 버튼, 아코디언 컴포넌트, 입력(Input), 다이얼로그(Dialog), 네비게이션 바 등은 `shadcn/ui`의 Radix 코어 접근성 컴포넌트를 사용하여 처음부터 직접 디자인하는 시간을 단축하고 고품질(Accessible) UX를 달성합니다.
*   클라이언트 사이드 상태 트리는 `Zustand`로 결합하여 중앙화(Global Store)하고 컴포넌트 리렌더링과 프레임 드랍을 최소화합니다.
