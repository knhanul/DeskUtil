"""문서 인덱서"""
import os
import logging
from pathlib import Path
from .scanner import FileScanner
from .database.fts5_db import FTS5Database
from .extractors import get_extractor

def user_database_path():
    data_dir = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'DeskUtil'
    return data_dir / 'document_search.db'


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

    def update_registered(self, extensions: set[str], force=False, cancelled=None, progress=None):
        cancelled = cancelled or (lambda: False)
        stats = {'total': 0, 'processed': 0, 'new': 0, 'modified': 0,
                 'deleted': 0, 'unchanged': 0, 'failed': 0, 'unsupported': 0,
                 'cancelled': False}
        folders = self.db.list_folders()
        scans = []
        for folder in folders:
            if cancelled():
                stats['cancelled'] = True
                return stats
            self.scanner.root_directories = [folder]
            if progress:
                progress(stats.copy(), folder)
            files, unsupported, complete = self.scanner.scan_index_files(extensions, cancelled)
            stats['unsupported'] += unsupported
            snapshot = self.db.document_snapshot(folder)
            deleted = set(snapshot) - set(files) if complete else set()
            stats['total'] += len(files) + len(deleted)
            scans.append((files, snapshot, deleted))

        for files, snapshot, deleted in scans:
            for file_path in files:
                if cancelled():
                    stats['cancelled'] = True
                    return stats
                file_stat = None
                try:
                    file_stat = os.stat(file_path)
                    previous = snapshot.get(file_path)
                    if (not force and previous and previous['status'] == 'indexed'
                            and previous['file_size'] == file_stat.st_size
                            and previous['mtime_ns'] == file_stat.st_mtime_ns):
                        stats['unchanged'] += 1
                    else:
                        extractor = get_extractor(file_path)
                        if not extractor:
                            raise ValueError('지원하지 않는 문서 형식입니다.')
                        text = extractor.extract_text(file_path)
                        if not text or not text.strip():
                            raise ValueError('본문 텍스트를 추출할 수 없습니다.')
                        self.db.upsert_indexed(file_path, text, file_stat)
                        stats['modified' if previous else 'new'] += 1
                except Exception as exc:
                    stats['failed'] += 1
                    try:
                        self.db.record_failure(file_path, file_stat, str(exc))
                    except Exception:
                        logging.getLogger(__name__).exception('Failed to store index error for %s', file_path)
                stats['processed'] += 1
                if progress:
                    progress(stats.copy(), file_path)
            if cancelled():
                stats['cancelled'] = True
                return stats
            if deleted:
                try:
                    self.db.remove_indexed(deleted)
                    stats['deleted'] += len(deleted)
                except Exception:
                    stats['failed'] += len(deleted)
                    logging.getLogger(__name__).exception('Failed to remove stale index rows')
                stats['processed'] += len(deleted)
                if progress:
                    progress(stats.copy(), '')
        self.db.save_index_run(stats['unsupported'])
        return stats
