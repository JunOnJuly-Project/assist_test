import sqlite3
import os
import json
from loguru import logger
from datetime import datetime

class JobQueueManager:
    """
    [지연 처리 기반 마이크로 세이브 매니저]
    문서 파싱 및 그래프(LightRAG) 연산이 길어질 경우, 노트북 절전 모드나 크래시에 의해
    작업 데이터가 날아가는 것을 방지하기 위해 Chunk(청크) 단위로 진행 상태를 SQLite에 수시로 기록합니다.
    """
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(base_dir, "database", "rag_jobs.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Job Queue 메타데이터 테이블 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id TEXT PRIMARY KEY,
                        filename TEXT,
                        total_chunks INTEGER DEFAULT 0,
                        processed_chunks INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'PENDING',  -- PENDING, FAST_TRACK_DONE, GRAPH_EXTRACTING, DONE, FAILED
                        created_at TEXT
                    )
                ''')
                conn.commit()
                logger.info("📦 [JobQueue] 지연 처리 작업 복구용 SQLite 테이블 연결 완료.")
        except Exception as e:
            logger.error(f"[JobQueue] DB 초기화 실패: {e}")

    def create_job(self, job_id: str, filename: str, total_chunks: int):
        """새로운 문서 업로드 시, 작업을 등록합니다."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO jobs (job_id, filename, total_chunks, status, created_at)
                VALUES (?, ?, ?, 'PENDING', ?)
            ''', (job_id, filename, total_chunks, now))
            conn.commit()
        logger.debug(f"[JobQueue] 큐 등록 완료: {filename} (ID: {job_id}, 예상 {total_chunks}조각)")

    def update_progress(self, job_id: str, processed: int, new_status: str = None):
        """청크가 연산될 때마다 현재 진행된 상태를 마이크로 커밋합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if new_status:
                cursor.execute('UPDATE jobs SET processed_chunks = ?, status = ? WHERE job_id = ?', 
                               (processed, new_status, job_id))
            else:
                cursor.execute('UPDATE jobs SET processed_chunks = ? WHERE job_id = ?', 
                               (processed, job_id))
            conn.commit()
        
    def get_incomplete_jobs(self) -> list:
        """
        서버가 재부팅될 때(startup), 절전모드 이전에 끝마치지 못했던(DONE, FAILED가 아닌) 작업들을 불러옵니다.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT job_id, filename, total_chunks, processed_chunks, status
                FROM jobs
                WHERE status NOT IN ('DONE', 'FAILED')
            ''')
            rows = cursor.fetchall()
            jobs = []
            for row in rows:
                jobs.append({
                    "job_id": row[0],
                    "filename": row[1],
                    "total_chunks": row[2],
                    "processed_chunks": row[3],
                    "status": row[4]
                })
            return jobs

job_queue = JobQueueManager()
