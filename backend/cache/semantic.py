import os
import sqlite3
import hashlib
import numpy as np
from sentence_transformers import SentenceTransformer
from loguru import logger

class SemanticCache:
    def __init__(self, threshold: float = 0.95):
        """
        [최적화] CPU 병목 및 LLM 추론 비용(Cost)을 원천 차단하기 위해 동일/유사 질문에 즉시 캐시 응답을 뱉어내는 모듈입니다.
        대형 벡터 DB(Chroma 등) 대신 기본 내장 sqlite3를 사용하여 노트북 System RAM 소모를 극한으로 줄입니다.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(base_dir, "database", "semantic_cache.db")
        weights_dir = os.path.join(base_dir, "weights")
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(weights_dir, exist_ok=True)
        
        model_name = "jhgan/ko-sroberta-multitask"
        self.threshold = threshold
        
        logger.info(f"🧠 시맨틱 캐시(GPTCache) 임베딩 모델 로드 중... ({model_name})")
        
        # CPU 코어 강제 할당 (GPU 에러 완전 차단)
        try:
            self.embedder = SentenceTransformer(model_name, cache_folder=weights_dir, device='cpu')
            self._init_db()
            logger.info("✅ 시맨틱 캐시 시스템 구동 및 SQLite 연결 완료.")
        except Exception as e:
            logger.error(f"임베딩 로드 및 DB 초기화 실패: {e}")
            raise e

    def _init_db(self):
        """SQLite 캐시 테이블 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    id TEXT PRIMARY KEY,
                    prompt TEXT,
                    embedding BLOB,
                    response TEXT
                )
            ''')
            conn.commit()

    def _serialize_embedding(self, emb: np.ndarray) -> bytes:
        """NumPy 벡터를 SQLite BLOB 저장을 위해 바이트 변환"""
        return emb.tobytes()

    def _deserialize_embedding(self, blob: bytes) -> np.ndarray:
        """SQLite BLOB을 NumPy Float32 벡터로 복원"""
        return np.frombuffer(blob, dtype=np.float32)

    def search(self, prompt: str) -> str | None:
        """
        입력 프롬프트와 가장 유사한(threshold 이상) 이전 대화 응답을 검색하여 반환합니다.
        """
        query_emb = self.embedder.encode(prompt).astype(np.float32)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT embedding, response FROM cache')
            rows = cursor.fetchall()
            
            best_score = -1.0
            best_response = None
            
            for blob, response in rows:
                emb = self._deserialize_embedding(blob)
                # 코사인 유사도(Cosine Similarity)를 통해 의미적 일치 판별. 0으로 나누기 뻗음(Division by Zero) 방지
                norm_query = np.linalg.norm(query_emb)
                norm_emb = np.linalg.norm(emb)
                denominator = norm_query * norm_emb + 1e-9
                score = np.dot(query_emb, emb) / denominator
                if score > best_score:
                    best_score = float(score)
                    best_response = response
            
            # 기준치(95% 등) 통과 시 캐시 반환
            if best_score >= self.threshold:
                logger.info(f"💡 [Cache Hit] 유사도 {best_score:.3f} 돌파. LLM 추론 없이 즉시 반환합니다.")
                return best_response
                
        logger.debug(f"[Cache Miss] 일치하는 과거 대화가 없습니다.")
        return None

    def put(self, prompt: str, response: str):
        """
        새로운 대화 질의와 LLM 에이전트의 답변을 캐시 DB에 저장합니다.
        """
        query_emb = self.embedder.encode(prompt).astype(np.float32)
        # 텍스트 기반 해시값으로 고유 ID 생성 (빠른 중복 무시)
        prompt_hash = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT OR IGNORE INTO cache (id, prompt, embedding, response) 
                VALUES (?, ?, ?, ?)
                ''',
                (prompt_hash, prompt, self._serialize_embedding(query_emb), response)
            )
            conn.commit()
        logger.debug(f"[Cache Add] 새 답변 저장 이력 완료 (Hash ID: {prompt_hash[:8]})")
