"""문서 검색"""
from .database.fts5_db import FTS5Database

class DocumentSearch:
    """문서 검색 관리자"""
    
    def __init__(self, db_path: str = "doc_search.db"):
        self.db = FTS5Database(db_path)
    
    def search(self, query: str, limit: int = 100):
        """문서 검색"""
        return self.db.search(query, limit)
    
    def search_with_snippet(self, query: str, limit: int = 100):
        """스니펫 포함 검색"""
        return self.db.search_with_snippet(query, limit)
    
    def get_stats(self):
        """통계 정보"""
        return self.db.get_stats()
