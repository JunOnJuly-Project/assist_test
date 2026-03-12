import asyncio
from loguru import logger

class TaskManager:
    """
    [CPU-Only 병목 방어용 전역 싱글톤 락 매니저]
    에이전트와 대화하는 동안(채팅 API 응답 중), 백그라운드의 무거운 RAG 인제스천 
    작업 작업이 CPU 연산 코어를 뺏어 시스템 프리징이 일어나지 않도록 컨트롤(Lock)합니다.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskManager, cls).__new__(cls)
            # 공유 자원(CPU 렌더링)에 대한 asyncio 락(Lock) 할당 (FastAPI 비동기 호환)
            cls._instance.cpu_lock = asyncio.Lock()
            logger.info("🔒 [TaskManager] 전역 CPU Thread-Lock 매니저가 초기화되었습니다.")
        return cls._instance
    
    async def acquire_lock_for_chat(self) -> bool:
        """
        사용자 채팅 API가 들어올 때 CPU 사용 권한(Lock)을 획득합니다.
        가장 우선순위가 높습니다.
        """
        if self.cpu_lock.locked():
            logger.debug("[TaskManager] Lock이 이미 점유되어 있습니다. 채팅 최우선 대기 중...")
            
        await self.cpu_lock.acquire()
        logger.info("🟢 [TaskManager] 채팅 세션이 CPU Lock을 획득했습니다. (RAG 굽기 임시 멉춤)")
        return True
    
    def release_lock_from_chat(self):
        """
        채팅 응답이 끝났을 때 다시 Lock을 해제하여 백그라운드 봇이 CPU를 쓸 수 있게 길을 터줍니다.
        """
        if self.cpu_lock.locked():
            self.cpu_lock.release()
            logger.info("🔴 [TaskManager] 채팅 세션이 완료되어 CPU Lock을 해제합니다. (RAG 백그라운드 재가동)")
            
    async def check_lock_for_background(self) -> bool:
        """
        (RAG 봇에서 호출) 현재 사용자가 대화 중인지(Lock이 걸렸는지) '비차단형'으로 묻습니다.
        """
        if self.cpu_lock.locked():
            logger.warning("[TaskManager] ⚠️ 유저가 대화 중입니다. 백그라운드 RAG 파싱을 대기(Sleep)합니다.")
            return False
            
        logger.debug("[TaskManager] 백그라운드 작업이 안전합니다. (Lock 미발생 상태)")
        return True

# 애플리케이션 전역에서 상태를 조율할 싱글톤 인스턴스
global_lock_manager = TaskManager()
