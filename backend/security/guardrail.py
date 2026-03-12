import os
from transformers import pipeline
from loguru import logger

class PromptGuard:
    def __init__(self):
        """
        [보안] 악의적인 프롬프트 인젝션(Jailbreak 등)을 백엔드 진입 단계에서 사전에 차단합니다.
        가중치는 로컬 'weights' 폴더에 저장되어 외부(클라우드) 의존성을 완벽히 끊어냅니다.
        """
        # 프로젝트 루트의 weights 폴더 절대 경로 탐색
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cache_dir = os.path.join(base_dir, "weights")
        os.makedirs(cache_dir, exist_ok=True)
        
        model_name = "ProtectAI/deberta-v3-base-prompt-injection-v2"
        logger.info(f"🛡️ 보안 모듈(Prompt Injection 방어막) 로드 중... ({model_name})")
        
        # 노트북 CPU 전용 통제를 위해 device=-1 지정 (GPU 사용 안함)
        try:
            self.classifier = pipeline(
                "text-classification",
                model=model_name,
                model_kwargs={"cache_dir": cache_dir},
                device=-1
            )
            logger.info("✅ 보안 모듈 로드 완료. (Red Teaming 방어 준비됨)")
        except Exception as e:
            logger.error(f"보안 모델 오프라인 적재 실패 (인터넷을 통한 최초 1회 다운로드가 필요할 수 있습니다): {e}")
            raise e

    def check_prompt(self, text: str) -> bool:
        """
        프롬프트의 악의성 여부를 판별합니다.
        :param text: 사용자가 입력한 프롬프트 또는 외부(Drive)에서 유입된 텍스트.
        :return: True(안전함), False(인젝션 의심, 즉시 차단)
        """
        try:
            # max_length 512 초과시 잘라내어 CPU 병목(OOM) 방어
            result = self.classifier(text, truncation=True, max_length=512)
            label = result[0]['label']
            score = result[0]['score']
            
            # 위험성 분류 로깅
            logger.debug(f"[Guardrail] 분석 결과: {label} (확률: {score:.4f})")
            
            # 레이블이 'INJECTION'이고 확률이 절반을 넘으면 해킹 시도로 간주
            if label == 'INJECTION' and score > 0.5:
                return False
            return True
        except Exception as e:
            logger.error(f"[Guardrail] 텍스트 보안 검사 중 에러 발생: {e}")
            # 보안 보수성 원칙(Fail-Safe)에 따라 에러 시 통과시키지 않고 철저히 차단
            return False
