import time
import sys
import os
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from loguru import logger
import uvicorn

# backend 폴더 위치를 파이썬 경로에 추가 (명령어 'python main.py' 구동 호환성 해결)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 커스텀 보안/최적화 모듈 (Phase 1 목적)
from backend.security.guardrail import PromptGuard
from backend.cache.semantic import SemanticCache

# 1. FastAPI 코어 애플리케이션 초기화
app = FastAPI(
    title="On-Device Code-Agent Backend",
    version="1.0.0",
    description="CPU 기반 온디바이스 보안 강화 통합 API"
)

# 글로벌 모듈 로컬 캐싱 공간 (인터셉터)
guard: PromptGuard = None
cache: SemanticCache = None

@app.on_event("startup")
def startup_event():
    """서버 부팅 시 무거운 머신러닝 모델(Guard, Cache Embedder)을 시스템 메모리에 단 1회 로드합니다."""
    global guard, cache
    try:
        logger.info("🚀 [Startup] 시스템 전역 초기화 가동을 시작합니다...")
        guard = PromptGuard()
        cache = SemanticCache(threshold=0.95)
        logger.info("✅ [Startup] 모든 보호막 및 캐싱 엔진 준비 완료. API를 개방합니다.")
    except Exception as e:
        logger.error(f"❌ [Startup] 핵심 모듈 초기화 에러 (서버 기동 실패): {e}")
        # 모듈이 터지면 해킹 위험이 있으므로 시스템 안전 종료
        raise e

# 2. 입출력 스키마(DTO) 정의
class ChatRequest(BaseModel):
    prompt: str

class ChatResponse(BaseModel):
    response: str
    is_cached: bool
    execution_time_sec: float

# 3. 채팅/검색 메인 엔드포인트
@app.post("/chat", response_model=ChatResponse)
def unified_chat_endpoint(request: ChatRequest):
    prompt = request.prompt.strip()
    logger.info(f"📩 새 채팅 유입: '{prompt}'")
    
    start_time = time.time()

    # --- [Phase 0: 캐시 및 락 획득 인터셉터 계층] ---

    # 1단계. 악의성 검열 (Red Teaming Security)
    # 시스템 프롬프트 조작이나 파이썬 샌드박스 공격 언어를 막아냅니다.
    is_safe = guard.check_prompt(prompt)
    if not is_safe:
        logger.warning(f"🚨 [보안 경고] 악의적 프롬프트 인젝션이 감지되어 세션을 차단했습니다.")
        raise HTTPException(
            status_code=403, 
            detail="[보안 통제] 인젝션 공격 또는 금지된 프롬프트가 감지되었습니다. 요청이 차단됩니다."
        )

    # 2단계. 시맨틱 캐시(GPTCache) 확인
    # Ollama 엔진(CPU 극한 점유)을 호출하기 전 메모리 DB에서 과거 답변 서치.
    cached_response = cache.search(prompt)
    if cached_response:
        elapsed = time.time() - start_time
        logger.info(f"⚡ [최적화 반환] 캐시 반환에 성공했습니다. 소요시간: {elapsed:.3f}초")
        return ChatResponse(
            response=cached_response, 
            is_cached=True, 
            execution_time_sec=round(elapsed, 3)
        )

    # --- [Phase 1: 현재는 더미 Code-Agent 응답 처리 (Ollama 파이프라인 전)] ---
    # 나중에 여기에 Thread-Lock 및 SmolAgents가 바인딩됩니다.
    logger.info("⚙️ [추론 이관] 캐시에 없는 질문입니다. LLM 추론 엔진 연산을 시작합니다...")
    
    # 임시 목업 답변 (백엔드 통합 검증용)
    simulated_agent_response = f"Ollama 7B 모델에서 '{prompt}'에 대한 구조화된 답변을 생성했습니다. (Phase 1 더미 응답입니다)"
    time.sleep(1.5) # 연산 딜레이 시뮬레이션
    
    # 엔진이 열심히 대답한 내용을 다음 호출을 위해 1초 만에 SQLite에 적재 (최적화)
    cache.put(prompt, simulated_agent_response)
    
    elapsed = time.time() - start_time
    logger.info(f"✅ [정상 반환] 신규 답변 생성이 종료되었습니다. 소요시간: {elapsed:.3f}초")
    
    return ChatResponse(
        response=simulated_agent_response, 
        is_cached=False, 
        execution_time_sec=round(elapsed, 3)
    )

if __name__ == "__main__":
    # 로컬 네트워크에서만 접근 가능하도록 127.0.0.1 고정
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
