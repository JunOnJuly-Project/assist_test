import os
import pdfplumber
from loguru import logger

class DocumentParser:
    """
    [문서 최적 추출기]
    무거운 AI 파서(Docling 등)가 CPU를 녹이는 것을 막기 위해,
    일차적으로 가벼운 정규식 기반 pdfplumber나 텍스트 리더기를 통해 Fast-Track으로 지식을 빨아들입니다.
    이후 10페이지(또는 1000자) 단위의 '청크(Chunk)'로 토막내어 배열로 반환합니다.
    """
    
    def __init__(self, chunk_size: int = 1500, overlap: int = 150):
        # 긴 문맥을 유지하되, LLM의 Context Window를 터뜨리지 않을(1.5k) 적정선
        self.chunk_size = chunk_size
        self.overlap = overlap
        
    def _chunk_text(self, text: str) -> list:
        """텍스트를 겹침(Overlap)을 주며 잘라냅니다."""
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            # 다음 청크가 끊어진 맥락을 이어받기 위해 뒤로 살짝 후퇴(overlap)
            start += (self.chunk_size - self.overlap)
            
        return chunks

    def parse_file(self, file_path: str, ext: str) -> list:
        """
        물리 경로에 있는 파일을 열어 순수 텍스트를 추출하고 토막냅니다.
        :return: ["청크 조각 1번", "청크 조각 2번", ...]
        """
        extracted_text = ""
        try:
            if ext == ".pdf":
                logger.info(f"📄 [Parser] PDF 문서를 가벼운 파서를 통해 렌더링 없이 추출합니다: {file_path}")
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            extracted_text += text + "\n"
            else:
                # 텍스트, 마크다운 등의 순수 파일
                logger.info(f"📝 [Parser] 일반 텍스트 문서 해독을 시도합니다: {file_path}")
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    extracted_text = f.read()

            # 청크 단위로 토막내어 배열화
            final_chunks = self._chunk_text(extracted_text)
            logger.info(f"✂️ [Parser] 파싱 완료: 총 {len(final_chunks)}개의 덩어리로 분해되었습니다.")
            return final_chunks
            
        except Exception as e:
            logger.error(f"[Parser] 문서 파싱 중 치명적 에러 (버손상된 파일일 가능성): {e}")
            return []

doc_parser = DocumentParser()
