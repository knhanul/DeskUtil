"""SQLite FTS5 데이터베이스 관리 - 완전 재설계"""
import sqlite3
import os
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime


class FTS5Database:
    """SQLite FTS5 전문 검색 데이터베이스"""
    
    def __init__(self, db_path: str = "doc_search.db"):
        self.db_path = db_path
        print(f"[DB] 초기화: {db_path}")
        self._init_db()
    
    def _init_db(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 문서 메타데이터 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_ext TEXT NOT NULL,
                file_size INTEGER,
                mtime TIMESTAMP,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # FTS5 가상 테이블 - 별도 관리
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_index USING fts5(
                doc_text,
                tokenize='unicode61'
            )
        ''')
        
        # 매핑 테이블: doc_id <-> fts_rowid
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS doc_fts_map (
                doc_id INTEGER PRIMARY KEY,
                fts_rowid INTEGER UNIQUE,
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        print("[DB] 테이블 초기화 완료")
    
    def add_document(self, file_path: str, content: str) -> bool:
        """문서를 데이터베이스에 추가"""
        print(f"[DB] 추가: {Path(file_path).name[:30]}")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            path = Path(file_path)
            stat = path.stat()
            
            # 기존 문서 확인
            cursor.execute('SELECT doc_id FROM documents WHERE file_path = ?', (str(file_path),))
            existing = cursor.fetchone()
            
            if existing:
                old_doc_id = existing[0]
                print(f"[DB] 기존 문서 갱신: id={old_doc_id}")
                
                # 기존 매핑 조회
                cursor.execute('SELECT fts_rowid FROM doc_fts_map WHERE doc_id = ?', (old_doc_id,))
                map_row = cursor.fetchone()
                
                if map_row:
                    fts_rowid = map_row[0]
                    # FTS5 데이터 업데이트 (삭제 후 재삽입)
                    cursor.execute('DELETE FROM fts_index WHERE rowid = ?', (fts_rowid,))
                    cursor.execute('DELETE FROM doc_fts_map WHERE doc_id = ?', (old_doc_id,))
                
                # documents 테이블 업데이트
                cursor.execute('''
                    UPDATE documents 
                    SET file_name=?, file_ext=?, file_size=?, mtime=?, indexed_at=CURRENT_TIMESTAMP
                    WHERE doc_id=?
                ''', (path.name, path.suffix.lower(), stat.st_size, 
                      datetime.fromtimestamp(stat.st_mtime), old_doc_id))
                
                doc_id = old_doc_id
            else:
                # 새 문서 삽입
                cursor.execute('''
                    INSERT INTO documents (file_path, file_name, file_ext, file_size, mtime)
                    VALUES (?, ?, ?, ?, ?)
                ''', (str(file_path), path.name, path.suffix.lower(), stat.st_size,
                      datetime.fromtimestamp(stat.st_mtime)))
                
                doc_id = cursor.lastrowid
                print(f"[DB] 새 문서: id={doc_id}")
            
            # FTS5에 텍스트 삽입 (rowid는 자동 생성)
            cursor.execute('INSERT INTO fts_index (doc_text) VALUES (?)', (content,))
            fts_rowid = cursor.lastrowid
            
            # 매핑 저장
            cursor.execute('INSERT OR REPLACE INTO doc_fts_map (doc_id, fts_rowid) VALUES (?, ?)',
                          (doc_id, fts_rowid))
            
            conn.commit()
            print(f"[DB] 완료: doc_id={doc_id}, fts_rowid={fts_rowid}, content_len={len(content)}")
            return True
            
        except Exception as e:
            print(f"[DB ERROR] 추가 실패: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def search(self, query: str, limit: int = 100) -> List[Tuple[str, str]]:
        """FTS5를 사용하여 문서 검색"""
        print(f"[SEARCH] '{query}' 검색")
        results = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # FTS 쿼리 구성
            fts_query = ' AND '.join(query.split()) if ' ' in query else query
            print(f"[SEARCH] 쿼리: '{fts_query}'")
            
            # FTS5 검색 -> 매핑 테이블 -> documents 조인
            sql = '''
                SELECT d.file_path, d.file_name 
                FROM fts_index
                JOIN doc_fts_map dfm ON fts_index.rowid = dfm.fts_rowid
                JOIN documents d ON dfm.doc_id = d.doc_id
                WHERE fts_index MATCH ?
                LIMIT ?
            '''
            
            cursor.execute(sql, (fts_query, limit))
            rows = cursor.fetchall()
            
            print(f"[SEARCH] 결과: {len(rows)}개")
            for row in rows:
                results.append((row[0], row[1]))
            
            conn.close()
            
        except Exception as e:
            print(f"[SEARCH ERROR] {e}")
            import traceback
            traceback.print_exc()
        
        return results
    
    def search_with_snippet(self, query: str, limit: int = 100) -> List[Tuple[str, str, str]]:
        """검색 결과와 함께 스니펫(요약) 반환 - two-step approach"""
        print(f"[SNIPPET] '{query}' 검색")
        results = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            fts_query = ' AND '.join(query.split()) if ' ' in query else query
            
            # Step 1: Get matching documents
            sql = '''
                SELECT d.file_path, d.file_name, fts_index.rowid
                FROM fts_index
                JOIN doc_fts_map dfm ON fts_index.rowid = dfm.fts_rowid
                JOIN documents d ON dfm.doc_id = d.doc_id
                WHERE fts_index MATCH ?
                LIMIT ?
            '''
            
            cursor.execute(sql, (fts_query, limit))
            rows = cursor.fetchall()
            
            print(f"[SNIPPET] 결과: {len(rows)}개")
            
            for row in rows:
                file_path, file_name, fts_rowid = row
                # Step 2: Get snippet for each match
                cursor.execute(
                    'SELECT snippet(fts_index, 0, \'<b>\', \'</b>\', \'...\', 32) FROM fts_index WHERE rowid = ?',
                    (fts_rowid,)
                )
                snippet_row = cursor.fetchone()
                snippet = snippet_row[0] if snippet_row else ''
                results.append((file_path, file_name, snippet))
            
            conn.close()
            
        except Exception as e:
            print(f"[SNIPPET ERROR] {e}")
            import traceback
            traceback.print_exc()
        
        return results
    
    def is_indexed(self, file_path: str) -> bool:
        """파일이 이미 인덱싱되었는지 확인"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM documents WHERE file_path = ?', (str(file_path),))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except:
            return False
    
    def needs_update(self, file_path: str) -> bool:
        """파일이 변경되어 업데이트가 필요한지 확인"""
        try:
            path = Path(file_path)
            if not path.exists():
                return False
            
            current_mtime = path.stat().st_mtime
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT mtime FROM documents WHERE file_path = ?', (str(file_path),))
            row = cursor.fetchone()
            conn.close()
            
            if row is None:
                return True
            
            db_mtime = datetime.fromisoformat(row[0]) if row[0] else None
            return db_mtime is None or current_mtime > db_mtime.timestamp()
            
        except:
            return True
    
    def remove_document(self, file_path: str) -> bool:
        """문서를 데이터베이스에서 삭제"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT doc_id FROM documents WHERE file_path = ?', (str(file_path),))
            row = cursor.fetchone()
            
            if row:
                doc_id = row[0]
                
                cursor.execute('SELECT fts_rowid FROM doc_fts_map WHERE doc_id = ?', (doc_id,))
                map_row = cursor.fetchone()
                
                if map_row:
                    fts_rowid = map_row[0]
                    cursor.execute('DELETE FROM fts_index WHERE rowid = ?', (fts_rowid,))
                    cursor.execute('DELETE FROM doc_fts_map WHERE doc_id = ?', (doc_id,))
                
                cursor.execute('DELETE FROM documents WHERE doc_id = ?', (doc_id,))
                conn.commit()
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"삭제 오류: {e}")
            return False
    
    def get_stats(self) -> dict:
        """데이터베이스 통계 반환"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM documents')
            doc_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT file_ext, COUNT(*) FROM documents GROUP BY file_ext')
            ext_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                'total_documents': doc_count,
                'by_extension': ext_counts
            }
            
        except Exception as e:
            print(f"통계 오류: {e}")
            return {}
    
    def vacuum(self):
        """데이터베이스 최적화"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('VACUUM')
            conn.close()
        except Exception as e:
            print(f"VACUUM 오류: {e}")
