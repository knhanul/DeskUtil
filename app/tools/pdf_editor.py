import os
from pathlib import Path

import pymupdf
from PyQt6.QtCore import Qt, QSize, QMimeData
from PyQt6.QtGui import QPixmap, QImage, QDragEnterEvent, QDropEvent, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QMessageBox, QFrame, QGroupBox, QSplitter,
    QTabWidget, QLineEdit, QSpinBox, QRadioButton, QScrollArea, QProgressBar,
    QButtonGroup, QAbstractItemView
)

from app.common.styles import MODERN_QSS


class PdfEditorWidget(QWidget):
    """통합 PDF 편집: 분할 / 병합 / 페이지 편집 (미리보기 후 실행)"""

    def __init__(self, parent=None, comparison_settings=None):
        super().__init__(parent)
        self.setStyleSheet(MODERN_QSS)
        self.setAcceptDrops(True)

        # Focus mode 호환
        self.lbl_name1 = QLabel()
        self.lbl_name2 = QLabel()
        self.lbl_name1.hide()
        self.lbl_name2.hide()

        self.docs = []          # list of open pymupdf.Document
        self.file_paths = []    # corresponding paths
        self.current_index = -1
        self.page_order = []    # for page editor mode (indices of current doc)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # 상단: 드롭 영역 + 파일 목록
        top = QHBoxLayout()
        drop_label = QLabel("📄 PDF를 여기로 드래그하거나 [파일 추가]를 누르세요")
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_label.setStyleSheet("border: 2px dashed #ccc; border-radius: 8px; padding: 20px; color: #666;")
        drop_label.setMinimumHeight(60)
        top.addWidget(drop_label, 1)

        btn_add = QPushButton("파일 추가")
        btn_add.setObjectName("actionBtn")
        btn_add.clicked.connect(self.add_files)
        top.addWidget(btn_add)
        root.addLayout(top)

        # 메인 영역: 왼쪽 파일/페이지 목록 | 오른쪽 작업 패널
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 왼쪽: 파일 목록 + 페이지 썸네일
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(160)
        self.file_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.file_list.currentRowChanged.connect(self.on_file_selected)
        self.file_list.model().rowsMoved.connect(self._on_file_order_changed)
        left_layout.addWidget(QLabel("불러온 PDF (드래그로 순서 변경)"))
        left_layout.addWidget(self.file_list)

        self.page_list = QListWidget()
        self.page_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.page_list.setIconSize(QSize(120, 160))
        self.page_list.setSpacing(8)
        self.page_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.page_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        left_layout.addWidget(QLabel("페이지 미리보기"))
        left_layout.addWidget(self.page_list, 1)

        splitter.addWidget(left)

        # 오른쪽: 작업 탭
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_split_tab(), "분할")
        self.tabs.addTab(self._create_merge_tab(), "병합")
        self.tabs.addTab(self._create_page_tab(), "페이지 편집")
        right_layout.addWidget(self.tabs)

        self.preview_label = QLabel("미리보기: 작업을 설정한 후 [미리보기]를 누르세요")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("background: #f8f8f8; padding: 8px; border-radius: 4px;")
        right_layout.addWidget(self.preview_label)

        btn_row = QHBoxLayout()
        self.btn_preview = QPushButton("미리보기")
        self.btn_preview.clicked.connect(self.do_preview)
        self.btn_execute = QPushButton("실행")
        self.btn_execute.setObjectName("actionBtn")
        self.btn_execute.clicked.connect(self.do_execute)
        self.btn_execute.setEnabled(False)
        btn_row.addWidget(self.btn_preview)
        btn_row.addWidget(self.btn_execute)
        right_layout.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        right_layout.addWidget(self.progress)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self._create_bottom_bar(root)

        self._planned_action = None  # ('split', params) or ('merge', ...) or ('page', ...)

    def _create_bottom_bar(self, parent_layout):
        bar = QFrame()
        bar.setObjectName("actionBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 4, 8, 4)
        self.btn_switch_tool = QPushButton()
        self.btn_switch_tool.hide()
        self.btn_focus_mode = QPushButton()
        self.btn_focus_mode.setObjectName("secondaryBtn")
        self.btn_focus_mode.setFixedSize(40, 40)
        self.btn_focus_mode.setCheckable(True)
        bl.addStretch()
        bl.addWidget(self.btn_focus_mode)
        parent_layout.addWidget(bar)
        self.bottom_action_bar = bar

    def _create_split_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.radio_range = QRadioButton("페이지 범위 (예: 1-5, 6-10)")
        self.radio_every = QRadioButton("N페이지마다")
        self.radio_each = QRadioButton("각 페이지 개별 추출")
        self.radio_range.setChecked(True)
        lay.addWidget(self.radio_range)
        self.edit_range = QLineEdit()
        self.edit_range.setPlaceholderText("1-5, 6-10, 11-")
        lay.addWidget(self.edit_range)
        lay.addWidget(self.radio_every)
        row = QHBoxLayout()
        row.addWidget(QLabel("N:"))
        self.spin_every = QSpinBox()
        self.spin_every.setRange(1, 9999)
        self.spin_every.setValue(10)
        row.addWidget(self.spin_every)
        row.addStretch()
        lay.addLayout(row)
        lay.addWidget(self.radio_each)
        lay.addStretch()
        return w

    def _create_merge_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("여러 PDF를 드래그앤드롭하거나 [파일 추가]로 불러오세요.\n왼쪽 목록의 순서대로 병합됩니다 (드래그 또는 버튼으로 순서 변경)."))
        btn_up = QPushButton("선택 파일 위로")
        btn_up.clicked.connect(self.move_file_up)
        btn_down = QPushButton("선택 파일 아래로")
        btn_down.clicked.connect(self.move_file_down)
        lay.addWidget(btn_up)
        lay.addWidget(btn_down)
        lay.addStretch()
        return w

    def _create_page_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("페이지를 선택한 뒤 아래 작업을 사용하세요.\n(변경은 미리보기 후 실행 시 반영)"))
        btn_extract = QPushButton("선택 페이지 추출 (미리보기)")
        btn_extract.clicked.connect(lambda: self._stage_page("extract"))
        btn_delete = QPushButton("선택 페이지 삭제 (미리보기)")
        btn_delete.clicked.connect(lambda: self._stage_page("delete"))
        btn_reorder = QPushButton("현재 순서로 저장 (미리보기)")
        btn_reorder.clicked.connect(lambda: self._stage_page("reorder"))
        lay.addWidget(btn_extract)
        lay.addWidget(btn_delete)
        lay.addWidget(btn_reorder)
        lay.addStretch()
        return w

    # ── Drag & Drop ────────────────────────────────────────────────────
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith(".pdf"):
                paths.append(p)
        if paths:
            self._load_files(paths)

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "PDF 선택", "", "PDF Files (*.pdf)")
        if paths:
            self._load_files(paths)

    def _load_files(self, paths):
        for path in paths:
            if path in self.file_paths:
                continue
            try:
                doc = pymupdf.open(path)
                self.docs.append(doc)
                self.file_paths.append(path)
                item = QListWidgetItem(f"{os.path.basename(path)}  ({doc.page_count}p)")
                item.setData(Qt.ItemDataRole.UserRole, path)
                self.file_list.addItem(item)
            except Exception as e:
                QMessageBox.warning(self, "오류", f"{os.path.basename(path)}\n{e}")
        if self.current_index < 0 and self.docs:
            self.file_list.setCurrentRow(0)

    def on_file_selected(self, row):
        if row < 0 or row >= len(self.docs):
            return
        self.current_index = row
        self._refresh_page_thumbnails()

    def _refresh_page_thumbnails(self):
        self.page_list.clear()
        if self.current_index < 0:
            return
        doc = self.docs[self.current_index]
        self.page_order = list(range(doc.page_count))
        for i in range(doc.page_count):
            page = doc[i]
            pix = page.get_pixmap(matrix=pymupdf.Matrix(0.4, 0.4))
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(img.copy())
            item = QListWidgetItem(QIcon(pixmap), f"p{i+1}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.page_list.addItem(item)

    def move_file_up(self):
        row = self.file_list.currentRow()
        if row > 0:
            self._swap_files(row, row - 1)

    def move_file_down(self):
        row = self.file_list.currentRow()
        if 0 <= row < self.file_list.count() - 1:
            self._swap_files(row, row + 1)

    def _on_file_order_changed(self):
        """드래그로 순서가 바뀌면 내부 리스트도 동기화"""
        new_docs = []
        new_paths = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            if path and path in self.file_paths:
                idx = self.file_paths.index(path)
                new_docs.append(self.docs[idx])
                new_paths.append(path)
        if len(new_paths) == len(self.file_paths):
            self.docs = new_docs
            self.file_paths = new_paths

    def _swap_files(self, a, b):
        self.docs[a], self.docs[b] = self.docs[b], self.docs[a]
        self.file_paths[a], self.file_paths[b] = self.file_paths[b], self.file_paths[a]
        item = self.file_list.takeItem(a)
        self.file_list.insertItem(b, item)
        self.file_list.setCurrentRow(b)

    # ── Preview / Execute ───────────────────────────────────────────────
    def do_preview(self):
        tab = self.tabs.currentIndex()
        if tab == 0:
            self._preview_split()
        elif tab == 1:
            self._preview_merge()
        else:
            # page tab uses staged action
            if self._planned_action and self._planned_action[0] == "page":
                self._preview_page()
            else:
                self.preview_label.setText("페이지 편집 탭에서 작업을 먼저 선택하세요.")

    def _preview_split(self):
        if self.current_index < 0:
            self.preview_label.setText("먼저 PDF를 불러오세요.")
            return
        doc = self.docs[self.current_index]
        total = doc.page_count
        if self.radio_range.isChecked():
            text = self.edit_range.text().strip()
            if not text:
                self.preview_label.setText("범위를 입력하세요. 예: 1-5, 6-10")
                return
            ranges = self._parse_ranges(text, total)
            self._planned_action = ("split", {"mode": "range", "ranges": ranges, "base": Path(self.file_paths[self.current_index]).stem})
            desc = ", ".join(f"{s+1}-{e}" for s, e in ranges)
            self.preview_label.setText(f"분할 미리보기: {len(ranges)}개 파일 생성\n{desc}")
        elif self.radio_every.isChecked():
            n = self.spin_every.value()
            parts = (total + n - 1) // n
            self._planned_action = ("split", {"mode": "every", "n": n, "base": Path(self.file_paths[self.current_index]).stem})
            self.preview_label.setText(f"분할 미리보기: {n}페이지마다 → {parts}개 파일")
        else:
            self._planned_action = ("split", {"mode": "each", "base": Path(self.file_paths[self.current_index]).stem})
            self.preview_label.setText(f"분할 미리보기: {total}개 개별 파일")
        self.btn_execute.setEnabled(True)

    def _preview_merge(self):
        if len(self.docs) < 2:
            self.preview_label.setText("병합하려면 PDF를 2개 이상 불러오세요.")
            return
        names = [os.path.basename(p) for p in self.file_paths]
        self._planned_action = ("merge", {"paths": list(self.file_paths)})
        self.preview_label.setText("병합 미리보기 (순서):\n" + " → ".join(names))
        self.btn_execute.setEnabled(True)

    def _stage_page(self, mode):
        if self.current_index < 0:
            QMessageBox.warning(self, "알림", "먼저 PDF를 선택하세요.")
            return
        selected = [self.page_list.item(i).data(Qt.ItemDataRole.UserRole)
                    for i in range(self.page_list.count())
                    if self.page_list.item(i).isSelected()]
        self._planned_action = ("page", {"mode": mode, "selected": selected, "order": list(self.page_order)})
        self.do_preview()

    def _preview_page(self):
        action = self._planned_action[1]
        mode = action["mode"]
        selected = action["selected"]
        if mode == "extract":
            if not selected:
                self.preview_label.setText("추출할 페이지를 선택하세요.")
                self.btn_execute.setEnabled(False)
                return
            self.preview_label.setText(f"추출 미리보기: 페이지 {', '.join(str(i+1) for i in selected)}")
        elif mode == "delete":
            if not selected:
                self.preview_label.setText("삭제할 페이지를 선택하세요.")
                self.btn_execute.setEnabled(False)
                return
            remain = [i for i in self.page_order if i not in selected]
            self.preview_label.setText(f"삭제 미리보기: {len(selected)}페이지 제거 → {len(remain)}페이지 남음")
        else:
            self.preview_label.setText(f"재정렬 미리보기: 현재 순서 {len(self.page_order)}페이지로 저장")
        self.btn_execute.setEnabled(True)

    def do_execute(self):
        if not self._planned_action:
            return
        kind = self._planned_action[0]
        try:
            if kind == "split":
                self._exec_split()
            elif kind == "merge":
                self._exec_merge()
            elif kind == "page":
                self._exec_page()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))
        finally:
            self.progress.setVisible(False)
            self.btn_execute.setEnabled(False)
            self._planned_action = None

    def _parse_ranges(self, text, total):
        ranges = []
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                start = int(a) - 1 if a else 0
                end = int(b) if b else total
                ranges.append((max(0, start), min(total, end)))
            else:
                p = int(part) - 1
                ranges.append((p, p + 1))
        return ranges

    def _exec_split(self):
        params = self._planned_action[1]
        doc = self.docs[self.current_index]
        out_dir = str(Path(self.file_paths[self.current_index]).parent)
        base = params["base"]
        total = doc.page_count
        self.progress.setVisible(True)

        if params["mode"] == "range":
            ranges = params["ranges"]
            self.progress.setMaximum(len(ranges))
            for i, (s, e) in enumerate(ranges):
                if s >= e:
                    continue
                new_doc = pymupdf.open()
                new_doc.insert_pdf(doc, from_page=s, to_page=e - 1)
                new_doc.save(str(Path(out_dir) / f"{base}_p{s+1}-{e}.pdf"))
                new_doc.close()
                self.progress.setValue(i + 1)
        elif params["mode"] == "every":
            n = params["n"]
            idx = 1
            count = (total + n - 1) // n
            self.progress.setMaximum(count)
            for start in range(0, total, n):
                end = min(start + n, total)
                new_doc = pymupdf.open()
                new_doc.insert_pdf(doc, from_page=start, to_page=end - 1)
                new_doc.save(str(Path(out_dir) / f"{base}_part{idx}.pdf"))
                new_doc.close()
                self.progress.setValue(idx)
                idx += 1
        else:
            self.progress.setMaximum(total)
            for i in range(total):
                new_doc = pymupdf.open()
                new_doc.insert_pdf(doc, from_page=i, to_page=i)
                new_doc.save(str(Path(out_dir) / f"{base}_p{i+1}.pdf"))
                new_doc.close()
                self.progress.setValue(i + 1)
        QMessageBox.information(self, "완료", "분할이 완료되었습니다.")

    def _exec_merge(self):
        save_path, _ = QFileDialog.getSaveFileName(self, "병합 파일 저장", "merged.pdf", "PDF Files (*.pdf)")
        if not save_path:
            return
        out = pymupdf.open()
        for doc in self.docs:
            out.insert_pdf(doc)
        out.save(save_path)
        out.close()
        QMessageBox.information(self, "완료", f"병합 완료:\n{save_path}")

    def _exec_page(self):
        action = self._planned_action[1]
        mode = action["mode"]
        doc = self.docs[self.current_index]
        save_path, _ = QFileDialog.getSaveFileName(self, "저장", "edited.pdf", "PDF Files (*.pdf)")
        if not save_path:
            return
        out = pymupdf.open()
        if mode == "extract":
            for idx in action["selected"]:
                out.insert_pdf(doc, from_page=idx, to_page=idx)
        elif mode == "delete":
            selected = set(action["selected"])
            for idx in self.page_order:
                if idx not in selected:
                    out.insert_pdf(doc, from_page=idx, to_page=idx)
        else:
            for idx in self.page_order:
                out.insert_pdf(doc, from_page=idx, to_page=idx)
        out.save(save_path)
        out.close()
        QMessageBox.information(self, "완료", f"저장 완료:\n{save_path}")

    def closeEvent(self, event):
        for doc in self.docs:
            try:
                doc.close()
            except Exception:
                pass
        self.docs.clear()
        super().closeEvent(event)
