import os
from pathlib import Path

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox, QProgressBar, QPushButton, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from pdf_generator import ConverterManager, ConversionError, SUPPORTED_EXTENSIONS
from pdf_generator.converters import LibreOfficeConverter


class ConversionWorker(QThread):
    status = pyqtSignal(int, str, str, str)

    def __init__(self, jobs, output_dir, parent=None):
        super().__init__(parent)
        self.jobs = jobs
        self.output_dir = output_dir
        self.cancelled = False

    def run(self):
        import pythoncom
        pythoncom.CoInitialize()
        try:
            manager = ConverterManager()
            for row, source in self.jobs:
                if self.cancelled:
                    self.status.emit(row, '취소', '', '')
                    continue
                self.status.emit(row, '변환 중', '', '')
                try:
                    result = manager.convert_to_pdf(source, self.output_dir)
                    self.status.emit(row, '완료', str(result), '')
                except ConversionError as exc:
                    self.status.emit(row, '실패', '', str(exc))
                except Exception:
                    self.status.emit(row, '실패', '', 'PDF 생성에 실패했습니다. 로그를 확인해 주세요.')
        finally:
            pythoncom.CoUninitialize()


class DropArea(QLabel):
    files_dropped = pyqtSignal(list)

    def __init__(self):
        super().__init__('파일을 이곳에 끌어다 놓으세요\nHWP · HWPX · DOCX · XLSX · PPTX · 이미지 등')
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(95)
        self.setObjectName('cardFrame')
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.files_dropped.emit([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()


class PdfGeneratorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.errors = {}
        self.outputs = {}
        self.output_dir = Path.home() / 'Documents' / 'ConvertedPDF'
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        title = QLabel('PDF 생성')
        title.setObjectName('headerTitle')
        layout.addWidget(title)
        layout.addWidget(QLabel('문서를 원본 프로그램의 PDF 내보내기로 변환합니다. 원본 파일은 변경하지 않습니다.'))

        actions = QHBoxLayout()
        self.add_button = self._button('파일 추가', self.choose_files, actions)
        self.remove_button = self._button('선택 삭제', self.remove_selected, actions)
        self.clear_button = self._button('전체 삭제', self.clear_files, actions)
        self._button('변환 환경', self.show_environment, actions)
        actions.addStretch()
        layout.addLayout(actions)
        self.drop_area = DropArea()
        self.drop_area.files_dropped.connect(self.add_files)
        layout.addWidget(self.drop_area)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['파일명', '형식', '상태', '결과'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        folder = QHBoxLayout()
        folder.addWidget(QLabel('출력 위치'))
        self.folder_edit = QLineEdit(str(self.output_dir))
        folder.addWidget(self.folder_edit, 1)
        self.change_button = self._button('변경', self.choose_folder, folder)
        self.open_folder_button = self._button('출력 폴더 열기', self.open_folder, folder)
        layout.addLayout(folder)
        bottom = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        bottom.addWidget(self.progress, 1)
        self.start_button = self._button('PDF 생성 시작', self.start_conversion, bottom)
        self.cancel_button = self._button('작업 취소', self.cancel_conversion, bottom)
        self.cancel_button.setEnabled(False)
        layout.addLayout(bottom)

    @staticmethod
    def _button(label, callback, layout):
        button = QPushButton(label)
        button.setObjectName('actionBtn')
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_files([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, '변환할 파일 선택', '', '모든 파일 (*)')
        self.add_files(paths)

    def add_files(self, paths):
        if self.is_running():
            return
        existing = {self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                    for row in range(self.table.rowCount())}
        rejected = []
        for path in paths:
            source = Path(path)
            if not source.is_file():
                rejected.append(f'{source.name}: 파일을 찾을 수 없습니다.')
                continue
            if source.suffix.lower() == '.pdf':
                rejected.append(f'{source.name}: 이미 PDF 형식의 파일입니다.')
                continue
            if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
                rejected.append(f'{source.name}: 지원하지 않는 파일 형식입니다.')
                continue
            canonical = str(source.resolve())
            if canonical in existing:
                continue
            existing.add(canonical)
            row = self.table.rowCount()
            self.table.insertRow(row)
            item = QTableWidgetItem(source.name)
            item.setData(Qt.ItemDataRole.UserRole, canonical)
            item.setToolTip(canonical)
            self.table.setItem(row, 0, item)
            self.table.setItem(row, 1, QTableWidgetItem(source.suffix[1:].upper()))
            self.table.setItem(row, 2, QTableWidgetItem('대기'))
            self.table.setItem(row, 3, QTableWidgetItem(''))
        if rejected:
            QMessageBox.information(self, '파일 추가 안내', '\n'.join(rejected[:10]))

    def remove_selected(self):
        if self.is_running():
            return
        for row in sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)
        self.errors.clear()
        self.outputs.clear()

    def clear_files(self):
        if not self.is_running():
            self.table.setRowCount(0)
            self.errors.clear()
            self.outputs.clear()

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, '출력 폴더 선택', self.folder_edit.text())
        if path:
            self.folder_edit.setText(path)

    def open_folder(self):
        path = Path(self.folder_edit.text()).expanduser()
        if path.is_dir():
            os.startfile(path)
        else:
            QMessageBox.information(self, '출력 폴더', '출력 폴더가 아직 존재하지 않습니다.')

    def show_environment(self):
        try:
            import winreg
            def available(prog_id):
                try:
                    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id + r'\CLSID'):
                        return '등록됨'
                except OSError:
                    return '설치 확인 필요'
        except ImportError:
            def available(prog_id):
                return 'Windows에서 확인 가능'
        engines = [('한컴오피스 한글', 'HWPFrame.HwpObject'),
                   ('Microsoft Word', 'Word.Application'),
                   ('Microsoft Excel', 'Excel.Application'),
                   ('Microsoft PowerPoint', 'PowerPoint.Application')]
        lines = [f'{label}: {available(prog_id)}' for label, prog_id in engines]
        lines.append('LibreOffice: ' + ('사용 가능' if LibreOfficeConverter.executable() else '설치되지 않음'))
        QMessageBox.information(self, 'PDF 생성 환경', '\n'.join(lines))

    def is_running(self):
        return self.worker is not None and self.worker.isRunning()

    def start_conversion(self):
        if self.is_running():
            return
        jobs = [(row, self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
                for row in range(self.table.rowCount())
                if self.table.item(row, 2).text() != '완료']
        if not jobs:
            QMessageBox.information(self, 'PDF 생성', '변환할 파일을 추가해 주세요.')
            return
        output = Path(self.folder_edit.text()).expanduser()
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError:
            QMessageBox.warning(self, 'PDF 생성', '출력 폴더를 만들 수 없습니다. 위치와 권한을 확인해 주세요.')
            return
        self.worker = ConversionWorker(jobs, str(output), self)
        self.worker.status.connect(self.update_status)
        self.worker.finished.connect(self.conversion_finished)
        self.progress.show()
        for button in (self.add_button, self.remove_button, self.clear_button, self.start_button,
                       self.change_button, self.open_folder_button):
            button.setEnabled(False)
        self.folder_edit.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.worker.start()

    def update_status(self, row, state, output, error):
        self.table.item(row, 2).setText(state)
        self.table.removeCellWidget(row, 3)
        self.table.item(row, 3).setText('')
        if output:
            self.outputs[row] = output
            buttons = QWidget()
            layout = QHBoxLayout(buttons)
            layout.setContentsMargins(0, 0, 0, 0)
            self._button('PDF 열기', lambda checked=False, p=output: os.startfile(p), layout)
            self._button('저장 위치', lambda checked=False, p=output: os.startfile(str(Path(p).parent)), layout)
            self.table.setCellWidget(row, 3, buttons)
        elif error:
            self.errors[row] = error
            self.table.setItem(row, 3, QTableWidgetItem(error))
            self.table.item(row, 3).setToolTip(error)

    def cancel_conversion(self):
        if self.is_running():
            self.worker.cancelled = True
            self.cancel_button.setEnabled(False)

    def conversion_finished(self):
        self.progress.hide()
        for button in (self.add_button, self.remove_button, self.clear_button, self.start_button,
                       self.change_button, self.open_folder_button):
            button.setEnabled(True)
        self.folder_edit.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.worker.deleteLater()
        self.worker = None

    def closeEvent(self, event):
        if self.is_running():
            event.ignore()
            return
        super().closeEvent(event)
