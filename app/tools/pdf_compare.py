import os
import re
import unicodedata
from difflib import SequenceMatcher

import fitz
from PyQt6.QtCore import QEasingCurve, QPoint, QParallelAnimationGroup, QPropertyAnimation, QRect, QTimer, Qt, QMimeData
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QFrame, QGraphicsOpacityEffect, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget

from app.common.resources import get_resource_path
from app.common.styles import COLOR_WORKSPACE_DARK, COLOR_P1, COLOR_P2, COLOR_AREA, MODERN_QSS


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


class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.layout = QVBoxLayout(self)
        self.bg_frame = QFrame()
        self.bg_frame.setStyleSheet('background-color: rgba(255, 255, 255, 230); border-radius: 20px; border: 1px solid #DCDFE6;')
        self.bg_frame.setFixedSize(300, 200)

        f_layout = QVBoxLayout(self.bg_frame)
        self.icon_label = QLabel()
        logo_path = get_resource_path('posid_logo.png')
        if os.path.exists(logo_path):
            self.icon_label.setPixmap(QPixmap(logo_path).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.icon_label.setText('⚙️')
            self.icon_label.setStyleSheet('font-size: 50px; color: #004b93;')
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.msg = QLabel('처리 중...')
        self.msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.msg.setStyleSheet('font-size: 16px; font-weight: bold; color: #333; margin-top: 10px;')

        f_layout.addStretch()
        f_layout.addWidget(self.icon_label)
        f_layout.addWidget(self.msg)
        f_layout.addStretch()
        self.layout.addStretch()
        self.layout.addWidget(self.bg_frame, 0, Qt.AlignmentFlag.AlignCenter)
        self.layout.addStretch()
        self.hide()

    def start_animation(self, message='처리 중...'):
        self.msg.setText(f'<b>{message}</b>')
        self.show()
        self.setGeometry(self.parent().rect())
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b'opacity')
        self.fade_anim.setDuration(400)
        self.fade_anim.setStartValue(0.7)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.move_anim = QPropertyAnimation(self.bg_frame, b'pos')
        self.move_anim.setDuration(1000)
        center_pos = self.rect().center() - QPoint(self.bg_frame.width() // 2, self.bg_frame.height() // 2)
        self.move_anim.setStartValue(center_pos + QPoint(0, 40))
        self.move_anim.setKeyValueAt(0.2, center_pos - QPoint(0, 10))
        self.move_anim.setKeyValueAt(0.6, center_pos + QPoint(0, 10))
        self.move_anim.setEndValue(center_pos)
        self.move_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self.anim_group = QParallelAnimationGroup()
        self.anim_group.addAnimation(self.fade_anim)
        self.anim_group.addAnimation(self.move_anim)
        self.anim_group.start()

    def stop_animation(self):
        if hasattr(self, 'anim_group'):
            self.anim_group.stop()
        self.hide()
        self.opacity_effect.setOpacity(0.0)


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
        toolbar_layout.setSpacing(8)
        
        # Zoom controls
        self.zoom_in_btn = QPushButton('🔍+')
        self.zoom_in_btn.setObjectName('toolbarBtn')
        self.zoom_in_btn.setFixedSize(30, 30)
        self.zoom_in_btn.setStyleSheet('font-size: 10px;')
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        
        self.zoom_out_btn = QPushButton('🔍-')
        self.zoom_out_btn.setObjectName('toolbarBtn')
        self.zoom_out_btn.setFixedSize(30, 30)
        self.zoom_out_btn.setStyleSheet('font-size: 10px;')
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        
        self.fit_width_btn = QPushButton('너비')
        self.fit_width_btn.setObjectName('toolbarBtn')
        self.fit_width_btn.setFixedHeight(30)
        self.fit_width_btn.setStyleSheet('font-size: 10px;')
        self.fit_width_btn.clicked.connect(self.fit_to_width)
        
        self.fit_page_btn = QPushButton('페이지')
        self.fit_page_btn.setObjectName('toolbarBtn')
        self.fit_page_btn.setFixedHeight(30)
        self.fit_page_btn.setStyleSheet('font-size: 10px;')
        self.fit_page_btn.clicked.connect(self.fit_to_page)
        
        self.zoom_label = QLabel(f'{int(self.scale * 100)}%')
        self.zoom_label.setObjectName('toolbarLabel')
        self.zoom_label.setFixedWidth(50)
        
        # Search controls
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('찾기...')
        self.search_input.setObjectName('toolbarSearch')
        self.search_input.setFixedWidth(150)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_input.returnPressed.connect(self.find_next)
        
        self.find_prev_btn = QPushButton('▲')
        self.find_prev_btn.setObjectName('toolbarBtn')
        self.find_prev_btn.setFixedSize(28, 28)
        self.find_prev_btn.setStyleSheet('font-size: 9px;')
        self.find_prev_btn.clicked.connect(self.find_previous)
        
        self.find_next_btn = QPushButton('▼')
        self.find_next_btn.setObjectName('toolbarBtn')
        self.find_next_btn.setFixedSize(28, 28)
        self.find_next_btn.setStyleSheet('font-size: 9px;')
        self.find_next_btn.clicked.connect(self.find_next)
        
        # Add to toolbar
        toolbar_layout.addWidget(self.zoom_in_btn)
        toolbar_layout.addWidget(self.zoom_out_btn)
        toolbar_layout.addWidget(self.fit_width_btn)
        toolbar_layout.addWidget(self.fit_page_btn)
        toolbar_layout.addWidget(self.zoom_label)
        toolbar_layout.addSpacing(16)
        toolbar_layout.addWidget(self.search_input)
        toolbar_layout.addWidget(self.find_prev_btn)
        toolbar_layout.addWidget(self.find_next_btn)
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
        self.search_results = []
        self.current_search_index = 0
        self.search_highlights = {}
        self.current_highlight = None  # Track current search result highlight
        
        # Add drop zone indicator when empty
        self.drop_label = QLabel('📄 PDF 파일을 여기에 드래그 앤 드랍하세요\n또는 버튼을 클릭하여 파일을 선택하세요')
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet('''
            QLabel {
                color: #8E8E93;
                font-size: 15px;
                font-weight: 500;
                padding: 48px;
                border: 2px dashed #C6C6C8;
                border-radius: 16px;
                background-color: rgba(242, 242, 247, 0.6);
            }
        ''')
        self.vbox.addWidget(self.drop_label)

        self.open_pdf_btn = QPushButton('PDF 선택')
        self.open_pdf_btn.setObjectName('actionBtn')
        self.open_pdf_btn.setFixedHeight(38)
        self.open_pdf_btn.setMinimumWidth(140)
        self.open_pdf_btn.clicked.connect(self.open_pdf_via_dialog)
        self.vbox.addWidget(self.open_pdf_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        
        self.parent_tool = None  # Reference to parent tool for callback

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
                                color: #007AFF;
                                font-size: 15px;
                                font-weight: 500;
                                padding: 48px;
                                border: 2px dashed #007AFF;
                                border-radius: 16px;
                                background-color: rgba(0, 122, 255, 0.06);
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
                    color: #8E8E93;
                    font-size: 15px;
                    font-weight: 500;
                    padding: 48px;
                    border: 2px dashed #C6C6C8;
                    border-radius: 16px;
                    background-color: rgba(242, 242, 247, 0.6);
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
        for i in range(len(self.pdf_doc)):
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
                for bbox, color in self.word_highlights[i]:
                    if bbox:
                        rect = QRect(int(bbox[0] * self.scale), int(bbox[1] * self.scale), int((bbox[2] - bbox[0]) * self.scale), int((bbox[3] - bbox[1]) * self.scale))
                        painter.fillRect(rect, color)
            # Add search highlights in light gray
            if i in self.search_highlights:
                for bbox in self.search_highlights[i]:
                    rect = QRect(int(bbox[0] * self.scale), int(bbox[1] * self.scale), int((bbox[2] - bbox[0]) * self.scale), int((bbox[3] - bbox[1]) * self.scale))
                    painter.fillRect(rect, QColor(200, 200, 200, 30))  # Very light gray background
            # Add current result highlight with border box
            if hasattr(self, 'current_highlights') and i in self.current_highlights:
                for bbox in self.current_highlights[i]:
                    rect = QRect(int(bbox[0] * self.scale), int(bbox[1] * self.scale), int((bbox[2] - bbox[0]) * self.scale), int((bbox[3] - bbox[1]) * self.scale))
                    # Light background
                    painter.fillRect(rect, QColor(220, 220, 220, 40))  # Very light background
                    # Border box
                    painter.setPen(QPen(QColor(100, 100, 100), 2))
                    painter.drawRect(rect)
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
                if not re.match(r'[가-힣a-z0-9]', clean_char):
                    continue
                if not final_norm or not (clean_char == final_norm[-1]['char'] and abs(c['x'] - final_norm[-1]['x']) < 2.5):
                    final_norm.append({'char': clean_char, 'bbox': c['bbox'], 'x': c['x'], 'page': page_num, 'word_id': word_counter})
            raw_lines.append(''.join(line_str_raw))
        self.char_data = final_norm
        self.raw_text = '\n'.join(raw_lines)

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

    def on_search_text_changed(self, text):
        if not text.strip():
            self.clear_search_highlights()
            self.search_results = []
            self.current_search_index = 0
            return

    def search_in_pdf(self, text):
        if not self.pdf_doc or not text.strip():
            return
        self.search_results = []
        for page_num in range(len(self.pdf_doc)):
            page = self.pdf_doc.load_page(page_num)
            text_instances = page.search_for(text)
            for inst in text_instances:
                self.search_results.append((page_num, inst))
        if self.search_results:
            self.highlight_search_results()
            self.current_search_index = 0
            self.go_to_search_result(0)

    def highlight_search_results(self):
        if not self.search_results:
            return
        for page_num, rect in self.search_results:
            if page_num not in self.search_highlights:
                self.search_highlights[page_num] = []
            self.search_highlights[page_num].append(rect)
        self.refresh_highlights()

    def clear_search_highlights(self):
        if hasattr(self, 'search_highlights'):
            self.search_highlights.clear()
        if hasattr(self, 'current_highlights'):
            self.current_highlights.clear()
        self.current_highlight = None
        self.refresh_highlights()

    def find_next(self):
        # If no search results yet, trigger a new search
        if not self.search_results:
            search_text = self.search_input.text().strip()
            if search_text:
                self.clear_search_highlights()  # Clear previous highlights
                self.search_in_pdf(search_text)
            return
        
        if self.search_results:
            self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
            self.go_to_search_result(self.current_search_index)

    def find_previous(self):
        # If no search results yet, trigger a new search
        if not self.search_results:
            search_text = self.search_input.text().strip()
            if search_text:
                self.clear_search_highlights()  # Clear previous highlights
                self.search_in_pdf(search_text)
            return
        
        if self.search_results:
            self.current_search_index = (self.current_search_index - 1) % len(self.search_results)
            self.go_to_search_result(self.current_search_index)

    def go_to_search_result(self, index):
        if 0 <= index < len(self.search_results):
            # Clear previous current highlight
            if self.current_highlight:
                self.remove_current_highlight()
            
            page_num, rect = self.search_results[index]
            # Scroll to the page
            if page_num < len(self.page_labels):
                self.ensureWidgetVisible(self.page_labels[page_num])
                # Highlight current result with orange color
                self.highlight_current_result(page_num, rect)

    def highlight_current_result(self, page_num, rect):
        # Store current highlight info
        self.current_highlight = (page_num, rect)
        
        # Create a separate highlight for current result
        if 'current_highlights' not in self.__dict__:
            self.current_highlights = {}
        if page_num not in self.current_highlights:
            self.current_highlights[page_num] = []
        self.current_highlights[page_num].append(rect)
        
        self.refresh_highlights()

    def remove_current_highlight(self):
        if self.current_highlight and hasattr(self, 'current_highlights'):
            page_num, rect = self.current_highlight
            if page_num in self.current_highlights:
                try:
                    self.current_highlights[page_num].remove(rect)
                    if not self.current_highlights[page_num]:
                        del self.current_highlights[page_num]
                    self.refresh_highlights()
                except ValueError:
                    pass
            self.current_highlight = None
    
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
        self.char_data.clear()
        self.raw_text = ''
        self.pending_selection_rect = None
        self.search_results = []
        self.current_search_index = 0
        self.search_highlights = {}
        self.current_highlight = None
        if hasattr(self, 'current_highlights'):
            self.current_highlights.clear()
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
        workspace = QFrame()
        workspace.setObjectName('workspace')
        workspace_layout = QHBoxLayout(workspace)
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
        self.lbl_name2.setContentsMargins(8, 2, 8, 0)
        
        # Add toolbar
        v2_layout.addWidget(self.viewer2.toolbar)
        v2_layout.addWidget(self.viewer2, 1)
        
        # Bottom controls for PDF 2 (removed - moved to bottom bar)
        workspace_layout.addWidget(v2_panel)
        
        layout.addWidget(workspace, 1)

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

        self.btn_reset_all = QPushButton('🗑  전체 초기화')
        self.btn_reset_all.setObjectName('resetBtn')
        self.btn_reset_all.setFixedHeight(40)
        self.btn_reset_all.setMinimumWidth(120)
        bottom_action_layout.addWidget(self.btn_reset_all)

        layout.addWidget(bottom_action_bar)

        self.loading = LoadingOverlay(self)
        self.last_s1_norm = ''
        self.last_s2_norm = ''
        self.last_s1_raw = ''
        self.last_s2_raw = ''

        self.btn_compare.clicked.connect(self.request_comparison)
        self.btn_reset_all.clicked.connect(self.request_reset_all)
        self.btn_reset_page.clicked.connect(self.request_reset_page)
        self.btn_view_text.clicked.connect(self.show_text_dialog)

    def request_comparison(self):
        if not self.viewer1.char_data or not self.viewer2.char_data:
            QMessageBox.warning(self, '경고', '양쪽 비교 영역을 먼저 드래그해주세요.')
            return
        self.loading.start_animation('비교 분석 중...')
        QApplication.processEvents()
        QTimer.singleShot(100, self.run_comparison)

    def request_reset_all(self):
        self.loading.start_animation('전체 초기화 중...')
        QApplication.processEvents()
        QTimer.singleShot(500, self.reset_all)

    def request_reset_page(self):
        self.loading.start_animation('페이지 초기화 중...')
        QApplication.processEvents()
        QTimer.singleShot(300, self.reset_current_page)

    def reset_all(self):
        try:
            self.viewer1.clear_all_data()
            self.viewer2.clear_all_data()
            self.last_s1_norm = ''
            self.last_s2_norm = ''
        finally:
            self.loading.stop_animation()

    def reset_current_page(self):
        try:
            # Get current visible page for both viewers
            current_page1 = self.get_current_page(self.viewer1)
            current_page2 = self.get_current_page(self.viewer2)
            
            def clear_viewer_current_page(viewer, current_page):
                if current_page is None:
                    return

                if current_page in viewer.last_compared_area:
                    del viewer.last_compared_area[current_page]

                if current_page in viewer.word_highlights:
                    del viewer.word_highlights[current_page]

                if current_page in viewer.search_highlights:
                    del viewer.search_highlights[current_page]

                if hasattr(viewer, 'current_highlights') and current_page in viewer.current_highlights:
                    del viewer.current_highlights[current_page]

                if current_page < len(viewer.page_labels):
                    viewer.page_labels[current_page].clear_selection()

                if viewer.pending_selection_rect and viewer.pending_selection_rect[0] == current_page:
                    viewer.pending_selection_rect = None
                    viewer.char_data.clear()
                    viewer.raw_text = ''

            clear_viewer_current_page(self.viewer1, current_page1)
            clear_viewer_current_page(self.viewer2, current_page2)
            
            # Refresh highlights to update display
            self.viewer1.refresh_highlights()
            self.viewer2.refresh_highlights()
            
        finally:
            self.loading.stop_animation()
    
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

    def run_comparison(self):
        try:
            self.viewer1.last_compared_area.clear()
            self.viewer2.last_compared_area.clear()
            for viewer in [self.viewer1, self.viewer2]:
                if viewer.pending_selection_rect:
                    page_num, rect = viewer.pending_selection_rect
                    viewer.last_compared_area[page_num] = [rect]
            self.last_s1_norm = ''.join([d['char'] for d in self.viewer1.char_data])
            self.last_s2_norm = ''.join([d['char'] for d in self.viewer2.char_data])
            self.last_s1_raw = self.viewer1.raw_text
            self.last_s2_raw = self.viewer2.raw_text
            matcher = SequenceMatcher(None, self.last_s1_norm, self.last_s2_norm, autojunk=False)

            def highlight_entire_word(viewer, start_idx, end_idx, color):
                word_ids = set()
                for i in range(start_idx, end_idx):
                    word_ids.add(viewer.char_data[i]['word_id'])
                for char in viewer.char_data:
                    if char['word_id'] in word_ids:
                        self.add_hl(viewer, char, color)

            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == 'equal':
                    continue
                if tag in ('delete', 'replace'):
                    highlight_entire_word(self.viewer1, i1, i2, COLOR_P1)
                if tag in ('insert', 'replace'):
                    highlight_entire_word(self.viewer2, j1, j2, COLOR_P2)
            for viewer in [self.viewer1, self.viewer2]:
                for lbl in viewer.page_labels:
                    lbl.clear_selection()
                viewer.reload_pages()
        finally:
            self.loading.stop_animation()

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
            f"<span style='color:rgba(255,255,0,0.6); background:rgba(255,255,0,0.3); padding:6px 12px; border-radius:4px; margin-right:10px;'>■</span>"
            f"<b>PDF1 (노란색)</b>: PDF 1에서 삭제되거나 변경된 내용"
            f"</div>"
            f"<div>"
            f"<span style='color:rgba(0,255,127,0.6); background:rgba(0,255,127,0.3); padding:6px 12px; border-radius:4px; margin-right:10px;'>■</span>"
            f"<b>PDF2 (초록색)</b>: PDF 2에서 추가되거나 변경된 내용"
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
            f"<span style='color:rgba(255,255,0,0.6); background:rgba(255,255,0,0.3); padding:6px 12px; border-radius:4px; margin-right:10px;'>■</span>"
            f"<b>PDF1 (노란색)</b>: PDF 1에서 삭제되거나 변경된 내용"
            f"</div>"
            f"<div>"
            f"<span style='color:rgba(0,255,127,0.6); background:rgba(0,255,127,0.3); padding:6px 12px; border-radius:4px; margin-right:10px;'>■</span>"
            f"<b>PDF2 (초록색)</b>: PDF 2에서 추가되거나 변경된 내용"
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

    def resizeEvent(self, event):
        if self.loading.isVisible():
            self.loading.setGeometry(self.rect())
        super().resizeEvent(event)
