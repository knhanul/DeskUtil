"""DOCX 추출기"""
from pathlib import Path
import docx

class DOCXExtractor:
    """DOCX 텍스트 추출기"""
    
    def extract_text(self, file_path: str) -> str:
        """DOCX에서 텍스트 추출"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except:
            return ""
