import json
import re
from loguru import logger
from backend.api.ollama_client import ollama_client
from backend.rag.database.graph_db import graph_db

class LightRAGExtractor:
    """
    [Graph Extraction 지능 모듈]
    Ollama(qwen2.5-coder)에게 문서를 던져주고 "엔터티(Entity)"와 "관계(Relation)"를 
    JSON 규격으로 강제 추출해 내는 파기(Extractor) 브레인입니다.
    """
    
    def __init__(self):
        # JSON Schema를 프롬프트에 하드코딩하여 확정된 구조화 응답을 유도 (Few-Shot)
        self.system_prompt = '''
너는 세계 최고의 코드 및 기술 문서 데이터 분석가야.
주어진 문맥(Context)을 주의 깊게 읽고, 핵심 개체(Entity)와 그들 간의 관계(Relation)를 찾아내라.
반드시 아래의 **순수 JSON 형식**으로만 대답하고, 그 외의 다른 인사말이나 설명은 절대 출력하지 마.

{
    "entities": [
        {"name": "개체명(함수/클래스/개념)", "type": "개체종류", "description": "요약 설명"}
    ],
    "relations": [
        {"source": "주체 개체명", "target": "대상 개체명", "relationship": "관계 설명(호출한다, 상속한다 등)"}
    ]
}
'''

    async def extract_graph_from_chunk(self, chunk: str, source_id: str):
        prompt = f"{self.system_prompt}\n\n[문맥]\n{chunk}\n\n[답변(오직 JSON만 출력)]:"
        
        try:
            # 1. 모델 추론 (JSON 강제)
            response_text = await ollama_client.generate_thought_and_action(prompt)
            
            # 2. JSON 파싱 (방어 로직: 모델이 실수로 마크다운 ```json ... ``` 을 붙일 경우 제거)
            clean_json = re.sub(r'```json|```', '', response_text).strip()
            
            # 최악의 경우 모델이 헛소리를 하면 여기서 DecodeError가 터집니다. (안전벨트)
            data = json.loads(clean_json)
            
            # 3. 개체와 관계를 Graph DB(SQLite)에 바로 저장
            entities = data.get("entities", [])
            relations = data.get("relations", [])
            
            for ent in entities:
                if "name" in ent and "type" in ent and "description" in ent:
                    graph_db.insert_entity(ent["name"], ent["type"], ent["description"], source_id)
            
            for rel in relations:
                if "source" in rel and "target" in rel and "relationship" in rel:
                    graph_db.insert_relation(rel["source"], rel["target"], rel["relationship"], source_id)
                    
            logger.info(f"🕸️ [GraphExtractor] 지식 마이닝 성공! {len(entities)}개의 개체와 {len(relations)}개의 관계 DB 저장 완료.")
            
        except json.JSONDecodeError:
            logger.warning(f"⚠️ [GraphExtractor] Ollama가 분석에 실패했거나 올바른 JSON을 만들지 않았습니다 (일부 데이터 폐기)")
        except Exception as e:
            logger.error(f"❌ [GraphExtractor] 그래프 추출 중 시스템 에러: {e}")

graph_extractor = LightRAGExtractor()
