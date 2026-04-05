"""텍스트 추출기"""
from pathlib import Path

class TextExtractor:
    """일반 텍스트 파일 추출기"""
    
    def extract_text(self, file_path: str) -> str:
        """텍스트 파일에서 내용 추출"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='cp949') as f:
                    return f.read()
            except:
                return ""
        except:
            return ""
