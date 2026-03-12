import os
import asyncio
from loguru import logger

# Phase 2 로컬 RAG 모듈들
from backend.rag.parser.doc_parser import doc_parser
from backend.rag.database.job_queue import job_queue
from backend.rag.database.lancedb_manager import LanceDBManager
from backend.security.thread_lock import global_lock_manager

class RAGPipeline:
    """
    [지연 지식 주입 파이프라인 (Fast Track)]
    FastAPI 엔드포인트가 즉시 응답할 수 있도록, 무거운 문서 처리를 
    백그라운드에서 청크(Chunk) 단위로 쪼개어 조금씩 연산하는 워커(Worker)입니다.
    """
    def __init__(self):
        # LanceDB 인스턴스 (인프로세스 DB)
        self.db = LanceDBManager()
        
    async def process_document_background(self, file_path: str, filename: str, ext: str, embedder):
        """
        FastAPI의 BackgroundTasks에 던져지는 비동기 진입점입니다.
        embedder는 캐시 시스템 메모리에 적재된 변수(SentenceTransformer)를 빌려옵니다.
        """
        job_id = f"job_{filename}_{os.path.getsize(file_path)}"
        
        try:
            # 1. 텍스트 추출 및 청크 분해 (doc_parser)
            logger.info("🔪 [Pipeline] 원본 문서를 가위질(Parsing) 합니다...")
            # 파싱은 무거운 I/O이므로 쓰레드 격리 
            chunks = await asyncio.to_thread(doc_parser.parse_file, file_path, ext)
            total_chunks = len(chunks)
            if total_chunks == 0:
                logger.warning(f"⚠️ [Pipeline] 추출된 텍스트가 없습니다: {filename}")
                return
            
            # 2. 작업 큐 세이브 (절전모드 극복용, 쪼개진 덩어리 수 기록)
            await asyncio.to_thread(job_queue.create_job, job_id, filename, total_chunks)
            
            logger.info(f"⏳ [Pipeline] {total_chunks}조각에 대한 GPU 지식 벡터 변환(Fast Track) 시작...")
            
            # 3. DB 파편화를 막고 성능을 끌어올리기 위한 Batch 처리 세팅
            batch_texts = []
            batch_vectors = []
            BATCH_SIZE = 10
            
            for i, chunk in enumerate(chunks):
                
                # [안전장치] 채팅 스레드가 CPU를 뺏어갔는지 확인 (비차단 확인)
                while True:
                    can_process = await global_lock_manager.check_lock_for_background()
                    if can_process:
                        break # CPU 널널함 -> RAG 진행
                    else:
                        # 유저 채팅 중 -> RAG는 눈치보며 3초 대기 
                        await asyncio.sleep(3)
                        
                # 임베딩 비용 발생구간 (쓰레드 격리)
                vector = await asyncio.to_thread(embedder.encode, chunk)
                batch_texts.append(chunk)
                batch_vectors.append(vector)
                
                # 배치 사이즈에 도달하거나 마지막 조각인 경우 일괄 LanceDB 삽입
                if len(batch_texts) >= BATCH_SIZE or i == total_chunks - 1:
                    await asyncio.to_thread(self.db.insert_chunks, filename, batch_texts, batch_vectors)
                    # 처리된 개수만큼 마이크로 커밋
                    await asyncio.to_thread(job_queue.update_progress, job_id, i + 1, "FAST_TRACK_PROCESSING")
                    # 버퍼 비우기
                    batch_texts.clear()
                    batch_vectors.clear()
                
                # 노트북 프리징 방지용 숨돌리기 (0.1초)
                await asyncio.sleep(0.1)
                
            # 4. Fast Track (벡터 저장) 완료 (추후 Phase 2 2부에서 Graph 연산으로 넘길 지점)
            await asyncio.to_thread(job_queue.update_progress, job_id, total_chunks, "FAST_TRACK_DONE")
            logger.info(f"🎉 [Pipeline] {filename}의 문서 벡터 생성이 종료되었습니다! 이제 로컬 검색이 가능합니다.")
                
        except Exception as e:
            logger.error(f"❌ [Pipeline] 파이프라인 백그라운드 붕괴 (OOM 또는 파일손상): {e}")
            await asyncio.to_thread(job_queue.update_progress, job_id, 0, "FAILED")
            
        finally:
            # [방어막] 파싱 중 에러가 나거나 크래시가 발생해도 항상 임시 파일을 삭제 (디스크 좀비화 방어)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.debug(f"[Pipeline] 격리되었던 임시 파일을 안전하게 파기했습니다: {file_path}")
                except Exception as e:
                    logger.warning(f"[Pipeline] 임시 파일 삭제 실패: {e}")

rag_pipeline = RAGPipeline()
