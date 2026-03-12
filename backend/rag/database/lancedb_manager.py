import os
import lancedb
import numpy as np
from loguru import logger

class LanceDBManager:
    """
    [핵심 벡터 스토리지: LanceDB]
    SQLite처럼 서버리스(In-process)로 로컬 디스크에 꽂히면서도, 
    수만 개의 텍스트를 초고속(AVX 최적화)으로 벡터 검색할 수 있는 랩탑 친화적 DB입니다.
    사용자가 업로드한 'Fast Track(요약 벡터)' 문서 조각들이 이곳에 저장됩니다.
    """
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(base_dir, "database", "lancedb_rag")
        os.makedirs(self.db_path, exist_ok=True)
        
        # LanceDB 커넥션 형성
        try:
            self.db = lancedb.connect(self.db_path)
            self.table_name = "document_chunks"
            logger.info(f"⚡ [LanceDB] 로컬 벡터 스토리지 바인딩 완료. (저장소: {self.db_path})")
        except Exception as e:
            logger.error(f"[LanceDB] 연결 실패: {e}")

    def insert_chunks(self, filename: str, chunks: list, embeddings: list):
        """
        [Fast Track] 
        파서가 자른 문서 조각(청크)과 임베딩(벡터 숫자)들을 배열로 받아,
        단 1초 만에 로컬 데이터베이스에 들이붓습니다(Insert).
        
        :param filename: 소속된 문서 출처
        :param chunks: ["문서 조각1", "조각2", ...]
        :param embeddings: [ [0.1, 0.2, ...], [0.3, 0.4, ...], ... ]
        """
        data = []
        for i, (text, vector) in enumerate(zip(chunks, embeddings)):
            data.append({
                "id": f"{filename}_chunk_{i}",
                "filename": filename,
                "text": text,
                "vector": vector
            })
            
        try:
            # 테이블이 없으면 생성, 있으면 끝부분에 이어서 삽입(Append)
            if self.table_name not in self.db.table_names():
                # 데이터가 1개라도 있어야 스키마가 잡힘
                self.table = self.db.create_table(self.table_name, data=data)
                logger.info("⚡ [LanceDB] 'document_chunks' 1호 테이블이 최초 개통되었습니다.")
            else:
                self.table = self.db.open_table(self.table_name)
                self.table.add(data)
                
            logger.debug(f"[LanceDB] 문서 {filename}의 총 {len(data)}개 벡터 조각 저장 완료.")
            
        except Exception as e:
            logger.error(f"[LanceDB] 청크 삽입(Insert) 중 크래시: {e}")

    def search_similar(self, query_vector: np.ndarray, limit: int = 3) -> list:
        """사용자가 채팅을 치면 관련된 조각 3개를 찾아서 꺼내옵니다."""
        try:
            if self.table_name not in self.db.table_names():
                return []
                
            table = self.db.open_table(self.table_name)
            # 코사인 유사도 연산으로 관련성 높은 문맥 즉시 Search
            results = table.search(query_vector).limit(limit).to_pandas()
            
            contexts = []
            for _, row in results.iterrows():
                contexts.append(row["text"])
            
            return contexts
        except Exception as e:
            logger.error(f"[LanceDB] 유사도 검색 중 에러 발생: {e}")
            return []

lancedb_manager = LanceDBManager()
