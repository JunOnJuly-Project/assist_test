import time
import sys
import os
import asyncio
import uuid
import shutil
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
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

# 문서 RAG 모듈 (Phase 2 목적)
from backend.security.file_validator import file_validator
from backend.rag.pipeline import rag_pipeline
from backend.agent.code_agent_engine import code_agent_engine

# 1. FastAPI 코어 애플리케이션 초기화
app = FastAPI(
    title="On-Device Code-Agent Backend",
    version="1.0.0",
    description="CPU 기반 온디바이스 보안 강화 통합 API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 프론트엔드 출처(개발망) 모두 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
@app.post("/chat") # response_model=ChatResponse removed as return type changed to dict
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
            return {
                "status": "success",
                "prompt": prompt,
                "response": cached_response, 
                "is_cached": True, 
                "elapsed_seconds": round(elapsed, 2)
            }

        # --- [Phase 1: 모델 연산 브레인 (CPU-Only 한계통제 블록)] ---
        logger.info("⚙️ [추론 이관] 캐시에 없는 질문입니다. LLM 추론 엔진 연산을 시작합니다...")
        
        # --- [Phase 2: RAG 검색 지식 파이프라인 연계] ---
        # 실제 Ollama 통신 전 LanceDB에서 관련된 지식(Fast-Track)을 꺼내어 Context에 주입합니다.
        try:
            # 1초 만에 문장을 벡터로 바꿈 (CPU 메모리에 존재하는 sroberta 재활용)
            query_vector = await asyncio.to_thread(cache.embedder.encode, prompt)
            # 랜스 DB 검색 (가장 유사한 3개의 조각 픽업)
            rag_contexts = await asyncio.to_thread(rag_pipeline.db.search_similar, query_vector, limit=3)
        except Exception as e:
            logger.warning(f"RAG 검색 중 장애 발생 (Ollama 단독 답변으로 넘어갑니다): {e}")
            rag_contexts = []
            
        final_prompt = prompt
        if rag_contexts:
            context_str = "\n\n".join(rag_contexts)
            # Ollama에게 외부 지식망을 달아줌
            final_prompt = f"다음은 시스템 내부에 저장된 파일 지식입니다. 이를 바탕으로 대답하세요:\n{context_str}\n\n사용자 질의: {prompt}"
            logger.info("📚 [RAG] 지식베이스에서 3개의 관련 문서 조각을 찾아 모델 프롬프트에 주입했습니다.")
        
        # [실제 Ollama 통신 계층] 더미를 제거하고 aiohttp로 로컬 LLM에 비동기 프롬프트를 보냅니다.
        actual_llm_response = await ollama_client.generate_thought_and_action(final_prompt)
        
        # 엔진이 무사히 대답한 내용을 다음 호출을 위해 SQLite에 적재 (최적화)
        # SQLite I/O 역시 100% 동기식이므로 메인 루프 방어 (원래 prompt 기준 저장)
        await asyncio.to_thread(cache.put, prompt, actual_llm_response)
        
        elapsed = time.time() - start_time
        logger.info(f"✅ [정상 반환] 신규 답변 생성이 종료되었습니다. 소요시간: {elapsed:.3f}초")
        
        return {
            "status": "success",
            "prompt": prompt,
            "response": actual_llm_response,
            "is_cached": False, 
            "elapsed_seconds": round(elapsed, 2)
        }
        
    except Exception as e:
        logger.error(f"❌ [Chat EndPoint] 백엔드 채팅 엔진 붕괴: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 코어 연산 중 에러가 터졌습니다.")
    finally:
        # [방어 2번] 버그나 에러로 이 블록을 빠져나가더라도 무조건 CPU 권한(Lock)을 RAG 워커에게 돌려줌
        logger.debug("[Chat] 채팅 사이클 루프 종료. Lock 해제 안전장치 가동.")
        global_lock_manager.release_lock_from_chat()

@app.post("/agent")
async def code_agent_endpoint(request: ChatRequest):
    """
    [Phase 3] 능동형 자율 코딩 에이전트 브레인 진입로.
    단순 Q&A가 아닌, 파이썬 코드를 샌드박스에 돌려보고 싶거나 복잡한 버그 픽싱, 자동화 스크립트 작성 등
    코드와 관련된 임무를 직접 수행하고 검증해주길 바랄 때 호출하는 특수 엔드포인트입니다.
    """
    prompt = request.prompt
    logger.info(f"👨‍💻 [Agent API] 사용자 자율 코딩 미션 수신: {prompt[:30]}...")
    
    # 샌드박스(uv run) 및 마이닝을 위해 CPU Lock 대기는 추후 최적화할 수 있으나
    # 현재는 에이전트 실행이 가장 중요하므로 Lock 획득 후 진행
    await global_lock_manager.acquire_lock_for_chat()
    
    start_time = time.time()
    try:
        # 1. 시맨틱 캐시로 이미 풀었던 코드 미션인지 스킵 시도
        cached = cache.search(f"{prompt} [AGENT_MODE]")
        if cached:
            return {
                "status": "success",
                "source": "cache",
                "response": cached,
                "elapsed_seconds": round(time.time() - start_time, 2)
            }
        
        # 2. 에이전트 엔진에게 미션 위임 (알아서 execute_python_code 툴 사용/반복 검증 수행)
        agent_answer = await code_agent_engine.solve_task(prompt)
        
        # 3. SQLite 캐시에 [AGENT_MODE] 태그를 붙여 저장
        await asyncio.to_thread(cache.put, f"{prompt} [AGENT_MODE]", agent_answer)
        
        elapsed = time.time() - start_time
        return {
            "status": "success",
            "source": "smolagents",
            "response": agent_answer,
            "elapsed_seconds": round(elapsed, 2)
        }
    except Exception as e:
        logger.error(f"❌ [Agent API] 에이전트 샌드박스 붕괴: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        global_lock_manager.release_lock_from_chat()


# 4. 문서 업로드 및 RAG 지식 주입 백그라운드 라우터
@app.post("/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    [지연 처리 RAG 문서 엔드포인트]
    사용자가 파일을 올리면 무서운 보안 검열(file_validator)을 거친 후 일단 "성공!"을 프론트에 즉각 리턴합니다.
    진짜 무거운 PDF 파싱 및 딥러닝 그래프 추출은 '백그라운드 스레드(BackgroundTasks)' 속으로 격리됩니다.
    """
    logger.info(f"📂 새 파일 업로드 요청 감지: {file.filename}")
    
    # [방어 1번] 악성 파일 여부 시그니처 샌드박스 검열 (1초 이내 컷)
    is_safe_file = await file_validator.validate_file(file)
    if not is_safe_file:
        raise HTTPException(
            status_code=415,
            detail="[보안 통제] 지원하지 않는 확장자나 위변조된 악성 파일 형식입니다. (업로드 차단)"
        )
        
    try:
        # FastAPI temp 방어구역에 임시 파일로 격리 저장
        base_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir = os.path.join(base_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # [방어 2번] Path Traversal 원천 차단: 파일명에 섞인 상위 경로 공격 기호를 무효화시키고 UUID 강제화
        safe_filename = os.path.basename(file.filename)
        secure_filename = f"{uuid.uuid4().hex}_{safe_filename}"
        
        file_path = os.path.join(temp_dir, secure_filename)
        _, ext = os.path.splitext(file.filename)
        ext = ext.lower()
        
        # [방어 3번] OOM 폭발 방어: 500MB짜리 PDF도 메모리를 통하지 않고 디스크에 Chunk 단위로 흘려보냄
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        file_size = os.path.getsize(file_path)
        logger.info(f"💾 로컬 격리 보관소에 파일 저장 완료. 용량: {file_size} bytes")
        
        # [백그라운드 파이프라인 트리거]
        # 무거운 파싱과 연산(Fast Track 벡터 인서트 -> 추후 Graph 구축)을 워커에게 미룹니다.
        background_tasks.add_task(
            rag_pipeline.process_document_background, 
            file_path, 
            secure_filename,
            ext,
            cache.embedder  # main.py의 싱글톤 SentenceTransformer를 빌려줌 (RAM 절약)
        )
        
        return {
            "status": "success",
            "message": "📁 파일 검열을 통과하고 백그라운드 엔진에 접수되었습니다. (현재 벡터 전환(Fast Track) 작업 중)",
            "filename": secure_filename
        }
        
    except Exception as e:
        logger.error(f"❌ 파일 업로드 시스템 에러: {e}")
        raise HTTPException(status_code=500, detail="서버 내 파일 처리 중 OOM 또는 디스크 에러가 발생했습니다.")

if __name__ == "__main__":
    # 로컬 네트워크에서만 접근 가능하도록 127.0.0.1 고정
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
