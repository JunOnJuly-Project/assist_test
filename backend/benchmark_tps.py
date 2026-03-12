import urllib.request
import json
import time
import sys

def check_ollama_status():
    """Ollama 데몬이 실행 중인지 확인합니다."""
    url = "http://localhost:11434/"
    try:
        response = urllib.request.urlopen(url, timeout=3)
        if response.status == 200:
            return True
    except Exception:
        pass
    return False

def pull_model(model_name):
    """지정된 모델을 백그라운드에서 다운로드(Pull) 요청합니다."""
    print(f"[PM/Backend] '{model_name}' 모델을 확인 및 준비 중입니다. 최초 다운로드 시 시간이 오래 걸릴 수 있습니다...")
    url = "http://localhost:11434/api/pull"
    data = {"name": model_name}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), method='POST')
    try:
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        print(f"[Error] 모델 모델 Pull 실패: {e}")
        return False

def run_tps_benchmark(model_name="qwen2.5-coder:7b", prompt="Explain the theory of relativity in 10 sentences."):
    """LLM의 초당 토큰 생성 속도(TPS)를 벤치마크합니다."""
    print(f"\n🚀 [Phase 1: TPS Benchmark] 모델: {model_name} | 프롬프트 전송 중...")
    
    url = "http://localhost:11434/api/generate"
    data = {
        "model": model_name,
        "prompt": prompt,
        "stream": False # 정확한 속도 측정을 위해 한 번에 받습니다.
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), method='POST')
    
    start_time = time.time()
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        end_time = time.time()
        
        total_duration = end_time - start_time
        eval_count = result.get('eval_count', 0) # 생성된 토큰 수
        eval_duration = result.get('eval_duration', 1) / 1e9 # 나노초 -> 초 변환
        
        tps = eval_count / eval_duration if eval_duration > 0 else 0
        
        print("\n" + "="*50)
        print("✅ [벤치마크 테스트 결과]")
        print(f"⏱️ 총 소요 시간: {total_duration:.2f} 초")
        print(f"📝 생성된 토큰 수: {eval_count} 토큰")
        print(f"⚡ 토큰 생성 속도 (TPS): {tps:.2f} Tokens/sec")
        print("="*50)
        
        if tps >= 5.0:
            print("\n🎉 [PM 판정: 통과 (Go!)] 5 TPS 이상 달성. 현재 모델을 그대로 주력으로 사용합니다.")
        else:
            print("\n⚠️ [PM 판정: 불합격 (No-Go!)] 5 TPS 미달. CPU 스로틀링이나 RAM 스왑이 심각합니다.")
            print("👉 [조치 권고] 모델 스펙을 'phi3.5' 혹은 극소형 모델로 강등하는 것을 강력히 권고합니다.")
            
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"\n❌ 모델 '{model_name}'을/를 찾을 수 없습니다. (Ollama에 설치되지 않음)")
            print(f"터미널에서 'ollama run {model_name}' 명령어를 실행하여 설치해주세요.")
        else:
            print(f"\n❌ HTTP 에러: {e}")
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")

if __name__ == "__main__":
    target_model = "qwen2.5-coder:7b"
    
    if not check_ollama_status():
        print("❌ [장애 발생] Ollama 백그라운드 서버가 응답하지 않습니다.")
        print("먼저 Windows (또는 WSL) 터미널을 열고 'ollama serve' 또는 최상단 Ollama 아이콘을 실행해 주십시오.")
        sys.exit(1)
        
    # 모델 Pull 시도는 동기/비동기 문제가 있을 수 있으므로 생략하고 바로 벤치마크 호출로 돌파
    run_tps_benchmark(target_model)
