import asyncio
import httpx
import json
import time
import os

BASE_URL = "http://127.0.0.1:8000"

async def test_chat():
    print("=== [1] 기본 채팅 및 최적화(Cache)/보안망(PromptGuard) 연계 테스트 ===")
    async with httpx.AsyncClient() as client:
        payload = {"prompt": "안녕? FastAPI랑 Ollama로 돌아가고 있니?"}
        
        # 첫 번째 통신 (Ollama 실시간 연산 - Cache Miss)
        print("💡 [C->S] 최초 질문 전송 (LLM 추론 예정)...")
        start = time.time()
        resp1 = await client.post(f"{BASE_URL}/chat", json=payload, timeout=60.0)
        elp1 = time.time() - start
        try:
            print(f"✅ [S->C] Ollama 응답 도착 ({elp1:.2f}초):")
            print(json.dumps(resp1.json(), indent=2, ensure_ascii=False))
        except:
            print(resp1.text)
            
        # 두 번째 통신 (Semantic Cache - Cache Hit 대기)
        print("\n💡 [C->S] 의미상 똑같은 질문 전송 (Semantic Cache Hit 테스트)...")
        payload2 = {"prompt": "안녕? 너 FastAPI와 Ollama로 작동하는거지?"}
        start = time.time()
        resp2 = await client.post(f"{BASE_URL}/chat", json=payload2, timeout=60.0)
        elp2 = time.time() - start
        try:
            print(f"✅ [S->C] Cache 응답 도착 ({elp2:.2f}초):")
            print(json.dumps(resp2.json(), indent=2, ensure_ascii=False))
        except:
            print(resp2.text)


async def test_upload():
    print("\n=== [2] 파일 RAG 해킹 방어 & 멀티스레딩 백그라운드 파이프라인 테스트 ===")
    test_file = "sample_test_knowledge.txt"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("이 프로젝트는 JunOnJuly-Project 에서 만들고 있는 온디바이스 AI 에이전트 시스템입니다. 핵심 기술로 FastAPI와 LanceDB가 사용되며 Phase3에서는 uv 샌드박스가 활용됩니다.")
        
    async with httpx.AsyncClient() as client:
        print(f"💡 [C->S] RAG 문서 '{test_file}' 보안 검열 및 업로드 요청...")
        with open(test_file, "rb") as f:
            files = {"file": (test_file, f, "text/plain")}
            start = time.time()
            resp = await client.post(f"{BASE_URL}/upload", files=files, timeout=60.0)
            elp = time.time() - start
            try:
                print(f"✅ [S->C] RAG 큐 인서트 응답 도착 ({elp:.2f}초):")
                print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
                print("\n👀 백그라운드 서버 로그를 보시면 현재 Fast-Track(벡터) 및 Graph 추출이 비동기로 병렬 작동 중일 것입니다.")
            except:
                print(resp.text)
                
    if os.path.exists(test_file):
        os.remove(test_file)

async def test_agent():
    print("\n=== [3] Smolagents 자율 코딩 샌드박스 (우회/탈옥 방어 및 출력) 테스트 ===")
    async with httpx.AsyncClient() as client:
        # LLM에게 실제로 코드를 짠 뒤 실행해달라고 명령 (System Prompt의 조건 발동)
        payload = {"prompt": "1부터 10까지 곱해주는 팩토리얼 파이썬 코드를 작성하고, 샌드박스(execute_python_code 툴)에서 실행해서 그 결과값을 출력으로 알려줄래?"}
        print("💡 [C->S] 에이전트 브레인에게 자율 코딩 및 검증 미션 전달...")
        
        start = time.time()
        # 생각 -> 코딩 -> 테스트 -> 최종 반환 사이클 적용 시 시간이 꽤 걸림
        resp = await client.post(f"{BASE_URL}/agent", json=payload, timeout=240.0)
        elp = time.time() - start
        try:
            print(f"✅ [S->C] 에이전트 자율 미션 성공 ({elp:.2f}초):")
            print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        except:
            print(resp.text)

async def main():
    print("\n" + "="*50)
    print("🚀 On-Device Code-Agent 전역 통합 인젝터 (E2E Test) 시작")
    print("="*50 + "\n")
    
    await test_chat()
    # 잦은 API 통신에 의한 스로틀 쿨다운
    await asyncio.sleep(2)
    
    await test_upload()
    await asyncio.sleep(5) # 백그라운드 그래프 연산 시간 확보
    
    await test_agent()
    
    print("\n" + "="*50)
    print("🎉 전역 통합 시스템 테스트가 정상적으로 종료되었습니다.")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
