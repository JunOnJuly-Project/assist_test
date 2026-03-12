import os
import filetype
from fastapi import UploadFile, HTTPException
from loguru import logger

class FileValidator:
    """
    [해킹 방어망] 파일 시그니처 샌드박스
    확장자 위변조(예: 바이러스.bat -> 바이러스.pdf) 공격을 원천 차단하기 위해 
    바이너리 헤더(Magic Number)를 확인하고, 특정 텍스트(.log)는 인메모리 디코딩으로 무해함을 증명합니다.
    """
    
    # 허용할 안전한 MIME 타입 목록
    ALLOWED_MIMES = [
        "application/pdf",          # PDF 문서
        "text/plain",               # TXT 파일
        "text/csv",                 # CSV 데이터
        "application/zip",          # Docling/LightRAG 파싱을 위한 압축 해제용
        "application/epub+zip"      # 전자책
    ]
    
    # 허용할 폴백(Fallback) 순수 텍스트 확장자 (파일타입 패키지가 놓칠 수 있는 것들)
    ALLOWED_TEXT_EXTENSIONS = [".log", ".md", ".json", ".xml", ".html", ".conf"]

    @classmethod
    async def validate_file(cls, file: UploadFile) -> bool:
        """
        FastAPI 라우터단에서 문서를 읽기 전 즉각 검문합니다.
        """
        try:
            # 1. 시그니처 판별을 위해 앞 2048 바이트만 미리 읽기 (메모리 절약)
            header_bytes = await file.read(2048)
            await file.seek(0) # 커서 원상복구
            
            # 2. 파일 확장자와 이름 확보
            filename = file.filename.lower()
            _, ext = os.path.splitext(filename)
            
            # 3. 바이너리 시그니처 검사 (filetype 라이브러리)
            kind = filetype.guess(header_bytes)
            
            if kind is not None:
                # 파일 구조가 명확히 판별된 경우 (PDF 등)
                if kind.mime in cls.ALLOWED_MIMES:
                    logger.info(f"✅ [시그니처 합격] 안전한 파일 구조 확인: {filename} ({kind.mime})")
                    return True
                else:
                    logger.warning(f"🚨 [시그니처 차단] 금지된 파일 형식 감지: {filename} (실제 MIME: {kind.mime})")
                    return False
            
            # 4. 판별 불가 파일의 인메모리 텍스트 디코딩 샌드박스 검증 (Fallback)
            # 로그(.log), 마크다운(.md) 같은 순수 텍스트 파일은 Magic Number가 없어 kind가 None으로 나옴
            if ext in cls.ALLOWED_TEXT_EXTENSIONS:
                logger.debug(f"[시그니처 검사] 순수 텍스트 파일 우회 검증 시도: {filename}")
                try:
                    # UTF-8로 정상 텍스트인지 해독 시도 (멀티바이트 깨짐 무시)
                    header_bytes.decode('utf-8', errors='ignore')
                    logger.info(f"✅ [디코딩 합격] 무해한 텍스트 파일로 입증됨: {filename}")
                    return True
                except UnicodeDecodeError:
                    # 깨진 문자나 바이너리 덩어리(악성 exe, bat)가 들어있는 경우 차단
                    logger.error(f"🚨 [디코딩 차단] 텍스트 파일 위장 악성 바이너리 감지: {filename}")
                    return False
                    
            logger.warning(f"⚠️ [시그니처 미상] 허용되지 않은 파일 형식: {filename}")
            return False
            
        except Exception as e:
            logger.error(f"[FileValidator] 파일 검증 중 시스템 에러 발생: {e}")
            return False

file_validator = FileValidator()
