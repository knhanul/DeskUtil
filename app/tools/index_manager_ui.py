from pathlib import Path
from threading import Event

try:
    from PySide6.QtCore import QThread, Signal
    from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget,
                                   QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout)
except ImportError:
    from PyQt6.QtCore import QThread, pyqtSignal as Signal
    from PyQt6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget,
                                 QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout)

from doc_search.database.fts5_db import FTS5Database
from doc_search.indexer import DocumentIndexer


class IndexWorker(QThread):
    progress = Signal(dict, str)
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, db_path, extensions, force=False, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.extensions = extensions
        self.force = force
        self._cancelled = Event()

    def cancel(self):
        self._cancelled.set()

    def run(self):
        try:
            result = DocumentIndexer(self.db_path).update_registered(
                self.extensions, force=self.force, cancelled=self._cancelled.is_set,
                progress=self.progress.emit,
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class IndexManagerDialog(QDialog):
    index_updated = Signal()

    def __init__(self, db_path, extensions, parent=None):
        super().__init__(parent)
        self.db_path = str(db_path)
        self.extensions = set(extensions)
        self.worker = None
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = FTS5Database(self.db_path)
        self.setWindowTitle('문서 색인 관리')
        self.resize(720, 600)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('색인 대상 폴더'))
        self.folders = QListWidget()
        layout.addWidget(self.folders)
        folder_actions = QHBoxLayout()
        self.add_button = self._button('폴더 추가', self.add_folder, folder_actions)
        self.remove_button = self._button('폴더 제거', self.remove_folder, folder_actions)
        layout.addLayout(folder_actions)
        self.stats_label = QLabel()
        layout.addWidget(self.stats_label)
        self.failures = QPlainTextEdit()
        self.failures.setReadOnly(True)
        self.failures.setPlaceholderText('색인 실패 파일이 없습니다.')
        layout.addWidget(self.failures)
        self.progress_label = QLabel('색인 준비')
        layout.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        actions = QHBoxLayout()
        self.update_button = self._button('변경분 업데이트', lambda: self.start_index(False), actions)
        self.rebuild_button = self._button('전체 다시 색인', self.confirm_rebuild, actions)
        self.clear_button = self._button('색인 DB 초기화', self.clear_index, actions)
        layout.addLayout(actions)
        self.cancel_button = QPushButton('작업 취소')
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_index)
        layout.addWidget(self.cancel_button)
        self.refresh()

    @staticmethod
    def _button(label, callback, row):
        button = QPushButton(label)
        button.clicked.connect(callback)
        row.addWidget(button)
        return button

    def refresh(self):
        selected = self.folders.currentItem().text() if self.folders.currentItem() else ''
        self.folders.clear()
        self.folders.addItems(self.db.list_folders())
        for index in range(self.folders.count()):
            if self.folders.item(index).text() == selected:
                self.folders.setCurrentRow(index)
        stats = self.db.index_stats()
        self.stats_label.setText(
            f"색인 폴더 {self.folders.count()}개 | 색인 문서 {stats['total']:,}개 | "
            f"정상 {stats['indexed']:,}개 | 실패 {stats['failed']:,}개 | "
            f"지원하지 않음 {stats['unsupported']:,}개\n"
            f"최근 색인 {stats['updated_at'] or '없음'} | DB 크기 {stats['db_size']:,} bytes"
        )
        self.failures.setPlainText('\n'.join(
            f"{item['file_path']}: {item['error_message']}" for item in stats['errors']
        ))

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, '색인할 폴더 선택')
        if folder:
            try:
                if not self.db.add_folder(folder):
                    QMessageBox.information(self, '색인 관리', '이미 상위 폴더가 등록되어 있습니다.')
                self.refresh()
                self.index_updated.emit()
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, '색인 관리', str(exc))

    def remove_folder(self):
        selected = self.folders.currentItem()
        if not selected:
            return
        if QMessageBox.question(self, '폴더 제거',
                                '선택한 폴더와 해당 색인 데이터를 제거합니다. 원본 파일은 삭제되지 않습니다.\n계속하시겠습니까?'
                                ) != QMessageBox.StandardButton.Yes:
            return
        self.db.remove_folder(selected.text())
        self.refresh()
        self.index_updated.emit()

    def confirm_rebuild(self):
        if QMessageBox.question(self, '전체 다시 색인',
                                '등록된 폴더의 모든 문서를 다시 추출하여 색인을 갱신합니다. 계속하시겠습니까?'
                                ) == QMessageBox.StandardButton.Yes:
            self.start_index(True)

    def clear_index(self):
        if QMessageBox.question(self, '색인 DB 초기화',
                                '검색 색인 데이터만 삭제됩니다. 원본 문서는 삭제되지 않습니다. 계속하시겠습니까?'
                                ) != QMessageBox.StandardButton.Yes:
            return
        self.db.clear_index()
        self.refresh()
        self.index_updated.emit()

    def start_index(self, force):
        if self.worker and self.worker.isRunning():
            return
        if not self.db.list_folders():
            QMessageBox.information(self, '색인 관리', '먼저 색인할 폴더를 추가해 주세요.')
            return
        self.worker = IndexWorker(self.db_path, self.extensions, force, self)
        self.worker.progress.connect(self.update_progress)
        self.worker.completed.connect(self.complete_index)
        self.worker.failed.connect(self.fail_index)
        self.worker.finished.connect(self._release_worker)
        self.progress_bar.setRange(0, 0)
        for button in (self.add_button, self.remove_button, self.update_button,
                       self.rebuild_button, self.clear_button):
            button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_label.setText('색인 준비 중...')
        self.worker.start()

    def update_progress(self, stats, path):
        if stats['total']:
            self.progress_bar.setRange(0, stats['total'])
            self.progress_bar.setValue(stats['processed'])
        self.progress_label.setText(
            f"현재 파일: {path}\n전체 {stats['total']:,} | 완료 {stats['processed']:,} | "
            f"신규 {stats['new']:,} | 변경 {stats['modified']:,} | 삭제 {stats['deleted']:,} | "
            f"실패 {stats['failed']:,}"
        )

    def complete_index(self, stats):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0 if stats['cancelled'] else 100)
        self.progress_label.setText('색인 취소됨' if stats['cancelled'] else '색인 완료')
        self._finish()

    def fail_index(self, message):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f'색인 실패: {message}')
        self._finish()

    def _finish(self):
        for button in (self.add_button, self.remove_button, self.update_button,
                       self.rebuild_button, self.clear_button):
            button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.refresh()
        self.index_updated.emit()

    def _release_worker(self):
        self.worker.deleteLater()
        self.worker = None

    def cancel_index(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_button.setEnabled(False)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            event.ignore()
            QMessageBox.information(self, '색인 관리', '현재 파일 처리 후 작업이 취소됩니다. 작업 취소를 눌러 주세요.')
            return
        super().closeEvent(event)
