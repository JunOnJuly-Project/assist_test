import time
import sys
import os
import asyncio
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger
import uvicorn

# backend 폴더 위치를 파이썬 경로에 추가 (명령어 'python main.py' 구동 호환성 해결)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 커스텀 보안/최적화/통신 모듈 (Phase 1 목적)
from backend.security.guardrail import PromptGuard
from backend.cache.semantic import SemanticCache
from backend.security.thread_lock import global_lock_manager
from backend.api.ollama_client import ollama_client

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
    # [방어막 1] 무제한 프롬프트 폭격(DoS)을 막기 위해 4000자 제한 강제 통제
    prompt: str = Field(..., max_length=4000, description="사용자 질문 (최대 4000자)")

class ChatResponse(BaseModel):
    response: str
    is_cached: bool
    execution_time_sec: float

# 3. 채팅/검색 메인 엔드포인트
@app.post("/chat", response_model=ChatResponse)
async def unified_chat_endpoint(request: ChatRequest):
    """
    사용자의 실제 입력을 비동기로 받아 처리합니다. 
    최우선순위(채팅) 작업이므로 글로벌 CPU 락을 획득하여 문서(RAG) Ingestion 등의 백그라운드 작업을 막습니다.
    """
    prompt = request.prompt.strip()
    logger.info(f"📩 새 채팅 유입: '{prompt}'")
    
    start_time = time.time()
    lock_acquired = False
    
    try:
        # [방어막 2] 채팅 세션 진입 전 반드시 스레드 락(CPU 권한)을 획득 대기합니다.
        await global_lock_manager.acquire_lock_for_chat()
        lock_acquired = True

        # --- [Phase 0: 캐시 및 악의성 인터셉터 계층] ---
        # [방어막 3] 메인 비동기 루프 대기열 마비(Deadlock)를 막기 위해 별도 스레드로 격리하여 실행
        is_safe = await asyncio.to_thread(guard.check_prompt, prompt)
        if not is_safe:
            logger.warning(f"🚨 [보안 경고] 악의적 프롬프트 인젝션이 감지되어 세션을 차단했습니다.")
            raise HTTPException(
                status_code=403, 
                detail="[보안 통제] 인젝션 공격 또는 금지된 프롬프트가 감지되었습니다. 요청이 차단됩니다."
            )

        cached_response = await asyncio.to_thread(cache.search, prompt)
        if cached_response:
            elapsed = time.time() - start_time
            logger.info(f"⚡ [최적화 반환] 캐시 반환에 성공했습니다. 소요시간: {elapsed:.3f}초")
            return ChatResponse(
                response=cached_response, 
                is_cached=True, 
                execution_time_sec=round(elapsed, 3)
            )

        # --- [Phase 1: 모델 연산 브레인 (CPU-Only 한계통제 블록)] ---
        logger.info("⚙️ [추론 이관] 캐시에 없는 질문입니다. LLM 추론 엔진 연산을 시작합니다...")
        
        # [실제 Ollama 통신 계층] 더미를 제거하고 aiohttp로 로컬 LLM에 비동기 프롬프트를 보냅니다.
        actual_llm_response = await ollama_client.generate_thought_and_action(prompt)
        
        # 엔진이 무사히 대답한 내용을 다음 호출을 위해 SQLite에 적재 (최적화)
        # SQLite I/O 역시 100% 동기식이므로 메인 루프 방어
        await asyncio.to_thread(cache.put, prompt, actual_llm_response)
        
        elapsed = time.time() - start_time
        logger.info(f"✅ [정상 반환] 신규 답변 생성이 종료되었습니다. 소요시간: {elapsed:.3f}초")
        
        return ChatResponse(
            response=actual_llm_response, 
            is_cached=False, 
            execution_time_sec=round(elapsed, 3)
        )
        
    finally:
        # [방어막 4] 실제로 락을 취득했을 때만 풀리도록 Fail-Safe 예외를 정밀하게 분리
        if lock_acquired:
            try:
                global_lock_manager.release_lock_from_chat()
            except Exception as e:
                logger.error(f"❌ [TaskManager] Lock 강제 해제 중 충돌 방어됨: {e}")

if __name__ == "__main__":
    # 로컬 네트워크에서만 접근 가능하도록 127.0.0.1 고정
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
