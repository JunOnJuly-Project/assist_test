import sqlite3
import os
from loguru import logger

class GraphDBManager:
    """
    [LightRAG 핵심 지식 그래프 스토리지]
    로컬 환경에서 무거운 GraphDB(Neo4j 등) 대신 SQLite를 활용하여
    개체(Entity)와 관계(Relation)를 가벼운 노드와 엣지 테이블로 저장합니다.
    """
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(base_dir, "database", "knowledge_graph.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 노드 (Entities) 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS entities (
                        entity_name TEXT PRIMARY KEY,
                        entity_type TEXT,
                        description TEXT,
                        source_id TEXT
                    )
                ''')
                # 엣지 (Relations) 테이블
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS relations (
                        source_entity TEXT,
                        target_entity TEXT,
                        relationship TEXT,
                        weight INTEGER DEFAULT 1,
                        source_id TEXT,
                        UNIQUE(source_entity, target_entity, relationship)
                    )
                ''')
                conn.commit()
                logger.debug("🕸️ [GraphDB] 지식 그래프(LightRAG)용 로컬 SQLite 연동 완료.")
        except Exception as e:
            logger.error(f"[GraphDB] 초기화 실패: {e}")

    def insert_entity(self, name: str, entity_type: str, desc: str, source_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 이미 존재하는 개체면 설명을 누적(융합)하거나 업데이트
            cursor.execute('''
                INSERT INTO entities (entity_name, entity_type, description, source_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(entity_name) DO UPDATE SET
                description = description || ' | ' || excluded.description
            ''', (name, entity_type, desc, source_id))
            conn.commit()

    def insert_relation(self, source: str, target: str, rel: str, source_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 이미 같은 관계가 있다면 가중치(weight)만 증가시켜 중요도를 높입니다.
            cursor.execute('''
                INSERT INTO relations (source_entity, target_entity, relationship, weight, source_id)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(source_entity, target_entity, relationship) DO UPDATE SET
                weight = weight + 1
            ''', (source, target, rel, source_id))
            conn.commit()

graph_db = GraphDBManager()
