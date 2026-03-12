import os
from loguru import logger
from smolagents import Tool
from backend.agent.sandbox.uv_env import uv_sandbox
import asyncio

class RunPythonSandboxTool(Tool):
    """
    [에이전트 무기]
    Smolagents 에이전트가 이 툴(도구)을 호출하여 자신이 작성한 Python 스크립트를 실제 환경에서 실행합니다.
    """
    name = "execute_python_code"
    description = "에이전트가 작성한 파이썬(.py) 코드를 실제 격리된 백엔드 로컬 환경(Sandbox)에서 컴파일 및 실행합니다. 프린트(출력)된 문자열을 통해 실행 결과를 검증받을 수 있습니다."
    
    # Smolagents 입력 규격
    inputs = {
        "code": {
            "type": "string",
            "description": "실행시킬 온전한 파이썬 소스 코드 (의존성 패키지가 필요하다면 상단에 PEP 723 블록으로 명시할 것)"
        }
    }
    
    # 툴의 반환 결과 규격
    output_type = "string"

    def forward(self, code: str) -> str:
        """
        Smolagents는 내부적으로 비동기를 지원하지 않는 동기 루프에서 툴을 부를 때가 많습니다.
        따라서 동기(Synchronous) 래핑으로 uv_sandbox의 비동기 실행기를 호출합니다.
        """
        logger.info(f"🤖 [Agent Tool] 에이전트가 {len(code)}글자의 코드를 작성하여 격리 샌드박스 실행을 요청했습니다.")
        try:
            # 기존 이벤트 루프가 있을 경우 (FastAPI와 함께 돌 경우) asyncio.run()이 꼬일 수 있으므로
            # event loop 방어용 new_loop를 씁니다.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(uv_sandbox.run_code(code))
            loop.close()
            
            logger.debug("[Agent Tool] 샌드박스의 출력 결과를 에이전트 두뇌로 반환 성공.")
            return result
            
        except Exception as e:
            return f"[Tool Error] 샌드박스 실행 엔진 에러 (의존성 패키지 설치 실패이거나 내부 버그): {e}"

sandbox_tool = RunPythonSandboxTool()
