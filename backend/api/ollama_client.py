import aiohttp
import json
from loguru import logger

class OllamaClient:
    """
    [Phase 1] 로컬 Ollama 데몬(LLM)과 통신하는 비동기 클라이언트.
    CPU 렌더링 환경에서의 Timeout 및 VRAM(RAM) 메모리 스왑 방어를 위해 num_predict와 num_thread 파라미터를 제어합니다.
    """
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host
        self.default_model = "qwen2.5-coder:7b"
        logger.info(f"🔌 [Ollama API] Ollama 클라이언트 세팅 완료. (타겟 LLM: {self.default_model})")

    async def generate_thought_and_action(self, prompt: str, stop_sequences: list = None) -> str:
        """
        비동기로 Ollama에 프롬프트를 보내고 텍스트 응답을 수집합니다.
        (CPU 스로틀링 대처를 위해 stream=False 우선 적용, Phase 4 스트리밍 도입 전까지 반환형 통일)
        """
        url = f"{self.host}/api/generate"
        
        # 모델명 및 발열 통제 옵션 설정
        payload = {
            "model": self.default_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                # [CPU-Only 옵션 제어]
                "num_predict": 1024,   # 한 번에 너무 많은 토큰을 뱉다가 과열방지 및 타임아웃 방어 (1K 제한)
                "temperature": 0.2,    # 코드/기능 에이전트는 창의성보다 논리적 결정이 중요
                "top_p": 0.9,
                #"num_thread": 6       # 필요시 물리 코어 수만큼 스레드 제한하여 쿨링/렌더링 양보 가능
            }
        }
        
        # SmolAgents 적용 전/후 정지 단어가 있을 경우
        if stop_sequences:
            payload["options"]["stop"] = stop_sequences

        try:
            # 랩탑 연산 속도가 느릴(OOM 회피) 경우를 대비해 넉넉한 120초 비동기 타임아웃
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
                logger.debug(f"[Ollama] LLM 스레드 가동 시작... (1024 토큰 제한)")
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"[Ollama] 에러 응답 수신: {error_text}")
                        return f"[System Error] LLM이 응답하지 않습니다: HTTP {response.status}"
                    
                    data = await response.json()
                    result_text = data.get("response", "")
                    
                    # TPS 측정 로직
                    eval_count = data.get('eval_count', 0)
                    eval_duration = data.get('eval_duration', 1) / 1e9
                    tps = eval_count / eval_duration if eval_duration > 0 else 0
                    logger.debug(f"[Ollama] 연산 완료. (생성 토큰: {eval_count}, TPS: {tps:.2f} Tokens/sec)")
                    
                    return result_text.strip()
                    
        except aiohttp.ClientError as ce:
            logger.error(f"[Ollama] 연결 오류 발생 (서버 꺼짐 확인 요망): {ce}")
            return "[System Error] LLM 연결 실패. Ollama가 백그라운드에서 실행중인지 확인하세요."
        except asyncio.TimeoutError:
            logger.error("[Ollama] 타임아웃 발생 (노트북 CPU 과부하 또는 RAM 스왑 극한 상황)")
            return "[System Error] 노트북 연산 시간이 120초를 초과하여 타임아웃 처리되었습니다."

ollama_client = OllamaClient()
