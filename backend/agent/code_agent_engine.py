from loguru import logger
from smolagents import ToolCallingAgent, OpenAIServerModel
from smolagents.agents import EMPTY_PROMPT_TEMPLATES
from backend.agent.sandbox.sandbox_tool import sandbox_tool
import asyncio
import copy

class AutodidactCodeAgent:
    """
    [Phase 3] 능동형 코드 작성 및 검증 브레인
    Smolagents의 ToolCallingAgent를 기반으로, 사용자 질의에 맞춰 스스로 파이썬 코드를 작성하고
    uv_sandbox(execute_python_code 툴)에 코드를 던져 결과를 돌려주는 '자율 주행(Autopilot)' 프로그래머입니다.
    """
    def __init__(self, ollama_host: str = "http://localhost:11434/v1"):
        logger.info("🧠 [CodeAgent] Smolagents 기반 자율 코딩 에이전트 초기화 중...")
        
        # Ollama의 OpenAI 호환 API 서버 모드를 활용하여 로컬 모델과 통신
        self.model = OpenAIServerModel(
            model_id="qwen2.5-coder:7b",
            api_base=ollama_host,
            api_key="dummy_ollama"
        )
        
        # 에이전트에게 쥐어줄 무기(도구) 모음집
        self.tools = [sandbox_tool]
        
        # smolagents 최신 API: EMPTY_PROMPT_TEMPLATES를 기본 뼈대로 사용하고 system_prompt만 커스텀
        templates = copy.deepcopy(EMPTY_PROMPT_TEMPLATES)
        templates["system_prompt"] = """너는 세계 최고의 파이썬 백엔드 개발자이자, 자동화 스크립트 작성 로봇이야.
사용자가 기능을 요청하면 생각만 하지 말고, 제공된 도구(execute_python_code)를 사용해
직접 코드를 짠 다음 샌드박스로 실행시키고, 그 결과를 확인해서 대답해라.
절대로 무한 루프 코드를 던지지 마!
출력 결과(stdout/stderr)가 보이면 그것을 근거로 사용자에게 최종 보고를 해라."""
        
        self.agent = ToolCallingAgent(
            tools=self.tools,
            model=self.model,
            prompt_templates=templates,
        )
        
    async def solve_task(self, user_prompt: str) -> str:
        """
        사용자의 코딩 요구사항을 접수하고, 에이전트가 생각->코딩->실행->검증 단계를 거쳐 해결합니다.
        (Ollama 연산 및 샌드박스 실행으로 인해 수십 초 소요 예상)
        """
        logger.info(f"✨ [CodeAgent] 사용자 미션 수령: {user_prompt[:50]}...")
        try:
            # Smolagents 내부 루프는 동기식이므로 to_thread를 사용하여 FastAPI 이벤트루프 막힘 방지
            result = await asyncio.to_thread(self.agent.run, user_prompt)
            logger.info("🎉 [CodeAgent] 미션 자율 해결 완료.")
            return str(result)
        except Exception as e:
            logger.error(f"❌ [CodeAgent] 에이전트 브레인 활동 중 치명적 오류 파손: {e}")
            return f"[System Error] 코드 에이전트 뇌(Brain) 파열: {e}"

code_agent_engine = AutodidactCodeAgent()
