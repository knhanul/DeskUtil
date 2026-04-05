"""추출기 모듈"""
from pathlib import Path
from .text_extractor import TextExtractor
from .pdf_extractor import PDFExtractor
from .docx_extractor import DOCXExtractor
from .hwp_extractor import HWPExtractor
from .cell_extractor import CellExtractor
from .xlsx_extractor import XLSXExtractor

def get_extractor(file_path: str):
    """파일 확장자에 따른 추출기 반환"""
    ext = Path(file_path).suffix.lower()
    
    extractors = {
        '.txt': TextExtractor(),
        '.md': TextExtractor(),
        '.py': TextExtractor(),
        '.js': TextExtractor(),
        '.html': TextExtractor(),
        '.css': TextExtractor(),
        '.json': TextExtractor(),
        '.xml': TextExtractor(),
        '.pdf': PDFExtractor(),
        '.docx': DOCXExtractor(),
        '.hwp': HWPExtractor(),
        '.hwpx': HWPExtractor(),
        '.cell': CellExtractor(),
        '.xlsx': XLSXExtractor(),
        '.xls': XLSXExtractor(),
    }
    
    return extractors.get(ext)

__all__ = ['get_extractor', 'TextExtractor', 'PDFExtractor', 'DOCXExtractor', 
           'HWPExtractor', 'CellExtractor', 'XLSXExtractor']
