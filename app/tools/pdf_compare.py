import os
import re
import unicodedata
from difflib import SequenceMatcher

import fitz
from PyQt6.QtCore import QEasingCurve, QPoint, QParallelAnimationGroup, QPropertyAnimation, QRect, QTimer, Qt, QMimeData
from PyQt6.QtGui import QColor, QFont, QImage, QMovie, QPainter, QPen, QPixmap, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QFrame, QGraphicsOpacityEffect, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget

from app.common.resources import get_resource_path, get_timer_gif_path
from app.common.styles import COLOR_WORKSPACE_DARK, COLOR_P1, COLOR_P2, COLOR_AREA, MODERN_QSS
from app.common.pdf_search_helper import PDFSearchHelper
from app.common.pdf_compare_worker import CompareThreadManager


class ViewComparisonTextDialog(QDialog):
    def __init__(self, s1_norm, s2_norm, s1_raw, s2_raw, parent=None):
        super().__init__(parent)
        self.setWindowTitle('추출 데이터 정밀 확인')
        self.resize(1050, 850)
        self.setStyleSheet(MODERN_QSS)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        def create_box_section(title, content_html, copy_data):
            container = QFrame()
            container.setObjectName('cardFrame')
            layout = QVBoxLayout(container)
            layout.setContentsMargins(15, 15, 15, 15)
            header = QHBoxLayout()
            title_lbl = QLabel(f"<b style='font-size:14px; color:#004b93;'>{title}</b>")
            header.addWidget(title_lbl)
            header.addStretch()
            btn = QPushButton('📋 텍스트 복사')
            btn.setObjectName('actionBtn')
            btn.setFixedWidth(130)
            btn.clicked.connect(lambda: self.copy_to_clip(copy_data))
            header.addWidget(btn)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setFont(QFont('Consolas', 10))
            text_edit.setHtml(content_html)
            text_edit.setStyleSheet('border: none; background: #F8F9FA;')
            layout.addLayout(header)
            layout.addWidget(text_edit)
            return container

        norm_html = (
            f"<div style='display:flex; justify-content:space-between;'>"
            f"<div style='flex:1; margin-right:10px;'><b>📄 PDF 1 (Normalized)</b><br><div style='background:#ffffff; border:1px solid #ddd; padding:10px; border-radius:4px;'>{s1_norm}</div></div><br>"
            f"<div style='flex:1;'><b>📄 PDF 2 (Normalized)</b><br><div style='background:#ffffff; border:1px solid #ddd; padding:10px; border-radius:4px;'>{s2_norm}</div></div></div>"
        )
        norm_copy = f"--- [PDF 1 Normalized] ---\n{s1_norm}\n\n--- [PDF 2 Normalized] ---\n{s2_norm}"
        main_layout.addWidget(create_box_section('[1] 정규화 텍스트 (실제 비교 대상)', norm_html, norm_copy), 1)

        raw_html = (
            f"<b>📄 PDF 1 (Raw)</b><br><div style='background:#ffffff; border:1px solid #ddd; padding:10px; border-radius:4px;'>{s1_raw.replace(chr(10), '<br>')}</div><br>"
            f"<b>📄 PDF 2 (Raw)</b><br><div style='background:#ffffff; border:1px solid #ddd; padding:10px; border-radius:4px;'>{s2_raw.replace(chr(10), '<br>')}</div>"
        )
        raw_copy = f"--- [PDF 1 Raw] ---\n{s1_raw}\n\n--- [PDF 2 Raw] ---\n{s2_raw}"
        main_layout.addWidget(create_box_section('[2] 원문 데이터 (띄어쓰기 및 줄바꿈 포함)', raw_html, raw_copy), 1)

        close_btn = QPushButton('닫기')
        close_btn.setFixedSize(120, 36)
        close_btn.clicked.connect(self.accept)
        main_layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignCenter)

    def copy_to_clip(self, text):
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, '성공', '텍스트가 클립보드에 복사되었습니다.')


class SelectableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selection_start = None
        self.selection_end = None
        self.is_selecting = False
        self.page_num = -1
        self.setStyleSheet('border: 0.5px solid #C6C6C8; background-color: white; border-radius: 4px;')
        self.setMargin(0)

    def _image_rect(self):
        pix = self.pixmap()
        if not pix:
            return QRect()
        contents = self.contentsRect()
        x = contents.x() + max(0, (contents.width() - pix.width()) // 2)
        y = contents.y() + max(0, (contents.height() - pix.height()) // 2)
        return QRect(x, y, pix.width(), pix.height())

    def _clamp_to_image(self, point):
        image_rect = self._image_rect()
        if image_rect.isNull():
            return point
        x = min(max(point.x(), image_rect.left()), image_rect.right())
        y = min(max(point.y(), image_rect.top()), image_rect.bottom())
        return QPoint(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selection_start = self._clamp_to_image(event.pos())
            self.selection_end = self.selection_start
            self.is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.selection_end = self._clamp_to_image(event.pos())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            image_rect = self._image_rect()
            selection_rect = QRect(self.selection_start, self.selection_end).normalized().intersected(image_rect)
            parent = self.parent()
            while parent and not isinstance(parent, PDFViewer):
                parent = parent.parent()
            if parent:
                local_rect = selection_rect.translated(-image_rect.topLeft())
                parent.on_selection_complete(self.page_num, local_rect)
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selection_start and self.selection_end:
            painter = QPainter(self)
            painter.setBrush(QColor(0, 120, 255, 60))
            painter.setPen(QPen(QColor(0, 0, 255), 2, Qt.PenStyle.DashLine))
            painter.drawRect(QRect(self.selection_start, self.selection_end).normalized())
            painter.end()

    def clear_selection(self):
        self.selection_start = None
        self.selection_end = None
        self.update()


class PDFViewer(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('pdfViewerArea')
        self.setWidgetResizable(True)
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        # Initialize scale before creating toolbar
        self.scale = 1.5
        
        # Toolbar
        self.toolbar = QFrame()
        self.toolbar.setObjectName('pdfToolbar')
        self.toolbar.setFixedHeight(40)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        toolbar_layout.setSpacing(0)
        
        # Zoom controls - enlarged for visibility
        self.zoom_in_btn = QPushButton('🔍+')
        self.zoom_in_btn.setObjectName('toolbarBtn')
        self.zoom_in_btn.setFixedSize(50, 34)
        self.zoom_in_btn.setStyleSheet('font-size: 14px; padding: 0px; margin: 0px;')
        self.zoom_in_btn.setToolTip('확대')
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        
        self.zoom_out_btn = QPushButton('🔍-')
        self.zoom_out_btn.setObjectName('toolbarBtn')
        self.zoom_out_btn.setFixedSize(50, 34)
        self.zoom_out_btn.setStyleSheet('font-size: 14px; padding: 0px; margin: 0px;')
        self.zoom_out_btn.setToolTip('축소')
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        
        self.fit_width_btn = QPushButton('너비맞춤')
        self.fit_width_btn.setObjectName('toolbarBtn')
        self.fit_width_btn.setFixedHeight(34)
        self.fit_width_btn.setStyleSheet('font-size: 12px; padding: 0px; margin: 0px;')
        self.fit_width_btn.setToolTip('너비에 맞춤')
        self.fit_width_btn.clicked.connect(self.fit_to_width)
        
        self.fit_page_btn = QPushButton('페이지맞춤')
        self.fit_page_btn.setObjectName('toolbarBtn')
        self.fit_page_btn.setFixedHeight(34)
        self.fit_page_btn.setStyleSheet('font-size: 12px; padding: 0px; margin: 0px;')
        self.fit_page_btn.setToolTip('페이지에 맞춤')
        self.fit_page_btn.clicked.connect(self.fit_to_page)
        
        self.zoom_label = QLabel(f'{int(self.scale * 100)}%')
        self.zoom_label.setObjectName('toolbarLabel')
        self.zoom_label.setFixedWidth(50)
        
        # Page navigation
        self.page_nav_label = QLabel('페이지')
        self.page_nav_label.setObjectName('toolbarLabel')
        self.page_nav_label.setFixedWidth(36)
        
        self.page_spin = QLineEdit()
        self.page_spin.setObjectName('pageSpin')
        self.page_spin.setFixedSize(50, 30)
        self.page_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_spin.setStyleSheet('font-size: 12px;')
        self.page_spin.setPlaceholderText('1')
        self.page_spin.returnPressed.connect(self._on_page_return_pressed)
        
        self.page_total_label = QLabel('/ 0')
        self.page_total_label.setObjectName('toolbarLabel')
        self.page_total_label.setFixedWidth(50)
        
        self.go_page_btn = QPushButton('이동')
        self.go_page_btn.setObjectName('toolbarBtn')
        self.go_page_btn.setFixedSize(40, 30)
        self.go_page_btn.setStyleSheet('font-size: 12px; padding: 0px; margin: 0px;')
        self.go_page_btn.setToolTip('해당 페이지로 이동')
        self.go_page_btn.clicked.connect(self._on_goto_page)
        
        # Initialize search helper
        self.search_helper = PDFSearchHelper(self)
        
        # Add zoom controls first
        toolbar_layout.addWidget(self.zoom_in_btn)
        toolbar_layout.addWidget(self.zoom_out_btn)
        toolbar_layout.addWidget(self.fit_width_btn)
        toolbar_layout.addWidget(self.fit_page_btn)
        toolbar_layout.addWidget(self.zoom_label)
        toolbar_layout.addSpacing(16)
        
        # Page navigation controls
        toolbar_layout.addWidget(self.page_nav_label)
        toolbar_layout.addWidget(self.page_spin)
        toolbar_layout.addWidget(self.page_total_label)
        toolbar_layout.addWidget(self.go_page_btn)
        toolbar_layout.addSpacing(16)
        
        # Setup search UI using helper
        search_input, find_prev_btn, find_next_btn, search_count_label = self.search_helper.setup_search_ui(toolbar_layout)
        
        # Store references for compatibility
        self.search_input = search_input
        self.find_prev_btn = find_prev_btn
        self.find_next_btn = find_next_btn
        
        # Set Korean UI text
        self.search_helper.set_placeholder_text('검색어 입력')
        self.search_helper.set_button_text('이전', '이후')
        
        toolbar_layout.addStretch()
        
        # Scroll area for PDF content
        self.container = QWidget()
        self.vbox = QVBoxLayout(self.container)
        self.vbox.setContentsMargins(20, 20, 20, 20)
        self.vbox.setSpacing(20)
        self.vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.setWidget(self.container)
        self.pdf_doc = None
        self.page_labels = []
        self.page_base_pixmaps = []
        self.char_data = []
        self.raw_text = ''
        self.word_highlights = {}
        self.last_compared_area = {}
        self.pending_selection_rect = None
        
        # Add drop zone indicator when empty
        self.drop_label = QLabel('📄 PDF 파일을 여기에 드래그 앤 드랍하세요\n또는 아래 버튼을 클릭하여 파일을 선택하세요')
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet('''
            QLabel {
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 500;
                padding: 40px 30px;
                border: 2px dashed #8E8E93;
                border-radius: 12px;
                background-color: rgba(120, 120, 128, 0.3);
            }
        ''')
        self.vbox.addWidget(self.drop_label)

        self.open_pdf_btn = QPushButton('📁 PDF 파일 선택')
        self.open_pdf_btn.setObjectName('actionBtn')
        self.open_pdf_btn.setFixedHeight(48)
        self.open_pdf_btn.setMinimumWidth(180)
        self.open_pdf_btn.setStyleSheet('''
            QPushButton {
                font-size: 14px;
                font-weight: 600;
                padding: 10px 20px;
            }
        ''')
        self.open_pdf_btn.clicked.connect(self.open_pdf_via_dialog)
        self.vbox.addWidget(self.open_pdf_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        
        self.parent_tool = None  # Reference to parent tool for callback
        self.verticalScrollBar().valueChanged.connect(self._on_scroll_page_changed)

    def _on_scroll_page_changed(self):
        if not self.page_labels:
            return
        scroll_y = self.verticalScrollBar().value()
        viewport_h = self.viewport().height()
        mid_y = scroll_y + viewport_h / 2
        page_top = self.vbox.contentsMargins().top()
        for i, lbl in enumerate(self.page_labels):
            lbl_h = lbl.height()
            lbl_mid = page_top + lbl_h / 2
            if mid_y < lbl_mid + lbl_h / 2:
                self.page_spin.setText(str(i + 1))
                break
            page_top += lbl_h + self.vbox.spacing()

    def load_pdf(self, path):
        try:
            self.pdf_doc = fitz.open(path)
            self.reload_pages()
            return True
        except Exception:
            return False

    def update_loaded_pdf_label(self, pdf_path):
        if not self.parent_tool:
            return
        if self == self.parent_tool.viewer1:
            self.parent_tool.lbl_name1.setText(f"<b style='color:#007AFF; font-size:15px; font-weight:600;'>[PDF 1] 📄 {os.path.basename(pdf_path)}</b>")
        elif self == self.parent_tool.viewer2:
            self.parent_tool.lbl_name2.setText(f"<b style='color:#007AFF; font-size:15px; font-weight:600;'>[PDF 2] 📄 {os.path.basename(pdf_path)}</b>")

    def open_pdf_via_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'PDF 파일 선택', '', 'PDF Files (*.pdf)')
        if not file_path:
            return
        self.clear_all_data()
        if self.load_pdf(file_path):
            self.update_loaded_pdf_label(file_path)
        else:
            QMessageBox.warning(self, '오류', 'PDF 파일을 불러오지 못했습니다.')
    
    def set_parent_tool(self, parent_tool):
        """Set reference to parent tool for callback"""
        self.parent_tool = parent_tool
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            # Check if any URL is a PDF file
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith('.pdf'):
                    event.acceptProposedAction()
                    # Highlight drop zone
                    if hasattr(self, 'drop_label') and self.drop_label.isVisible():
                        self.drop_label.setStyleSheet('''
                            QLabel {
                                color: #FFFFFF;
                                font-size: 14px;
                                font-weight: 600;
                                padding: 40px 30px;
                                border: 2px dashed #007AFF;
                                border-radius: 12px;
                                background-color: rgba(0, 122, 255, 0.4);
                            }
                        ''')
                    return
        event.ignore()
    
    def dragLeaveEvent(self, event):
        """Handle drag leave event"""
        # Reset drop zone styling
        if hasattr(self, 'drop_label') and self.drop_label.isVisible():
            self.drop_label.setStyleSheet('''
                QLabel {
                    color: #FFFFFF;
                    font-size: 14px;
                    font-weight: 500;
                    padding: 40px 30px;
                    border: 2px dashed #8E8E93;
                    border-radius: 12px;
                    background-color: rgba(120, 120, 128, 0.3);
                }
            ''')
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event"""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith('.pdf'):
                    pdf_path = url.toLocalFile()
                    
                    # Clear existing data
                    self.clear_all_data()
                    
                    # Load PDF
                    if self.load_pdf(pdf_path):
                        self.update_loaded_pdf_label(pdf_path)
                    
                    event.acceptProposedAction()
                    return
        event.ignore()

    def reload_pages(self):
        if not self.pdf_doc:
            return
        
        # Hide drop label when PDF is loaded
        if hasattr(self, 'drop_label'):
            self.drop_label.hide()
        if hasattr(self, 'open_pdf_btn'):
            self.open_pdf_btn.hide()
        
        for lbl in self.page_labels:
            lbl.setParent(None)
        self.page_labels.clear()
        self.page_base_pixmaps.clear()
        total_pages = len(self.pdf_doc)
        self.page_total_label.setText(f'/ {total_pages}')
        for i in range(total_pages):
            page = self.pdf_doc.load_page(i)
            pix = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale))
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            base_pixmap = QPixmap.fromImage(img.copy())
            lbl = SelectableLabel(self.container)
            lbl.page_num = i
            lbl.setPixmap(base_pixmap.copy())
            self.vbox.addWidget(lbl)
            self.page_labels.append(lbl)
            self.page_base_pixmaps.append(base_pixmap)
        self.refresh_highlights()

    def refresh_highlights(self):
        for i, lbl in enumerate(self.page_labels):
            if i >= len(self.page_base_pixmaps):
                continue
            img = self.page_base_pixmaps[i].toImage().copy()
            painter = QPainter(img)
            if i in self.last_compared_area:
                for bbox in self.last_compared_area[i]:
                    rect = QRect(int(bbox[0] * self.scale), int(bbox[1] * self.scale), int((bbox[2] - bbox[0]) * self.scale), int((bbox[3] - bbox[1]) * self.scale))
                    painter.fillRect(rect, COLOR_AREA)
            if i in self.word_highlights:
                for bbox, word_id, color in self.word_highlights[i]:
                    if bbox:
                        rect = QRect(int(bbox[0] * self.scale), int(bbox[1] * self.scale), int((bbox[2] - bbox[0]) * self.scale), int((bbox[3] - bbox[1]) * self.scale))
                        painter.fillRect(rect, color)
            # Use search helper for search highlights
            self.search_helper.render_search_highlights(painter, i, self.scale)
            painter.end()
            lbl.setPixmap(QPixmap.fromImage(img))

    def on_selection_complete(self, page_num, rect):
        if rect.width() < 5:
            return
        x0 = rect.x() / self.scale
        y0 = rect.y() / self.scale
        x1 = (rect.x() + rect.width()) / self.scale
        y1 = (rect.y() + rect.height()) / self.scale
        self.pending_selection_rect = (page_num, fitz.Rect(x0, y0, x1, y1))
        self.char_data = []
        self.raw_text = ''
        self.extract_and_process_text(page_num, rect)

    def extract_and_process_text(self, page_num, rect):
        x0 = rect.x() / self.scale
        y0 = rect.y() / self.scale
        x1 = (rect.x() + rect.width()) / self.scale
        y1 = (rect.y() + rect.height()) / self.scale
        fitz_rect = fitz.Rect(x0, y0, x1, y1)
        page = self.pdf_doc.load_page(page_num)
        raw_dict = page.get_text('rawdict', clip=fitz_rect)
        all_raw_chars = []
        for block in raw_dict.get('blocks', []):
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    for char in span.get('chars', []):
                        c = char['c']
                        c_norm = unicodedata.normalize('NFC', c)
                        all_raw_chars.append({'char': c_norm, 'bbox': char['bbox'], 'y': char['bbox'][1], 'x': char['bbox'][0]})
        if not all_raw_chars:
            return
        all_raw_chars.sort(key=lambda x: x['y'])
        grouped = []
        curr = [all_raw_chars[0]]
        for i in range(1, len(all_raw_chars)):
            if all_raw_chars[i]['y'] - curr[-1]['y'] < 5.0:
                curr.append(all_raw_chars[i])
            else:
                grouped.append(curr)
                curr = [all_raw_chars[i]]
        grouped.append(curr)
        final_norm = []
        raw_lines = []
        word_counter = 0
        for line in grouped:
            line.sort(key=lambda x: x['x'])
            line_str_raw = []
            word_counter += 1
            for i, c in enumerate(line):
                line_str_raw.append(c['char'])
                if i > 0 and (line[i - 1]['char'].strip() == '' or abs(c['x'] - line[i - 1]['bbox'][2]) > 2.5):
                    word_counter += 1
                clean_char = c['char'].lower().strip()
                if not re.match(r'[가-힣a-z0-9.,?!;:()\-\[\]{}\'"]', clean_char):
                    continue
                if not final_norm or not (clean_char == final_norm[-1]['char'] and abs(c['x'] - final_norm[-1]['x']) < 2.5):
                    final_norm.append({'char': clean_char, 'bbox': c['bbox'], 'x': c['x'], 'page': page_num, 'word_id': word_counter})
            raw_lines.append(''.join(line_str_raw))
        self.char_data = final_norm
        self.raw_text = '\n'.join(raw_lines)

    def _on_page_return_pressed(self):
        self._on_goto_page()
    
    def _on_goto_page(self):
        if not self.pdf_doc:
            return
        text = self.page_spin.text().strip()
        if not text:
            return
        try:
            page_num = int(text)
        except ValueError:
            return
        self.goto_page(page_num)
    
    def goto_page(self, page_num):
        if not self.pdf_doc or not self.page_labels:
            return
        total = len(self.page_labels)
        if page_num < 1:
            page_num = 1
        if page_num > total:
            page_num = total
        idx = page_num - 1
        lbl = self.page_labels[idx]
        y = lbl.y()
        self.verticalScrollBar().setValue(y)
        self.page_spin.setText(str(page_num))
    
    def zoom_in(self):
        self.scale *= 1.2
        self.update_zoom_label()
        self.reload_pages()

    def zoom_out(self):
        self.scale /= 1.2
        self.update_zoom_label()
        self.reload_pages()

    def fit_to_width(self):
        if not self.pdf_doc or len(self.pdf_doc) == 0:
            return
        page = self.pdf_doc.load_page(0)
        page_rect = page.rect
        available_width = max(100, self.viewport().width() - 40)
        self.scale = available_width / page_rect.width
        self.update_zoom_label()
        self.reload_pages()

    def fit_to_page(self):
        if not self.pdf_doc or len(self.pdf_doc) == 0:
            return
        page = self.pdf_doc.load_page(0)
        page_rect = page.rect
        available_width = max(100, self.viewport().width() - 40)
        available_height = max(100, self.viewport().height() - 40)
        width_scale = available_width / page_rect.width
        height_scale = available_height / page_rect.height
        self.scale = min(width_scale, height_scale)
        self.update_zoom_label()
        self.reload_pages()

    def update_zoom_label(self):
        self.zoom_label.setText(f'{int(self.scale * 100)}%')

    # Search methods delegated to helper
    def on_search_text_changed(self, text):
        self.search_helper.on_search_text_changed(text)

    def search_in_pdf(self, text):
        self.search_helper.search_in_pdf(text)

    def highlight_search_results(self):
        self.search_helper.highlight_search_results()

    def clear_search_highlights(self):
        self.search_helper.clear_search_highlights()

    def find_next(self):
        self.search_helper.find_next()

    def find_previous(self):
        self.search_helper.find_previous()

    def go_to_search_result(self, index):
        self.search_helper.go_to_search_result(index)

    def highlight_current_result(self, page_num, rect):
        self.search_helper.highlight_current_result(page_num, rect)

    def remove_current_highlight(self):
        self.search_helper.remove_current_highlight()
    
    def flash_search_highlight(self, page_num, rect):
        # Temporary highlight to show current search result
        if page_num not in self.search_highlights:
            self.search_highlights[page_num] = []
        self.search_highlights[page_num].append(rect)
        self.refresh_highlights()
        
        # Remove after a short delay
        QTimer.singleShot(500, lambda: self.remove_flash_highlight(page_num, rect))
    
    def remove_flash_highlight(self, page_num, rect):
        if page_num in self.search_highlights:
            try:
                self.search_highlights[page_num].remove(rect)
                if not self.search_highlights[page_num]:
                    del self.search_highlights[page_num]
                self.refresh_highlights()
            except ValueError:
                pass

    def clear_all_data(self):
        self.word_highlights.clear()
        self.last_compared_area.clear()
        self.char_data = []
        self.raw_text = ''
        self.search_helper.clear_all_search_data()
        for lbl in self.page_labels:
            lbl.clear_selection()
        if hasattr(self, 'drop_label'):
            self.drop_label.show()
        if hasattr(self, 'open_pdf_btn'):
            self.open_pdf_btn.show()
        self.refresh_highlights()


class PdfCompareWidget(QWidget):
    tool_key = 'pdf_compare'
    tool_name = '📄 PDF 지정 영역 비교'
    window_title = 'PDF 지정 영역 비교'
    singleton = True
    enabled = True

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 0, 10, 10)

        # Middle Workspace Container
        self.workspace = QFrame()
        self.workspace.setObjectName('workspace')
        workspace_layout = QHBoxLayout(self.workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(16)
        # PDF 1 Panel
        v1_panel = QFrame()
        v1_panel.setObjectName('pdfPanel')
        v1_layout = QVBoxLayout(v1_panel)
        v1_layout.setContentsMargins(0, 0, 0, 0)
        v1_layout.setSpacing(0)
        
        self.viewer1 = PDFViewer()
        self.viewer1.set_parent_tool(self)  # Set parent reference
        
        # Add PDF name label at top with minimal margin
        self.lbl_name1 = QLabel("<b style='color:#007AFF; font-size:15px; font-weight:600;'>[PDF 1]</b>")
        self.lbl_name1.setContentsMargins(10, 6, 10, 4)
        v1_layout.addWidget(self.lbl_name1)
        
        # Add toolbar
        v1_layout.addWidget(self.viewer1.toolbar)
        v1_layout.addWidget(self.viewer1, 1)
        
        # Create PDF name labels
        self.lbl_name2 = QLabel("<b style='color:#007AFF; font-size:15px; font-weight:600;'>[PDF 2]</b>")
        
        # Bottom controls for PDF 1 (removed - moved to bottom bar)
        workspace_layout.addWidget(v1_panel)

        # PDF 2 Panel
        v2_panel = QFrame()
        v2_panel.setObjectName('pdfPanel')
        v2_layout = QVBoxLayout(v2_panel)
        v2_layout.setContentsMargins(0, 0, 0, 0)
        v2_layout.setSpacing(0)
        
        self.viewer2 = PDFViewer()
        self.viewer2.set_parent_tool(self)  # Set parent reference
        
        # Add PDF name label at top with minimal margin
        v2_layout.addWidget(self.lbl_name2)
        self.lbl_name2.setContentsMargins(10, 6, 10, 4)
        
        # Add toolbar
        v2_layout.addWidget(self.viewer2.toolbar)
        v2_layout.addWidget(self.viewer2, 1)
        
        # Bottom controls for PDF 2 (removed - moved to bottom bar)
        workspace_layout.addWidget(v2_panel)
        
        layout.addWidget(self.workspace, 1)
        
        # Loading Overlay (Image-based, centered)
        self.loading_overlay = QLabel(self)
        self.loading_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_overlay.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.85);
                border-radius: 12px;
            }
        """)
        self.loading_overlay.setFixedSize(400, 300)
        self.loading_overlay.hide()
        
        # Loading message label
        self.loading_message = QLabel("비교중", self.loading_overlay)
        self.loading_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_message.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                font-size: 16px;
                color: #333333;
                font-weight: 500;
            }
        """)
        self.loading_message.setGeometry(0, 210, 400, 30)
        
        # Loading GIF (nuni_timer_w.gif)
        self.loading_gif = QLabel(self.loading_overlay)
        self.loading_gif.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_gif.setFixedSize(160, 160)
        self.loading_gif.setGeometry(120, 30, 160, 160)
        
        gif_path = get_timer_gif_path()
        if gif_path and os.path.exists(gif_path):
            self.movie = QMovie(gif_path)
            self.movie.setScaledSize(self.loading_gif.size())
            self.loading_gif.setMovie(self.movie)
        else:
            self.loading_gif.setText("⏳")
            self.loading_gif.setStyleSheet("font-size: 48px; background: transparent; border: none;")

        # Bottom Action Bar
        bottom_action_bar = QFrame()
        bottom_action_bar.setObjectName('actionBar')
        bottom_action_layout = QHBoxLayout(bottom_action_bar)
        bottom_action_layout.setContentsMargins(12, 8, 12, 8)
        bottom_action_layout.setSpacing(10)

        # Left: Extract data button (secondary)
        self.btn_view_text = QPushButton('📋  추출 데이터 확인')
        self.btn_view_text.setObjectName('secondaryBtn')
        self.btn_view_text.setFixedHeight(40)
        self.btn_view_text.setMinimumWidth(150)
        bottom_action_layout.addWidget(self.btn_view_text)

        bottom_action_layout.addStretch()

        # Center: Compare button (primary)
        self.btn_compare = QPushButton('⚡  비교 실행')
        self.btn_compare.setObjectName('compareBtn')
        self.btn_compare.setFixedHeight(42)
        self.btn_compare.setMinimumWidth(150)
        bottom_action_layout.addWidget(self.btn_compare)

        bottom_action_layout.addStretch()

        # Right: Reset buttons (destructive)
        self.btn_reset_page = QPushButton('↩  페이지 초기화')
        self.btn_reset_page.setObjectName('resetBtn')
        self.btn_reset_page.setFixedHeight(40)
        self.btn_reset_page.setMinimumWidth(130)
        bottom_action_layout.addWidget(self.btn_reset_page)

        self.btn_reset_all = QPushButton('🗑  초기화')
        self.btn_reset_all.setObjectName('resetBtn')
        self.btn_reset_all.setFixedHeight(40)
        self.btn_reset_all.setMinimumWidth(120)
        bottom_action_layout.addWidget(self.btn_reset_all)

        layout.addWidget(bottom_action_bar)

        self.last_s1_norm = ''
        self.last_s2_norm = ''
        self.last_s1_raw = ''
        self.last_s2_raw = ''
        
        # Thread manager for async comparison
        self.compare_manager = None

        self.btn_compare.clicked.connect(self.request_comparison)
        self.btn_reset_all.clicked.connect(self.request_reset_all)
        self.btn_reset_page.clicked.connect(self.request_reset_page)
        self.btn_view_text.clicked.connect(self.show_text_dialog)

    def resizeEvent(self, event):
        """창 크기 변경 시 로딩 오버레이 중앙 정렬"""
        super().resizeEvent(event)
        if hasattr(self, 'loading_overlay'):
            # Center the loading overlay in the widget
            x = (self.width() - self.loading_overlay.width()) // 2
            y = (self.height() - self.loading_overlay.height()) // 2
            self.loading_overlay.move(x, y)

    def show_loading(self, show: bool, message: str = ""):
        """로딩 오버레이 표시/숨김 및 workspace 활성화/비활성화"""
        if show:
            if message:
                self.loading_message.setText(message)
            # Center the overlay
            x = (self.width() - self.loading_overlay.width()) // 2
            y = (self.height() - self.loading_overlay.height()) // 2
            self.loading_overlay.move(x, y)
            self.loading_overlay.show()
            self.loading_overlay.raise_()
            if hasattr(self, 'movie') and self.movie:
                self.movie.start()
            # Disable workspace to block user input
            self.workspace.setEnabled(False)
        else:
            self.loading_overlay.hide()
            if hasattr(self, 'movie') and self.movie:
                self.movie.stop()
            # Re-enable workspace
            self.workspace.setEnabled(True)

    def request_comparison(self):
        if not self.viewer1.char_data or not self.viewer2.char_data:
            QMessageBox.warning(self, '경고', '양쪽 비교 영역을 먼저 드래그해주세요.')
            return
        self.start_async_comparison()

    def request_reset_all(self):
        QTimer.singleShot(100, self.reset_all)

    def request_reset_page(self):
        QTimer.singleShot(100, self.reset_current_page)

    def reset_all(self):
        self.show_loading(True, "하이라이트 초기화 중...")
        # GIF 애니메이션이 시작될 시간을 확보 후 단계별 실행
        QTimer.singleShot(120, lambda: self._do_reset_all(0))
    
    def _do_reset_all(self, step_index=0):
        """실제 초기화 작업 수행 (단계별 실행)"""
        viewers = [self.viewer1, self.viewer2]

        if step_index >= len(viewers):
            self.last_s1_norm = ''
            self.last_s2_norm = ''
            self.show_loading(False)
            return

        try:
            viewer = viewers[step_index]
            viewer.word_highlights.clear()
            viewer.last_compared_area.clear()
            viewer.diff_pages = []
            viewer.diff_index = -1
            viewer.reload_pages()
            QTimer.singleShot(10, lambda: self._do_reset_all(step_index + 1))
        except Exception:
            self.show_loading(False)
            raise

    def reset_current_page(self):
        self.show_loading(True, "페이지 초기화 중...")
        # GIF 애니메이션이 시작될 시간을 확보 후 단계별 실행
        QTimer.singleShot(120, lambda: self._do_reset_current_page(0))
    
    def _do_reset_current_page(self, step_index=0):
        """실제 페이지 초기화 작업 수행 (단계별 실행)"""
        if step_index == 0:
            self._reset_current_page1 = self.get_current_page(self.viewer1)
            self._reset_current_page2 = self.get_current_page(self.viewer2)

        def clear_viewer_current_page(viewer, current_page):
            if current_page is None:
                return

            if current_page in viewer.last_compared_area:
                del viewer.last_compared_area[current_page]

            if current_page in viewer.word_highlights:
                del viewer.word_highlights[current_page]

            if hasattr(viewer, 'current_highlights') and current_page in viewer.current_highlights:
                del viewer.current_highlights[current_page]

            if current_page < len(viewer.page_labels):
                viewer.page_labels[current_page].clear_selection()

            if viewer.pending_selection_rect and viewer.pending_selection_rect[0] == current_page:
                viewer.pending_selection_rect = None
                viewer.char_data.clear()
                viewer.raw_text = ''

        try:
            if step_index == 0:
                clear_viewer_current_page(self.viewer1, self._reset_current_page1)
                self.viewer1.refresh_highlights()
                QTimer.singleShot(10, lambda: self._do_reset_current_page(1))
                return

            if step_index == 1:
                clear_viewer_current_page(self.viewer2, self._reset_current_page2)
                self.viewer2.refresh_highlights()
                QTimer.singleShot(10, lambda: self._do_reset_current_page(2))
                return

            self.show_loading(False)
            self._reset_current_page1 = None
            self._reset_current_page2 = None
        except Exception:
            self.show_loading(False)
            self._reset_current_page1 = None
            self._reset_current_page2 = None
            raise
    
    def get_current_page(self, viewer):
        if not viewer.page_labels:
            return None

        viewport_height = viewer.viewport().height()
        scroll_top = viewer.verticalScrollBar().value()
        scroll_bottom = scroll_top + viewport_height

        max_visible_height = -1
        current_page = None
        page_top = viewer.vbox.contentsMargins().top()

        for i, label in enumerate(viewer.page_labels):
            label_top = page_top
            label_bottom = label_top + label.height()

            visible_top = max(scroll_top, label_top)
            visible_bottom = min(scroll_bottom, label_bottom)
            visible_height = max(0, visible_bottom - visible_top)

            if visible_height > max_visible_height:
                max_visible_height = visible_height
                current_page = i

            page_top = label_bottom + viewer.vbox.spacing()

        return current_page

    def start_async_comparison(self):
        """비동기 PDF 비교 시작 (QThread 사용)"""
        # 이전 manager 정리
        if self.compare_manager:
            self.compare_manager.cleanup()
        
        # 데이터 준비
        for viewer in [self.viewer1, self.viewer2]:
            viewer.last_compared_area.clear()
            if viewer.pending_selection_rect:
                page_num, rect = viewer.pending_selection_rect
                viewer.last_compared_area[page_num] = [rect]
        
        # 로딩 오버레이 표시
        self.show_loading(True, "비교중")
        self.btn_compare.setEnabled(False)
        
        # Thread Manager 생성 및 설정
        self.compare_manager = CompareThreadManager(self)
        self.compare_manager.setup_worker(
            char_data1=self.viewer1.char_data,  # 참조만 전달 (복사는 run()에서)
            char_data2=self.viewer2.char_data,
            raw_text1=self.viewer1.raw_text,
            raw_text2=self.viewer2.raw_text,
            pending_rect1=self.viewer1.pending_selection_rect,
            pending_rect2=self.viewer2.pending_selection_rect
        )
        
        # Signal 연결
        self.compare_manager.started.connect(self._on_compare_started)
        self.compare_manager.progress.connect(self._on_compare_progress)
        self.compare_manager.result_ready.connect(self._on_compare_result_ready)
        self.compare_manager.finished.connect(self._on_compare_finished)
        self.compare_manager.error.connect(self._on_compare_error)
        
        # GIF 첫 프레임 렌더링 시간 확보 후 스레드 시작
        QTimer.singleShot(50, self.compare_manager.start_comparison)
    
    def _on_compare_started(self):
        """비교 시작 시 (스레드가 실제로 시작된 시점)"""
        pass  # 로딩 다이얼로그는 이미 표시됨
    
    def _on_compare_progress(self, current, total):
        """진행률 업데이트 (오버레이 메시지 업데이트)"""
        if total > 0:
            percent = int((current / total) * 100)
            self.loading_message.setText(f"PDF 비교 중... ({percent}%)")
    
    def _on_compare_result_ready(self, result: dict):
        """Worker 결과를 받아 UI 업데이트 (메인 스레드)"""
        try:
            # 결과 저장
            self.last_s1_norm = result['s1_norm']
            self.last_s2_norm = result['s2_norm']
            self.last_s1_raw = result['s1_raw']
            self.last_s2_raw = result['s2_raw']
            
            # 하이라이트 적용 (일괄 처리)
            highlights1 = result.get('highlights1', [])
            highlights2 = result.get('highlights2', [])
            
            for hl in highlights1:
                self._apply_highlight_from_dict(self.viewer1, hl, COLOR_P1)
            for hl in highlights2:
                self._apply_highlight_from_dict(self.viewer2, hl, COLOR_P2)
            
            # diff_pages 설정
            self.viewer1.diff_pages = result.get('diff_pages1', [])
            self.viewer2.diff_pages = result.get('diff_pages2', [])
            self.viewer1.diff_index = -1
            self.viewer2.diff_index = -1
            
            # 뷰어 갱신 (최적화: visible 페이지만 우선 갱신)
            self._refresh_viewers_optimized()
            
        except Exception:
            raise
    
    def _refresh_viewers_optimized(self):
        """뷰어 갱신 최적화 - visible 페이지 우선, 나머지는 지연 갱신"""
        # 현재 visible 페이지 확인
        visible_pages1 = self._get_visible_pages(self.viewer1)
        visible_pages2 = self._get_visible_pages(self.viewer2)
        
        # 선택 영역만 먼저 클리어
        for lbl in self.viewer1.page_labels:
            lbl.clear_selection()
        for lbl in self.viewer2.page_labels:
            lbl.clear_selection()
        
        # Visible 페이지만 즉시 갱신 (사용자가 볼 수 있는 부분)
        for page_num in visible_pages1:
            if page_num < len(self.viewer1.page_labels):
                self.viewer1.page_labels[page_num].update()
        for page_num in visible_pages2:
            if page_num < len(self.viewer2.page_labels):
                self.viewer2.page_labels[page_num].update()
        
        # 전체 갱신은 지연 실행 (메인 루프 여유 있을 때)
        QTimer.singleShot(100, self._deferred_full_refresh)
    
    def _get_visible_pages(self, viewer):
        """현재 뷰포트에 보이는 페이지 번호 목록 반환 (QScrollArea용)"""
        visible_pages = []
        if not viewer.page_labels:
            return visible_pages
        
        # QScrollArea의 viewport 기준으로 계산
        viewport = viewer.viewport()
        if not viewport:
            return [0]  # 기본값: 첫 페이지
        
        scroll_y = viewer.verticalScrollBar().value()
        viewport_height = viewport.height()
        
        for i, lbl in enumerate(viewer.page_labels):
            # QLabel의 위치 계산 (스크롤 영역 내 상대 위치)
            lbl_y = lbl.y() if hasattr(lbl, 'y') else i * 100  # fallback
            lbl_height = lbl.height() if hasattr(lbl, 'height') else 100
            
            # 라벨이 viewport 내에 있는지 체크
            lbl_top = lbl_y
            lbl_bottom = lbl_y + lbl_height
            
            if lbl_bottom > scroll_y and lbl_top < scroll_y + viewport_height:
                visible_pages.append(i)
        
        return visible_pages if visible_pages else [0]
    
    def _deferred_full_refresh(self):
        """지연된 전체 갱신"""
        if hasattr(self, 'viewer1') and self.viewer1:
            self.viewer1.reload_pages()
        if hasattr(self, 'viewer2') and self.viewer2:
            self.viewer2.reload_pages()
        # 전체 갱신 완료 후 오버레이 숨김
        self.show_loading(False)
        self.btn_compare.setEnabled(True)
    
    def _on_compare_finished(self):
        """비교 완료 후 정리"""
        # 오버레이는 _deferred_full_refresh에서 전체 갱신 후 숨김
        if self.compare_manager:
            self.compare_manager.cleanup()
            self.compare_manager = None
    
    def _on_compare_error(self, error_msg: str):
        """비교 오류 처리"""
        self.show_loading(False)
        self.btn_compare.setEnabled(True)
        QMessageBox.critical(self, "비교 오류", f"PDF 비교 중 오류가 발생했습니다:\n{error_msg}")
        if self.compare_manager:
            self.compare_manager.cleanup()
            self.compare_manager = None
    
    def _apply_highlight_from_dict(self, viewer, hl_data: dict, color):
        """Worker에서 전달받은 highlight 데이터를 뷰어에 적용"""
        page_num = hl_data['page']
        bbox = hl_data['bbox']
        word_id = hl_data['word_id']
        
        if page_num not in viewer.word_highlights:
            viewer.word_highlights[page_num] = []
        
        # 중복 체크
        existing = [(b, w) for b, w, c in viewer.word_highlights[page_num]]
        if (bbox, word_id) not in existing:
            viewer.word_highlights[page_num].append((bbox, word_id, color))
    
    def run_comparison(self):
        """동기식 비교 (호환성 유지용 - 권장하지 않음)"""
        # 이 메서드는 더 이상 사용하지 않음 - 비동기 방식으로 대체됨
        self.start_async_comparison()
    
    def closeEvent(self, event):
        """위젯 종료 시 스레드 정리 (좀비 프로세스 방지)"""
        # 실행 중인 비교 작업이 있으면 정리
        if self.compare_manager:
            self.compare_manager.cancel()
            self.compare_manager.cleanup()
        
        super().closeEvent(event)

    def show_text_dialog(self):
        if not self.last_s1_norm and not self.last_s2_norm:
            QMessageBox.information(self, '안내', '최근 비교 데이터가 없습니다.')
            return
        ViewComparisonTextDialog(self.last_s1_norm, self.last_s2_norm, self.last_s1_raw, self.last_s2_raw, self).exec()

    def show_legend_caution_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('📋 범례 및 주의사항')
        dialog.setFixedSize(600, 450)
        dialog.setStyleSheet(MODERN_QSS)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Legend group
        legend_group = QGroupBox('🎨 하이라이트 범례')
        legend_group_layout = QVBoxLayout(legend_group)
        legend_group_layout.setContentsMargins(15, 15, 15, 15)
        legend_group_layout.setSpacing(10)
        
        legend_content = QLabel(
            f"<div style='font-size:14px; line-height:1.8;'>"
            f"<div style='margin-bottom:10px;'>"
            f"<span style='color:rgba(255,149,0,0.6); background:rgba(255,149,0,0.3); padding:6px 12px; border-radius:4px; margin-right:10px;'>■</span>"
            f"<b>PDF1 (주황색)</b>: PDF 1에서 삭제되거나 변경된 내용"
            f"</div>"
            f"<div>"
            f"<span style='color:rgba(0,255,127,0.6); background:rgba(0,255,127,0.3); padding:6px 12px; border-radius:4px; margin-right:10px;'>■</span>"
            f"<b>PDF2 (연두색)</b>: PDF 2에서 추가되거나 변경된 내용"
            f"</div>"
            f"</div>"
        )
        legend_group_layout.addWidget(legend_content)
        layout.addWidget(legend_group)
        
        # Caution group
        caution_group = QGroupBox('⚠️ 주의사항')
        caution_group_layout = QVBoxLayout(caution_group)
        caution_group_layout.setContentsMargins(15, 15, 15, 15)
        caution_group_layout.setSpacing(8)
        
        caution_content = QLabel(
            "<div style='font-size:14px; line-height:1.8;'>"
            "<div style='margin-bottom:12px;'>• <b>정규화 대조</b>: 한글, 영문, 숫자만 비교 대상</div>"
            "<div style='margin-bottom:12px;'>• <b>띄어쓰기</b>: 띄어쓰기 오류는 검증되지 않음</div>"
            "<div style='margin-bottom:12px;'>• <b>표 추출</b>: 셀 단위 드래그를 권장함</div>"
            "<div style='margin-bottom:12px;'>• <b>하이라이트</b>: 결과는 한쪽에만 표시될 수 있음</div>"
            "<div>• <b>정확도</b>: 100% 완벽하지 않을 수 있음, 참고용으로 활용</div>"
            "</div>"
        )
        caution_group_layout.addWidget(caution_content)
        layout.addWidget(caution_group)
        
        layout.addStretch()
        
        close_btn = QPushButton('닫기')
        close_btn.setObjectName('actionBtn')
        close_btn.setFixedHeight(38)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()

    def show_legend_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('🎨 하이라이트 범례')
        dialog.setFixedSize(500, 300)
        dialog.setStyleSheet(MODERN_QSS)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel('<h2 style="color:#004b93; margin-bottom:20px;">🎨 하이라이트 범례</h2>')
        layout.addWidget(title)
        
        content = QLabel(
            f"<div style='font-size:14px; line-height:1.8;'>"
            f"<div style='margin-bottom:15px;'>"
            f"<span style='color:rgba(255,149,0,0.6); background:rgba(255,149,0,0.3); padding:6px 12px; border-radius:4px; margin-right:10px;'>■</span>"
            f"<b>PDF1 (주황색)</b>: PDF 1에서 삭제되거나 변경된 내용"
            f"</div>"
            f"<div>"
            f"<span style='color:rgba(0,255,127,0.6); background:rgba(0,255,127,0.3); padding:6px 12px; border-radius:4px; margin-right:10px;'>■</span>"
            f"<b>PDF2 (연두색)</b>: PDF 2에서 추가되거나 변경된 내용"
            f"</div>"
            f"</div>"
        )
        layout.addWidget(content)
        layout.addStretch()
        
        close_btn = QPushButton('닫기')
        close_btn.setObjectName('actionBtn')
        close_btn.setFixedHeight(38)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()

    def show_caution_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('⚠️ 주의사항')
        dialog.setFixedSize(550, 350)
        dialog.setStyleSheet(MODERN_QSS)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel('<h2 style="color:#E6A23C; margin-bottom:20px;">⚠️ 주의사항</h2>')
        layout.addWidget(title)
        
        content = QLabel(
            "<div style='font-size:14px; line-height:1.8;'>"
            "<div style='margin-bottom:12px;'>• <b>정규화 대조</b>: 한글, 영문, 숫자만 비교 대상</div>"
            "<div style='margin-bottom:12px;'>• <b>띄어쓰기</b>: 띄어쓰기 오류는 검증되지 않음</div>"
            "<div style='margin-bottom:12px;'>• <b>표 추출</b>: 셀 단위 드래그를 권장함</div>"
            "<div style='margin-bottom:12px;'>• <b>하이라이트</b>: 결과는 한쪽에만 표시될 수 있음</div>"
            "<div>• <b>정확도</b>: 100% 완벽하지 않을 수 있음, 참고용으로 활용</div>"
            "</div>"
        )
        layout.addWidget(content)
        layout.addStretch()
        
        close_btn = QPushButton('닫기')
        close_btn.setObjectName('actionBtn')
        close_btn.setFixedHeight(38)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()

    def add_hl(self, viewer, info, color):
        page_num = info['page']
        if page_num not in viewer.word_highlights:
            viewer.word_highlights[page_num] = []
        if not any(h[0] == info['bbox'] and h[1] == color for h in viewer.word_highlights[page_num]):
            viewer.word_highlights[page_num].append((info['bbox'], color))
