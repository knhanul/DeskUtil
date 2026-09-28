"""SQLite FTS5 데이터베이스 관리 - 완전 재설계"""
import sqlite3
import os
from contextlib import closing
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
        
        columns = {row[1] for row in cursor.execute('PRAGMA table_info(documents)')}
        for name, sql_type in (('created_at', 'REAL'), ('mtime_ns', 'INTEGER'),
                               ('status', "TEXT NOT NULL DEFAULT 'indexed'"), ('error_message', 'TEXT')):
            if name not in columns:
                cursor.execute(f'ALTER TABLE documents ADD COLUMN {name} {sql_type}')
        has_indexed_fts = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='indexed_fts'"
        ).fetchone()
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS indexed_fts USING fts5(
                file_name, doc_text, tokenize='unicode61'
            )
        ''')
        cursor.execute('CREATE TABLE IF NOT EXISTS indexed_folders (path TEXT PRIMARY KEY)')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS index_runs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                updated_at TEXT, unsupported INTEGER NOT NULL DEFAULT 0
            )
        ''')
        if not has_indexed_fts:
            cursor.execute('''
                INSERT OR IGNORE INTO indexed_fts(rowid, file_name, doc_text)
                SELECT d.doc_id, d.file_name, f.doc_text
                FROM documents d
                JOIN doc_fts_map m ON m.doc_id = d.doc_id
                JOIN fts_index f ON f.rowid = m.fts_rowid
                WHERE d.status = 'indexed'
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
            cursor.execute('DELETE FROM indexed_fts WHERE rowid = ?', (doc_id,))
            cursor.execute('INSERT INTO indexed_fts(rowid, file_name, doc_text) VALUES (?, ?, ?)',
                           (doc_id, path.name, content))
            
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
                
                cursor.execute('DELETE FROM indexed_fts WHERE rowid = ?', (doc_id,))
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

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _under(path, folder):
        path = os.path.normcase(os.path.normpath(path))
        folder = os.path.normcase(os.path.normpath(folder))
        return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)

    def list_folders(self):
        with closing(self._connect()) as conn, conn:
            return [row['path'] for row in conn.execute('SELECT path FROM indexed_folders ORDER BY path')]

    def add_folder(self, folder):
        folder = os.path.normpath(os.path.abspath(folder))
        if not os.path.isdir(folder):
            raise ValueError('폴더를 찾을 수 없습니다.')
        current = self.list_folders()
        if any(self._under(folder, registered) for registered in current):
            return False
        with closing(self._connect()) as conn, conn:
            for registered in current:
                if self._under(registered, folder):
                    conn.execute('DELETE FROM indexed_folders WHERE path = ?', (registered,))
            conn.execute('INSERT INTO indexed_folders(path) VALUES (?)', (folder,))
        return True

    def _remove_rows(self, conn, paths):
        for path in paths:
            row = conn.execute('SELECT doc_id FROM documents WHERE file_path = ?', (path,)).fetchone()
            if not row:
                continue
            doc_id = row['doc_id']
            conn.execute('DELETE FROM indexed_fts WHERE rowid = ?', (doc_id,))
            mapping = conn.execute('SELECT fts_rowid FROM doc_fts_map WHERE doc_id = ?', (doc_id,)).fetchone()
            if mapping:
                conn.execute('DELETE FROM fts_index WHERE rowid = ?', (mapping['fts_rowid'],))
                conn.execute('DELETE FROM doc_fts_map WHERE doc_id = ?', (doc_id,))
            conn.execute('DELETE FROM documents WHERE doc_id = ?', (doc_id,))

    def remove_folder(self, folder, purge=True):
        with closing(self._connect()) as conn, conn:
            conn.execute('DELETE FROM indexed_folders WHERE path = ?', (folder,))
            if purge:
                paths = [row['file_path'] for row in conn.execute('SELECT file_path FROM documents')
                         if self._under(row['file_path'], folder)]
                self._remove_rows(conn, paths)

    def document_snapshot(self, folder):
        with closing(self._connect()) as conn, conn:
            return {row['file_path']: dict(row) for row in conn.execute(
                'SELECT file_path, file_size, mtime_ns, status FROM documents'
            ) if self._under(row['file_path'], folder)}

    def upsert_indexed(self, path, content, stat):
        path = os.path.normpath(path)
        with closing(self._connect()) as conn, conn:
            conn.execute('''
                INSERT INTO documents(file_path, file_name, file_ext, file_size, mtime,
                                      mtime_ns, created_at, status, error_message, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'indexed', NULL, CURRENT_TIMESTAMP)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_name=excluded.file_name, file_ext=excluded.file_ext,
                    file_size=excluded.file_size, mtime=excluded.mtime,
                    mtime_ns=excluded.mtime_ns, created_at=excluded.created_at,
                    status='indexed', error_message=NULL, indexed_at=CURRENT_TIMESTAMP
            ''', (path, Path(path).name, Path(path).suffix.lower(), stat.st_size,
                  datetime.fromtimestamp(stat.st_mtime).isoformat(sep=' '), stat.st_mtime_ns, stat.st_ctime))
            doc_id = conn.execute('SELECT doc_id FROM documents WHERE file_path = ?', (path,)).fetchone()['doc_id']
            conn.execute('DELETE FROM indexed_fts WHERE rowid = ?', (doc_id,))
            conn.execute('INSERT INTO indexed_fts(rowid, file_name, doc_text) VALUES (?, ?, ?)',
                         (doc_id, Path(path).name, content))

    def record_failure(self, path, stat, message):
        path = os.path.normpath(path)
        with closing(self._connect()) as conn, conn:
            conn.execute('''
                INSERT INTO documents(file_path, file_name, file_ext, file_size, mtime,
                                      mtime_ns, created_at, status, error_message, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'failed', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_size=excluded.file_size, mtime=excluded.mtime,
                    mtime_ns=excluded.mtime_ns, status='failed',
                    error_message=excluded.error_message, indexed_at=CURRENT_TIMESTAMP
            ''', (path, Path(path).name, Path(path).suffix.lower(),
                  stat.st_size if stat else 0,
                  datetime.fromtimestamp(stat.st_mtime).isoformat(sep=' ') if stat else None,
                  stat.st_mtime_ns if stat else None,
                  stat.st_ctime if stat else None, message[:500]))
            doc_id = conn.execute('SELECT doc_id FROM documents WHERE file_path = ?', (path,)).fetchone()['doc_id']
            conn.execute('DELETE FROM indexed_fts WHERE rowid = ?', (doc_id,))

    def remove_indexed(self, paths):
        with closing(self._connect()) as conn, conn:
            self._remove_rows(conn, paths)

    def save_index_run(self, unsupported):
        with closing(self._connect()) as conn, conn:
            conn.execute('''
                INSERT INTO index_runs(id, updated_at, unsupported) VALUES (1, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at=CURRENT_TIMESTAMP,
                                               unsupported=excluded.unsupported
            ''', (unsupported,))

    def index_stats(self):
        with closing(self._connect()) as conn, conn:
            counts = {row['status']: row['count'] for row in conn.execute(
                'SELECT status, COUNT(*) AS count FROM documents GROUP BY status'
            )}
            run = conn.execute('SELECT updated_at, unsupported FROM index_runs WHERE id = 1').fetchone()
            errors = [dict(row) for row in conn.execute('''
                SELECT file_path, error_message FROM documents WHERE status = 'failed'
                ORDER BY indexed_at DESC LIMIT 100
            ''')]
        return {
            'total': sum(counts.values()), 'indexed': counts.get('indexed', 0),
            'failed': counts.get('failed', 0), 'unsupported': run['unsupported'] if run else 0,
            'updated_at': run['updated_at'] if run else None,
            'db_size': Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0,
            'errors': errors,
        }

    def clear_index(self):
        with closing(self._connect()) as conn, conn:
            conn.execute('DELETE FROM indexed_fts')
            conn.execute('DELETE FROM doc_fts_map')
            conn.execute('DELETE FROM fts_index')
            conn.execute('DELETE FROM documents')
            conn.execute('DELETE FROM index_runs')

    def search_indexed(self, query, extensions, folders, search_content=True, search_filename=True,
                       sort='relevance', limit=1000):
        query = query.strip()
        if not query or not folders or not (search_content or search_filename) or not extensions:
            return []
        phrase = '"' + query.replace('"', '""') + '"'
        expression = phrase if search_content and search_filename else (
            ('doc_text:' if search_content else 'file_name:') + phrase
        )
        escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        clauses = []
        parameters = [expression, int(search_filename), int(search_filename), f'%{escaped}%']
        for folder in folders:
            prefix = folder.rstrip(os.sep) + os.sep
            escaped_folder = prefix.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            clauses.append("(d.file_path = ? OR d.file_path LIKE ? ESCAPE '\\')")
            parameters.extend((folder, escaped_folder + '%'))
        placeholders = ','.join('?' for _ in extensions)
        parameters.extend(sorted(extensions))
        order = {
            'modified': 'd.mtime_ns DESC', 'filename': 'd.file_name COLLATE NOCASE',
            'filekind': 'd.file_ext, d.file_name COLLATE NOCASE',
        }.get(sort, 'COALESCE(h.rank, 0) ASC, d.file_name COLLATE NOCASE')
        sql = f'''
            WITH h AS (
                SELECT rowid, bm25(indexed_fts, 3.0, 1.0) AS rank,
                       snippet(indexed_fts, 1, '', '', '...', 24) AS snippet
                FROM indexed_fts WHERE indexed_fts MATCH ?
            )
            SELECT d.file_path, d.file_name, d.file_ext, d.file_size, d.created_at,
                   d.mtime_ns, COALESCE(h.snippet, '') AS snippet
            FROM documents d LEFT JOIN h ON h.rowid = d.doc_id
            WHERE (d.status = 'indexed' OR (? = 1 AND d.status = 'failed'))
              AND (h.rowid IS NOT NULL OR (? = 1 AND d.file_name LIKE ? ESCAPE '\\'))
              AND ({' OR '.join(clauses)}) AND d.file_ext IN ({placeholders})
            ORDER BY {order} LIMIT ?
        '''
        parameters.append(limit)
        with closing(self._connect()) as conn, conn:
            return [dict(row) for row in conn.execute(sql, parameters)]
