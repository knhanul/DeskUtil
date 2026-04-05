"""
문서 실시간 검색 도구 (MDI 위젯)
폴더를 실시간으로 스캔하여 텍스트 검색
"""
import sys
import os
from pathlib import Path
from typing import Optional, Generator
import fnmatch

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QMessageBox, QProgressBar,
    QFileDialog, QSplitter, QTextEdit, QFrame, QApplication
)

# Extractors import
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from doc_search.extractors import get_extractor


class SearchWorker(QThread):
    """실시간 파일 검색 워커 스레드"""
    # Signals
    result_found = pyqtSignal(str, str, str)  # file_path, file_name, preview
    progress_updated = pyqtSignal(int, int, str)  # current, total, current_file
    search_finished = pyqtSignal(int, int)  # found_count, total_scanned
    search_error = pyqtSignal(str)
    
    def __init__(self, directory: str, query: str, recursive: bool = True):
        super().__init__()
        self.directory = directory
        self.query = query.lower()  # case-insensitive search
        self.recursive = recursive
        self._is_running = True
        self.supported_exts = {'.txt', '.pdf', '.docx', '.xlsx', '.hwp', '.cell', '.hwpx'}
    
    def stop(self):
        """검색 중지"""
        self._is_running = False
        self.wait(1000)  # Wait up to 1 second for thread to finish
    
    def run(self):
        """검색 실행 - generator pattern for real-time results"""
        try:
            found_count = 0
            scanned_count = 0
            
            # Get file list
            files = self._get_files()
            total_files = len(files)
            
            if total_files == 0:
                self.search_finished.emit(0, 0)
                return
            
            # Scan each file
            for i, file_path in enumerate(files):
                if not self._is_running:
                    break
                
                scanned_count += 1
                current_file = os.path.basename(file_path)
                
                # Emit progress
                self.progress_updated.emit(i + 1, total_files, current_file)
                
                # Check if file matches
                try:
                    if self._file_contains_query(file_path):
                        found_count += 1
                        preview = self._get_preview(file_path)
                        self.result_found.emit(
                            file_path,
                            current_file,
                            preview
                        )
                except Exception as e:
                    # Skip files that can't be read
                    pass
            
            self.search_finished.emit(found_count, scanned_count)
            
        except Exception as e:
            self.search_error.emit(str(e))
    
    def _get_files(self) -> list:
        """Get list of supported files"""
        files = []
        
        if self.recursive:
            for root, dirs, filenames in os.walk(self.directory):
                if not self._is_running:
                    break
                for filename in filenames:
                    ext = Path(filename).suffix.lower()
                    if ext in self.supported_exts or filename.endswith('.hwpx'):
                        files.append(os.path.join(root, filename))
        else:
            for filename in os.listdir(self.directory):
                filepath = os.path.join(self.directory, filename)
                if os.path.isfile(filepath):
                    ext = Path(filename).suffix.lower()
                    if ext in self.supported_exts or filename.endswith('.hwpx'):
                        files.append(filepath)
        
        return files
    
    def _file_contains_query(self, file_path: str) -> bool:
        """Check if file contains search query"""
        extractor = get_extractor(file_path)
        if not extractor:
            return False
        
        try:
            content = extractor.extract_text(file_path)
            if content and self.query in content.lower():
                return True
        except Exception:
            pass
        
        return False
    
    def _get_preview(self, file_path: str, max_length: int = 200) -> str:
        """Get text preview around search match"""
        try:
            extractor = get_extractor(file_path)
            if not extractor:
                return ""
            
            content = extractor.extract_text(file_path)
            if not content:
                return ""
            
            # Find query position and extract context
            content_lower = content.lower()
            query_pos = content_lower.find(self.query)
            
            if query_pos == -1:
                return content[:max_length].replace('\n', ' ')
            
            # Get context around match
            start = max(0, query_pos - 50)
            end = min(len(content), query_pos + len(self.query) + 100)
            preview = content[start:end]
            
            # Add ellipsis if truncated
            if start > 0:
                preview = "..." + preview
            if end < len(content):
                preview = preview + "..."
            
            # Highlight search term
            preview = preview.replace('\n', ' ')
            return preview
            
        except Exception:
            return ""


class DocumentSearchWidget(QWidget):
    """문서 검색 MDI 위젯"""
    
    tool_key = 'document_search'
    tool_name = '🔍 문서 찾기'
    window_title = '문서 통합 검색'
    singleton = False  # 여러 인스턴스 허용
    enabled = True
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_worker: Optional[SearchWorker] = None
        self.current_folder: Optional[str] = None
        self._build_ui()
    
    def _build_ui(self):
        """UI 구성"""
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(15, 15, 15, 15)
        
        # 상단: 폴더 선택, 검색어 입력, 버튼
        top_bar = QHBoxLayout()
        
        # Folder selection button
        self.btn_select_folder = QPushButton('📁 폴더 선택')
        self.btn_select_folder.setFixedHeight(36)
        self.btn_select_folder.setMinimumWidth(100)
        self.btn_select_folder.clicked.connect(self._select_folder)
        top_bar.addWidget(self.btn_select_folder)
        
        # Current folder label
        self.lbl_folder = QLabel('폴더: 미선택')
        self.lbl_folder.setStyleSheet('color: gray; padding-left: 10px;')
        top_bar.addWidget(self.lbl_folder, 1)
        
        root.addLayout(top_bar)
        
        # Search bar
        search_bar = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('검색어를 입력하세요...')
        self.search_input.setFixedHeight(36)
        self.search_input.returnPressed.connect(self._do_search)
        search_bar.addWidget(self.search_input, 1)
        
        self.btn_search = QPushButton('검색')
        self.btn_search.setFixedHeight(36)
        self.btn_search.setMinimumWidth(80)
        self.btn_search.clicked.connect(self._do_search)
        self.btn_search.setEnabled(False)
        search_bar.addWidget(self.btn_search)
        
        self.btn_cancel = QPushButton('취소')
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.setMinimumWidth(80)
        self.btn_cancel.clicked.connect(self._cancel_search)
        self.btn_cancel.setVisible(False)
        search_bar.addWidget(self.btn_cancel)
        
        root.addLayout(search_bar)
        
        # 진행 상황 표시
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        root.addWidget(self.progress_bar)
        root.addWidget(self.progress_label)
        
        # 메인 영역: 결과 목록과 미리보기
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 왼쪽: 검색 결과 목록
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.result_list = QListWidget()
        self.result_list.itemClicked.connect(self._show_preview)
        self.result_list.itemDoubleClicked.connect(self._open_file)
        left_layout.addWidget(QLabel('검색 결과:'))
        left_layout.addWidget(self.result_list)
        
        self.lbl_result_count = QLabel('0개 결과')
        left_layout.addWidget(self.lbl_result_count)
        
        splitter.addWidget(left_panel)
        
        # 오른쪽: 파일 내용 미리보기
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.preview_title = QLabel('파일을 선택하세요')
        self.preview_title.setStyleSheet('font-weight: bold; padding: 5px;')
        right_layout.addWidget(self.preview_title)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText('검색 결과에서 파일을 선택하면 내용이 표시됩니다.')
        right_layout.addWidget(self.preview_text)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])
        
        root.addWidget(splitter, 1)
        
        # 상태 표시줄
        self.status_label = QLabel('폴더를 선택하세요')
        root.addWidget(self.status_label)
    
    def _select_folder(self):
        """폴더 선택"""
        folder = QFileDialog.getExistingDirectory(self, '검색할 폴더 선택')
        if not folder:
            return
        
        self.current_folder = folder
        self.lbl_folder.setText(f'폴더: {folder}')
        self.lbl_folder.setStyleSheet('color: black; padding-left: 10px;')
        self.btn_search.setEnabled(True)
        self.status_label.setText('검색 준비 완료')
    
    def _do_search(self):
        """검색 실행"""
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, '경고', '검색어를 입력하세요.')
            return
        
        if not self.current_folder or not os.path.exists(self.current_folder):
            QMessageBox.warning(self, '경고', '검색할 폴더를 먼저 선택하세요.')
            return
        
        # Cancel any existing search
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.stop()
            self.search_worker.wait()
        
        # Reset UI
        self.result_list.clear()
        self.preview_text.clear()
        self.preview_title.setText('파일을 선택하세요')
        self.lbl_result_count.setText('0개 결과')
        
        # Show progress UI
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_search.setVisible(False)
        self.btn_cancel.setVisible(True)
        self.btn_select_folder.setEnabled(False)
        self.status_label.setText('검색 중...')
        
        # Start worker thread
        self.search_worker = SearchWorker(self.current_folder, query)
        self.search_worker.result_found.connect(self._on_result_found)
        self.search_worker.progress_updated.connect(self._on_progress_updated)
        self.search_worker.search_finished.connect(self._on_search_finished)
        self.search_worker.search_error.connect(self._on_search_error)
        self.search_worker.start()
    
    def _cancel_search(self):
        """검색 취소"""
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.stop()
            self.status_label.setText('검색 취소됨')
        
        self._reset_search_ui()
    
    def _on_result_found(self, file_path: str, file_name: str, preview: str):
        """실시간 결과 처리 - called from worker thread"""
        item = QListWidgetItem(f'{file_name}\n{file_path}')
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        item.setToolTip(preview[:200] if preview else file_path)
        self.result_list.addItem(item)
        
        # Update count
        count = self.result_list.count()
        self.lbl_result_count.setText(f'{count}개 결과')
        self.status_label.setText(f'검색 중... {count}개 발견')
    
    def _on_progress_updated(self, current: int, total: int, current_file: str):
        """진행 상황 업데이트"""
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
            self.progress_label.setText(f'{current}/{total} 파일 스캔 중...\n{current_file[:50]}')
    
    def _on_search_finished(self, found_count: int, total_scanned: int):
        """검색 완료 처리"""
        self._reset_search_ui()
        self.status_label.setText(f'검색 완료 - {found_count}개 발견 / {total_scanned}개 파일 스캔')
        
        if found_count == 0:
            QMessageBox.information(self, '검색 완료', '검색 결과가 없습니다.')
    
    def _on_search_error(self, error_msg: str):
        """검색 오류 처리"""
        self._reset_search_ui()
        QMessageBox.critical(self, '검색 오류', f'검색 중 오류 발생:\n{error_msg}')
    
    def _reset_search_ui(self):
        """검색 UI 초기화"""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.btn_search.setVisible(True)
        self.btn_cancel.setVisible(False)
        self.btn_select_folder.setEnabled(True)
    
    def _show_preview(self, item: QListWidgetItem):
        """선택된 파일 미리보기 표시"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path or not os.path.exists(file_path):
            return
        
        self.preview_title.setText(f'{os.path.basename(file_path)}')
        
        try:
            extractor = get_extractor(file_path)
            if extractor:
                content = extractor.extract_text(file_path)
                if content:
                    # Limit preview length
                    preview = content[:5000]
                    self.preview_text.setPlainText(preview)
                else:
                    self.preview_text.setPlainText('(내용 없음)')
            else:
                self.preview_text.setPlainText(
                    f'파일: {file_path}\n\n'
                    f'이 파일 형식은 미리보기를 지원하지 않습니다.\n'
                    f'더블클릭하여 외부 프로그램으로 열 수 있습니다.'
                )
        except Exception as e:
            self.preview_text.setPlainText(f'파일 읽기 오류: {e}')
    
    def _open_file(self, item: QListWidgetItem):
        """파일 외부 프로그램으로 열기"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path and os.path.exists(file_path):
            os.startfile(file_path)
    
    def closeEvent(self, event):
        """Close event handler to stop worker thread"""
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.stop()
            self.search_worker.wait(2000)
        event.accept()
