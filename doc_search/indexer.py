"""문서 인덱서"""
import os
from pathlib import Path
from .scanner import FileScanner
from .database.fts5_db import FTS5Database
from .extractors import get_extractor

class DocumentIndexer:
    """문서 인덱싱 관리자"""
    
    def __init__(self, db_path: str = "doc_search.db"):
        self.db = FTS5Database(db_path)
        self.scanner = FileScanner([])
    
    def index_directory(self, directory: str, force_reindex: bool = False):
        """디렉터리 인덱싱"""
        self.scanner.root_directories = [directory]
        
        for file_path in self.scanner.scan_files():
            try:
                if not force_reindex and self.db.is_indexed(file_path) and not self.db.needs_update(file_path):
                    continue
                
                # 텍스트 추출
                extractor = get_extractor(file_path)
                if extractor:
                    content = extractor.extract_text(file_path)
                    if content and content.strip():
                        success = self.db.add_document(file_path, content)
                        if success:
                            print(f"✓ 색인 완료: {Path(file_path).name}")
                    else:
                        print(f"추출된 텍스트 없음: {file_path}")
                else:
                    print(f"지원되지 않는 파일: {file_path}")
                    
            except Exception as e:
                print(f"인덱싱 오류 ({file_path}): {e}")
    
    def index_files(self, file_paths: list, force_reindex: bool = False):
        """특정 파일들만 인덱싱"""
        for file_path in file_paths:
            try:
                if not force_reindex and self.db.is_indexed(file_path) and not self.db.needs_update(file_path):
                    continue
                
                extractor = get_extractor(file_path)
                if extractor:
                    content = extractor.extract_text(file_path)
                    if content and content.strip():
                        self.db.add_document(file_path, content)
                        print(f"✓ 색인 완료: {Path(file_path).name}")
                    else:
                        print(f"추출된 텍스트 없음: {file_path}")
                else:
                    print(f"지원되지 않는 파일: {file_path}")
                    
            except Exception as e:
                print(f"인덱싱 오류 ({file_path}): {e}")
    
    def get_stats(self):
        """인덱싱 통계"""
        return self.db.get_stats()
