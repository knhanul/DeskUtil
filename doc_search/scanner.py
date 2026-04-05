"""파일 스캐너"""
import os
from pathlib import Path
from typing import List, Generator

SUPPORTED_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml',
    '.pdf', '.docx', '.doc', '.hwp', '.hwpx', '.cell', '.xlsx', '.xls'
}

class FileScanner:
    """파일 시스템 스캐너"""
    
    def __init__(self, root_directories: List[str]):
        self.root_directories = root_directories
    
    def scan_files(self) -> Generator[str, None, None]:
        """지원되는 파일들을 재귀적으로 스캔"""
        for root_dir in self.root_directories:
            if os.path.exists(root_dir):
                for file_path in Path(root_dir).rglob('*'):
                    if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                        yield str(file_path)
    
    def get_supported_files(self, directory: str) -> List[str]:
        """특정 디렉터리에서 지원되는 파일들만 반환"""
        if not os.path.exists(directory):
            return []
        
        files = []
        for file_path in Path(directory).rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(str(file_path))
        
        return files
