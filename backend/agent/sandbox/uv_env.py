import os
import uuid
import sys
import subprocess
import shutil
from loguru import logger

class SandboxError(Exception):
    pass

class UvSandbox:
    """
    [Phase 3] 파이썬 코드 실행용 uv 기반 로컬 격리 샌드박스
    에이전트(LLM)가 작성한 코드를 시스템에 손상을 주지 않도록 임시 폴더(Sandbox)에서 실행합니다.
    uv의 PEP 723 인라인 메타데이터 지원을 활용하면 에이전트가 패키지를 알아서 요청하고 격리 설치 후 실행 가능합니다.
    """
    def __init__(self, timeout_sec: int = 20):
        # 샌드박스의 타임아웃(기본 20초) (무한 루프 등 악성/버그 코드 강제 종료 목적)
        self.timeout_sec = timeout_sec
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.sandbox_root = os.path.join(base_dir, "temp", "sandbox")
        os.makedirs(self.sandbox_root, exist_ok=True)

    def run_code(self, source_code: str) -> str:
        """
        주어진 Python 소스 코드를 파일로 저장한 뒤 격리된 프로세스로 동기 실행합니다.
        (FastAPI의 하위 쓰레드에서 윈도우 ProactorEventLoop 충돌을 막기 위한 동기 subprocess 기반 설계)
        
        :param source_code: 실행할 Python 문자열 코드
        :return: 코드가 실행된 후 출력된 stdout 및 stderr 텍스트
        """
        # 고유 격리 공간(UID) 부여
        session_id = uuid.uuid4().hex
        session_dir = os.path.join(self.sandbox_root, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        script_path = os.path.join(session_dir, "agent_script.py")
        
        try:
            # 1. 스크립트 파일 작성 (윈도우 호환성 보장)
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(source_code)
                
            logger.debug(f"🧪 [Sandbox] 격리 폴더 생성 및 스크립트 준비 완료 (Session: {session_id[:8]})")
            
            # 2. uv run 명령어로 서브프로세스 파생
            # uv run은 스크립트에 선언된 의존성만 임시로 설치하여 글로벌 환경 오염을 차단함 (PEP 723 기반)
            try:
                # 윈도우 스레드 충돌 및 좀비 프로세스 완벽 방어형 동기 subprocess 호출
                process = subprocess.run(
                    ["uv", "run", "agent_script.py"],
                    cwd=session_dir,
                    capture_output=True,
                    text=True,       # 자동 UTF-8 디코딩
                    timeout=self.timeout_sec
                )
                
                # 3. 결과 출력 처리 (표준 출력 + 표준 에러 합산)
                output = ""
                if process.stdout:
                    output += process.stdout
                if process.stderr:
                    err_text = process.stderr
                    if err_text.strip():
                        output += f"\n[stderr]\n{err_text}"
                
                # 콘솔에 아무것도 출력하지 않았을 경우
                if not output.strip():
                    output = "실행이 완료되었으나, 출력(stdout) 결과가 없습니다. (print문을 사용했는지 확인하세요)"
                    
                logger.info(f"🟢 [Sandbox] 코드 실행 완료 (Exit Code: {process.returncode})")
                return output.strip()
                
            except subprocess.TimeoutExpired:
                # 무한 루프 등 타임아웃 발생 시 즉각 자식 프로세스 학살 (Kill)
                logger.warning(f"⚠️ [Sandbox] 코드 실행이 {self.timeout_sec}초를 초과하여 강제 종료되었습니다.")
                return f"[Timeout Error] 스크립트 실행이 {self.timeout_sec}초 타임아웃 제한을 초과하여 샌드박스에서 강제 종료되었습니다."

        except Exception as e:
            logger.error(f"❌ [Sandbox] 서브프로세스 샌드박스 크래시 발생: {e}")
            raise SandboxError(f"샌드박스 내부 시스템 에러 발생: {e}")
            
        finally:
            # [방어막] 코드 실행이 끝난 후, 생성되었던 일회용 격리 폴더를 영구 파기(우회 찌꺼기 방지)
            try:
                if os.path.exists(session_dir):
                    shutil.rmtree(session_dir)
                    logger.debug(f"🧹 [Sandbox] 격리 폴더를 성공적으로 파기했습니다. (Session: {session_id[:8]})")
            except Exception as e:
                logger.warning(f"🧹 [Sandbox] 격리 폴더 삭제 실패. 수동 폐기가 필요합니다: {e}")

uv_sandbox = UvSandbox()
