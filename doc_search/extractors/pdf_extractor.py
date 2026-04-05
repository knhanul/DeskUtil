"""PDF 추출기"""
import fitz

class PDFExtractor:
    """PDF 텍스트 추출기"""
    
    def extract_text(self, file_path: str) -> str:
        """PDF에서 텍스트 추출"""
        try:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text.strip()
        except:
            return ""
