import os
import re
import unicodedata
from difflib import SequenceMatcher

import fitz
from PyQt6.QtCore import QRect, QTimer, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from app.common.styles import COLOR_WORKSPACE_DARK, COLOR_P1, COLOR_P2, COLOR_AREA, MODERN_QSS
from app.tools.pdf_compare import LoadingOverlay
from app.common.pdf_search_helper import PDFSearchHelper


# ──────────────────────────────────────────────────────────
# HeaderFooterLabel : 페이지 렌더링 + 드래그 가능한 Header/Footer 경계선
# ──────────────────────────────────────────────────────────
class HeaderFooterLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_num = -1
        self.header_ratio = 0.0   # 상단 제외 비율 (0 = 제외 없음)
        self.footer_ratio = 0.0   # 하단 제외 비율 (0 = 제외 없음)
        self._dragging_header = False
        self._dragging_footer = False
        self._hit_margin = 8
        self.setMouseTracking(True)
        self.setStyleSheet('border: 0.5px solid #C6C6C8; background-color: white; border-radius: 4px;')
        self.setMargin(0)

    # --- 좌표 계산 ---
    def _image_rect(self):
        pix = self.pixmap()
        if not pix:
            return QRect()
        contents = self.contentsRect()
        x = contents.x() + max(0, (contents.width() - pix.width()) // 2)
        y = contents.y() + max(0, (contents.height() - pix.height()) // 2)
        return QRect(x, y, pix.width(), pix.height())

    def _header_y(self):
        pix = self.pixmap()
        image_rect = self._image_rect()
        return image_rect.y() + int(pix.height() * self.header_ratio) if pix else 0

    def _footer_y(self):
        pix = self.pixmap()
        image_rect = self._image_rect()
        return image_rect.y() + int(pix.height() * (1.0 - self.footer_ratio)) if pix else self.height()

    def _ratio_from_widget_y(self, y):
        image_rect = self._image_rect()
        if image_rect.height() <= 0:
            return 0.0
        local_y = y - image_rect.y()
        return max(0.0, min(1.0, local_y / image_rect.height()))

    # --- 마우스 이벤트 ---
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        y = event.position().toPoint().y()
        if abs(y - self._header_y()) <= self._hit_margin:
            self._dragging_header = True
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            return
        if abs(y - self._footer_y()) <= self._hit_margin:
            self._dragging_footer = True
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        y = event.position().toPoint().y()
        pix = self.pixmap()
        if not pix:
            return super().mouseMoveEvent(event)
        min_gap = 0.05

        if self._dragging_header:
            max_r = max(0.0, 1.0 - self.footer_ratio - min_gap)
            self.header_ratio = max(0.0, min(max_r, self._ratio_from_widget_y(y)))
            self.update()
            return
        if self._dragging_footer:
            max_r = max(0.0, 1.0 - self.header_ratio - min_gap)
            self.footer_ratio = max(0.0, min(max_r, 1.0 - self._ratio_from_widget_y(y)))
            self.update()
            return

        # 커서 변경
        if abs(y - self._header_y()) <= self._hit_margin or abs(y - self._footer_y()) <= self._hit_margin:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging_header or self._dragging_footer:
            self._dragging_header = False
            self._dragging_footer = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            # 부모 뷰어에 변경 알림
            viewer = self.parent()
            while viewer and not isinstance(viewer, HFViewer):
                viewer = viewer.parent()
            if viewer:
                viewer.on_exclusion_changed(self.header_ratio, self.footer_ratio)
            return
        super().mouseReleaseEvent(event)

    # --- 페인트: 제외 영역 오버레이 ---
    def clear_selection(self):
        """Clear selection state - placeholder for compatibility"""
        pass

    def paintEvent(self, event):
        super().paintEvent(event)
        pix = self.pixmap()
        if not pix:
            return
        image_rect = self._image_rect()
        w, h = image_rect.width(), image_rect.height()
        hy = self._header_y()
        fy = self._footer_y()
        painter = QPainter(self)
        # 반투명 어두운 영역
        painter.fillRect(QRect(image_rect.x(), image_rect.y(), w, max(0, hy - image_rect.y())), QColor(0, 0, 0, 90))
        painter.fillRect(QRect(image_rect.x(), fy, w, max(0, image_rect.bottom() + 1 - fy)), QColor(0, 0, 0, 90))
        # 주황색 점선 경계
        pen = QPen(QColor(255, 140, 0), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        if hy > image_rect.y():
            painter.drawLine(image_rect.x(), hy, image_rect.x() + w, hy)
        if fy < image_rect.y() + h:
            painter.drawLine(image_rect.x(), fy, image_rect.x() + w, fy)
        painter.end()


# ──────────────────────────────────────────────────────────
# HFViewer : Header/Footer 제외 기능이 있는 PDF 뷰어
#   - 기존 PDFViewer의 구조를 그대로 따름
#   - 차이: SelectableLabel 대신 HeaderFooterLabel 사용
#   - 텍스트 추출: 전체 페이지, Header/Footer 영역 제외
# ──────────────────────────────────────────────────────────
class HFViewer(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('pdfViewerArea')
        self.setWidgetResizable(True)
        self.setAcceptDrops(True)

        self.scale = 1.5
        self.header_ratio = 0.0
        self.footer_ratio = 0.0
        self.pdf_doc = None
        self.page_labels = []
        self.page_base_pixmaps = []
        self.char_data = []        # 추출된 정규화 문자 데이터
        self.raw_text = ''
        self.word_highlights = {}
        self.last_compared_area = {}
        self.parent_tool = None

        # 툴바
        self.toolbar = QFrame()
        self.toolbar.setObjectName('pdfToolbar')
        self.toolbar.setFixedHeight(40)
        tb = QHBoxLayout(self.toolbar)
        tb.setContentsMargins(8, 4, 8, 4)
        tb.setSpacing(8)

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

        self.fit_page_btn = QPushButton('Página')
        self.fit_page_btn.setObjectName('toolbarBtn')
        self.fit_page_btn.setFixedHeight(30)
        self.fit_page_btn.setStyleSheet('font-size: 10px;')
        self.fit_page_btn.clicked.connect(self.fit_to_page)

        self.zoom_label = QLabel(f'{int(self.scale * 100)}%')
        self.zoom_label.setObjectName('toolbarLabel')
        self.zoom_label.setFixedWidth(50)

        # Initialize search helper
        self.search_helper = PDFSearchHelper(self)
        
        # Setup search UI using helper
        search_input, find_prev_btn, find_next_btn, search_count_label = self.search_helper.setup_search_ui(tb)
        
        # Store references for compatibility
        self.search_input = search_input
        self.find_prev_btn = find_prev_btn
        self.find_next_btn = find_next_btn
        
        # Set Korean UI text
        self.search_helper.set_placeholder_text('Search...')
        self.search_helper.set_button_text('Prev', 'Next')

        tb.addWidget(self.zoom_in_btn)
        tb.addWidget(self.zoom_out_btn)
        tb.addWidget(self.fit_width_btn)
        tb.addWidget(self.fit_page_btn)
        tb.addWidget(self.zoom_label)
        tb.addSpacing(16)
        tb.addStretch()

        # 스크롤 영역
        self.container = QWidget()
        self.vbox = QVBoxLayout(self.container)
        self.vbox.setContentsMargins(20, 20, 20, 20)
        self.vbox.setSpacing(20)
        self.vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.setWidget(self.container)

        self.drop_label = QLabel('📄 PDF 파일을 여기에 드래그 앤 드랍하세요\n또는 버튼을 클릭하여 파일을 선택하세요')
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet(
            'QLabel { color: #8E8E93; font-size: 15px; font-weight: 500; padding: 48px; '
            'border: 2px dashed #C6C6C8; border-radius: 16px; background: rgba(242, 242, 247, 0.6); }'
        )
        self.vbox.addWidget(self.drop_label)

        self.open_pdf_btn = QPushButton('PDF 선택')
        self.open_pdf_btn.setObjectName('actionBtn')
        self.open_pdf_btn.setFixedHeight(38)
        self.open_pdf_btn.setMinimumWidth(140)
        self.open_pdf_btn.clicked.connect(self.open_pdf_via_dialog)
        self.vbox.addWidget(self.open_pdf_btn, 0, Qt.AlignmentFlag.AlignHCenter)

    def set_parent_tool(self, tool):
        self.parent_tool = tool

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

    # PDF loading methods로드 ───
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

    # ─── 드래그 앤 드롭 ───
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith('.pdf'):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith('.pdf'):
                    pdf_path = url.toLocalFile()
                    self.clear_all_data()
                    if self.load_pdf(pdf_path) and self.parent_tool:
                        if self == self.parent_tool.viewer1:
                            self.parent_tool.lbl_name1.setText(
                                f"<b style='color:#007AFF; font-size:15px; font-weight:600;'>[PDF 1] 📄 {os.path.basename(pdf_path)}</b>")
                        elif self == self.parent_tool.viewer2:
                            self.parent_tool.lbl_name2.setText(
                                f"<b style='color:#007AFF; font-size:15px; font-weight:600;'>[PDF 2] 📄 {os.path.basename(pdf_path)}</b>")
                    event.acceptProposedAction()
                    return
        event.ignore()

    # ─── 페이지 렌더링 ───
    def reload_pages(self):
        if not self.pdf_doc:
            return
        # 기존 비율 보존
        if self.page_labels:
            self.header_ratio = self.page_labels[0].header_ratio
            self.footer_ratio = self.page_labels[0].footer_ratio
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
            lbl = HeaderFooterLabel(self.container)
            lbl.page_num = i
            lbl.header_ratio = self.header_ratio
            lbl.footer_ratio = self.footer_ratio
            lbl.setPixmap(base_pixmap.copy())
            self.vbox.addWidget(lbl)
            self.page_labels.append(lbl)
            self.page_base_pixmaps.append(base_pixmap)
        self.refresh_highlights()

    # ─── Header/Footer 변경 콜백 ───
    def on_exclusion_changed(self, header_ratio, footer_ratio):
        """Header/Footer 변경 - 각 뷰어 독립적으로 조절"""
        self.header_ratio = header_ratio
        self.footer_ratio = footer_ratio
        for lbl in self.page_labels:
            lbl.header_ratio = header_ratio
            lbl.footer_ratio = footer_ratio
            lbl.update()
        # 동기화 제거: 각 뷰어는 독립적으로 조절

    # ─── 하이라이트 ───
    def refresh_highlights(self):
        for i, lbl in enumerate(self.page_labels):
            if i >= len(self.page_base_pixmaps):
                continue
            img = self.page_base_pixmaps[i].toImage().copy()
            painter = QPainter(img)
            if i in self.last_compared_area:
                for bbox in self.last_compared_area[i]:
                    rect = QRect(int(bbox[0] * self.scale), int(bbox[1] * self.scale),
                                 int((bbox[2] - bbox[0]) * self.scale), int((bbox[3] - bbox[1]) * self.scale))
                    painter.fillRect(rect, COLOR_AREA)
            if i in self.word_highlights:
                for bbox, color in self.word_highlights[i]:
                    rect = QRect(int(bbox[0] * self.scale), int(bbox[1] * self.scale),
                                 int((bbox[2] - bbox[0]) * self.scale), int((bbox[3] - bbox[1]) * self.scale))
                    painter.fillRect(rect, color)
            # Use search helper for search highlights
            self.search_helper.render_search_highlights(painter, i, self.scale)
            painter.end()
            lbl.setPixmap(QPixmap.fromImage(img))

    # ─── 텍스트 추출 (기존 extract_and_process_text 와 동일한 로직) ───
    def extract_body_text(self):
        """모든 페이지에서 Header/Footer를 제외한 본문 텍스트를 추출"""
        self.char_data = []
        self.raw_text = ''
        if not self.pdf_doc:
            return
        all_raw_chars = []
        for page_num in range(len(self.pdf_doc)):
            page = self.pdf_doc.load_page(page_num)
            page_h = page.rect.height
            h1 = page_h * self.header_ratio        # 상단 제외 경계
            h2 = page_h * (1.0 - self.footer_ratio)  # 하단 제외 경계
            raw_dict = page.get_text('rawdict')
            for block in raw_dict.get('blocks', []):
                if block.get('type') != 0:
                    continue
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        for char in span.get('chars', []):
                            c = char['c']
                            bbox = char['bbox']
                            # Header/Footer 영역 제외
                            if bbox[3] <= h1 or bbox[1] >= h2:
                                continue
                            c_norm = unicodedata.normalize('NFC', c)
                            all_raw_chars.append({
                                'char': c_norm, 'bbox': bbox,
                                'y': bbox[1], 'x': bbox[0], 'page': page_num
                            })

        if not all_raw_chars:
            return

        # Y좌표 기준 라인 그룹핑 (기존 로직 동일)
        all_raw_chars.sort(key=lambda c: (c['page'], c['y']))
        grouped = []
        curr = [all_raw_chars[0]]
        for i in range(1, len(all_raw_chars)):
            same_page = all_raw_chars[i]['page'] == curr[-1]['page']
            close_y = abs(all_raw_chars[i]['y'] - curr[-1]['y']) < 5.0
            if same_page and close_y:
                curr.append(all_raw_chars[i])
            else:
                grouped.append(curr)
                curr = [all_raw_chars[i]]
        grouped.append(curr)

        # 정규화 + word_id 부여 (기존 로직 동일)
        final_norm = []
        raw_lines = []
        word_counter = 0
        for line in grouped:
            line.sort(key=lambda c: c['x'])
            line_str_raw = []
            word_counter += 1
            page_num = line[0]['page']
            for i, c in enumerate(line):
                line_str_raw.append(c['char'])
                if i > 0 and (line[i - 1]['char'].strip() == '' or abs(c['x'] - line[i - 1]['bbox'][2]) > 2.5):
                    word_counter += 1
                clean_char = c['char'].lower().strip()
                if not re.match(r'[가-힣a-z0-9]', clean_char):
                    continue
                if not final_norm or not (clean_char == final_norm[-1]['char'] and abs(c['x'] - final_norm[-1]['x']) < 2.5):
                    final_norm.append({
                        'char': clean_char, 'bbox': c['bbox'],
                        'x': c['x'], 'page': page_num, 'word_id': word_counter
                    })
            raw_lines.append(''.join(line_str_raw))
        self.char_data = final_norm
        self.raw_text = '\n'.join(raw_lines)

    # ─── 줌 ───
    def zoom_in(self):
        self.scale *= 1.2
        self.zoom_label.setText(f'{int(self.scale * 100)}%')
        self.reload_pages()

    def zoom_out(self):
        self.scale /= 1.2
        self.zoom_label.setText(f'{int(self.scale * 100)}%')
        self.reload_pages()

    def fit_to_width(self):
        if not self.pdf_doc or len(self.pdf_doc) == 0:
            return
        pw = self.pdf_doc.load_page(0).rect.width
        self.scale = max(100, self.viewport().width() - 40) / pw
        self.zoom_label.setText(f'{int(self.scale * 100)}%')
        self.reload_pages()

    def fit_to_page(self):
        if not self.pdf_doc or len(self.pdf_doc) == 0:
            return
        r = self.pdf_doc.load_page(0).rect
        sw = max(100, self.viewport().width() - 40) / r.width
        sh = max(100, self.viewport().height() - 40) / r.height
        self.scale = min(sw, sh)
        self.zoom_label.setText(f'{int(self.scale * 100)}%')
        self.reload_pages()

    # ─── 초기화 ───
    def clear_all_data(self):
        self.word_highlights.clear()
        self.last_compared_area.clear()
        self.char_data.clear()
        self.raw_text = ''
        self.search_helper.clear_all_search_data()
        for lbl in self.page_labels:
            lbl.clear_selection()
        if hasattr(self, 'drop_label'):
            self.drop_label.show()
        if hasattr(self, 'open_pdf_btn'):
            self.open_pdf_btn.show()
        self.refresh_highlights()

    def get_scroll_anchor(self):
        """Convert current scroll position to (page, y) anchor"""
        if not self.page_labels:
            return None
        scroll_y = self.verticalScrollBar().value()
        current_y = 0
        for page_num, lbl in enumerate(self.page_labels):
            page_height = lbl.height() + self.vbox.spacing()
            if current_y + page_height > scroll_y:
                relative_y = max(0.0, (scroll_y - current_y) / max(self.scale, 0.0001))
                return (page_num, relative_y)
            current_y += page_height
        last_page = len(self.page_labels) - 1
        if last_page >= 0:
            return (last_page, 0.0)
        return None

    def scroll_to_anchor(self, anchor):
        """Immediately scroll to (page, y) anchor position"""
        if not anchor:
            return
        page_num, y_pos = anchor
        target_y = 0
        for i in range(min(page_num, len(self.page_labels))):
            target_y += self.page_labels[i].height() + self.vbox.spacing()
        target_y += int(y_pos * self.scale) - 80
        self.verticalScrollBar().setValue(max(0, target_y))


# ──────────────────────────────────────────────────────────
# HFCompareWidget : 메인 비교 위젯 (MDI에 등록)
# ──────────────────────────────────────────────────────────
class HFCompareWidget(QWidget):
    tool_key = 'pdf_hf_compare'
    tool_name = '📄 Header/Footer 제외 비교'
    window_title = 'PDF 출력물 비교'
    singleton = True
    enabled = True

    def __init__(self, parent=None):
        super().__init__(parent)
        self._syncing = False
        self.loading = LoadingOverlay(self)
        self.last_s1_norm = ''
        self.last_s2_norm = ''
        self.last_s1_raw = ''
        self.last_s2_raw = ''
        self.sync_anchor_pairs = []
        self._build_ui()

    # ─── UI 구성 ───
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(5)
        root.setContentsMargins(10, 0, 10, 10)

        workspace = QFrame()
        workspace.setObjectName('workspace')
        ws = QHBoxLayout(workspace)
        ws.setContentsMargins(0, 0, 0, 0)
        ws.setSpacing(16)

        # PDF 1
        p1 = QFrame(); p1.setObjectName('pdfPanel')
        l1 = QVBoxLayout(p1); l1.setContentsMargins(0, 0, 0, 0); l1.setSpacing(0)
        self.viewer1 = HFViewer()
        self.viewer1.set_parent_tool(self)
        self.lbl_name1 = QLabel("<b style='color:#007AFF; font-size:15px; font-weight:600;'>[PDF 1]</b>")
        self.lbl_name1.setContentsMargins(10, 6, 10, 4)
        l1.addWidget(self.lbl_name1)
        l1.addWidget(self.viewer1.toolbar)
        l1.addWidget(self.viewer1, 1)
        ws.addWidget(p1)

        # PDF 2
        p2 = QFrame(); p2.setObjectName('pdfPanel')
        l2 = QVBoxLayout(p2); l2.setContentsMargins(0, 0, 0, 0); l2.setSpacing(0)
        self.viewer2 = HFViewer()
        self.viewer2.set_parent_tool(self)
        self.lbl_name2 = QLabel("<b style='color:#007AFF; font-size:15px; font-weight:600;'>[PDF 2]</b>")
        self.lbl_name2.setContentsMargins(10, 6, 10, 4)
        l2.addWidget(self.lbl_name2)
        l2.addWidget(self.viewer2.toolbar)
        l2.addWidget(self.viewer2, 1)
        ws.addWidget(p2)

        root.addWidget(workspace, 1)

        # 하단 액션 바
        bar = QFrame()
        bar.setObjectName('actionBar')
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 8, 12, 8)
        bl.setSpacing(10)

        # 동시 스크롤 체크박스
        self.sync_scroll_cb = QCheckBox('동시 스크롤')
        self.sync_scroll_cb.setObjectName('actionCheckBox')
        self.sync_scroll_cb.setChecked(False)
        self.sync_scroll_cb.toggled.connect(self.toggle_sync_scroll)
        self.sync_scroll_enabled = False
        bl.addWidget(self.sync_scroll_cb)

        bl.addStretch()

        self.btn_compare = QPushButton('⚡  비교 실행')
        self.btn_compare.setObjectName('compareBtn')
        self.btn_compare.setFixedHeight(42)
        self.btn_compare.setMinimumWidth(150)
        self.btn_compare.clicked.connect(self.request_comparison)
        bl.addWidget(self.btn_compare)

        bl.addStretch()

        self.btn_reset = QPushButton('🗑  전체 초기화')
        self.btn_reset.setObjectName('resetBtn')
        self.btn_reset.setFixedHeight(40)
        self.btn_reset.setMinimumWidth(120)
        self.btn_reset.clicked.connect(self.request_reset)
        bl.addWidget(self.btn_reset)

        root.addWidget(bar)

        # 스크롤 동기화
        self.viewer1.verticalScrollBar().valueChanged.connect(self._sync1)
        self.viewer2.verticalScrollBar().valueChanged.connect(self._sync2)

    def _sync1(self, v):
        """viewer1 스크롤 시 viewer2 동기화"""
        if not self._syncing and self.sync_scroll_enabled:
            self._syncing = True
            target_anchor = self._find_partner_anchor(self.viewer1.get_scroll_anchor(), source_index=0)
            if target_anchor:
                self.viewer2.scroll_to_anchor(target_anchor)
            self._syncing = False

    def _sync2(self, v):
        """viewer2 스크롤 시 viewer1 동기화"""
        if not self._syncing and self.sync_scroll_enabled:
            self._syncing = True
            target_anchor = self._find_partner_anchor(self.viewer2.get_scroll_anchor(), source_index=1)
            if target_anchor:
                self.viewer1.scroll_to_anchor(target_anchor)
            self._syncing = False

    def toggle_sync_scroll(self, checked):
        """동시 스크롤 토글"""
        self.sync_scroll_enabled = checked

    def _find_partner_anchor(self, source_anchor, source_index):
        """현재 뷰어 앵커와 가장 가까운 비교 쌍을 찾아 반대편 앵커 반환"""
        if not source_anchor or not self.sync_anchor_pairs:
            return None
        src_page, src_y = source_anchor
        best_distance = None
        best_target = None
        for left_anchor, right_anchor in self.sync_anchor_pairs:
            candidate = left_anchor if source_index == 0 else right_anchor
            target = right_anchor if source_index == 0 else left_anchor
            if candidate is None or target is None:
                continue
            cand_page, cand_y = candidate
            page_distance = abs(cand_page - src_page) * 100000
            y_distance = abs(cand_y - src_y)
            distance = page_distance + y_distance
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_target = target
        return best_target

    def _build_anchor_from_range(self, viewer, start_idx, end_idx):
        """char_data 범위로부터 (page, y) 앵커 생성"""
        if start_idx >= end_idx or start_idx < 0 or end_idx > len(viewer.char_data):
            return None
        chars = viewer.char_data[start_idx:end_idx]
        if not chars:
            return None
        page_num = chars[0]['page']
        same_page_chars = [ch for ch in chars if ch['page'] == page_num]
        if not same_page_chars:
            same_page_chars = chars
        y_values = [((ch['bbox'][1] + ch['bbox'][3]) / 2) for ch in same_page_chars]
        if not y_values:
            return None
        return (page_num, sum(y_values) / len(y_values))

    def _build_page_bboxes_from_range(self, viewer, start_idx, end_idx):
        """char_data 범위를 페이지별 union bbox로 변환"""
        if start_idx >= end_idx or start_idx < 0 or end_idx > len(viewer.char_data):
            return {}
        page_boxes = {}
        for ch in viewer.char_data[start_idx:end_idx]:
            page_num = ch['page']
            x0, y0, x1, y1 = ch['bbox']
            if page_num not in page_boxes:
                page_boxes[page_num] = [x0, y0, x1, y1]
            else:
                page_boxes[page_num][0] = min(page_boxes[page_num][0], x0)
                page_boxes[page_num][1] = min(page_boxes[page_num][1], y0)
                page_boxes[page_num][2] = max(page_boxes[page_num][2], x1)
                page_boxes[page_num][3] = max(page_boxes[page_num][3], y1)
        return {page: tuple(bbox) for page, bbox in page_boxes.items()}

    def _append_compared_area(self, viewer, start_idx, end_idx):
        """비교된 실제 문자 영역을 last_compared_area에 누적"""
        page_boxes = self._build_page_bboxes_from_range(viewer, start_idx, end_idx)
        for page_num, bbox in page_boxes.items():
            if page_num not in viewer.last_compared_area:
                viewer.last_compared_area[page_num] = []
            viewer.last_compared_area[page_num].append(bbox)

    # ─── 비교 요청 ───
    def request_comparison(self):
        if not self.viewer1.pdf_doc or not self.viewer2.pdf_doc:
            QMessageBox.warning(self, '경고', '양쪽 PDF를 먼저 로드해주세요.')
            return
        self.loading.start_animation('비교 분석 중...')
        QApplication.processEvents()
        QTimer.singleShot(100, self.run_comparison)

    # ─── 비교 실행 (기존 run_comparison과 동일한 SequenceMatcher + 단어 하이라이트) ───
    def run_comparison(self):
        try:
            # 1) 텍스트 추출
            self.viewer1.extract_body_text()
            self.viewer2.extract_body_text()

            if not self.viewer1.char_data and not self.viewer2.char_data:
                QMessageBox.information(self, '안내', '추출된 텍스트가 없습니다. Header/Footer 제외 범위를 확인해주세요.')
                return

            # 2) 하이라이트 초기화
            self.viewer1.word_highlights.clear()
            self.viewer2.word_highlights.clear()
            self.viewer1.last_compared_area.clear()
            self.viewer2.last_compared_area.clear()
            self.sync_anchor_pairs = []

            # 3) 정규화 문자열
            self.last_s1_norm = ''.join(d['char'] for d in self.viewer1.char_data)
            self.last_s2_norm = ''.join(d['char'] for d in self.viewer2.char_data)
            self.last_s1_raw = self.viewer1.raw_text
            self.last_s2_raw = self.viewer2.raw_text

            # 4) SequenceMatcher 비교
            matcher = SequenceMatcher(None, self.last_s1_norm, self.last_s2_norm, autojunk=False)

            diff_pages1 = []
            diff_pages2 = []

            def highlight_entire_word(viewer, start_idx, end_idx, color, diff_pages):
                word_ids = set()
                for i in range(start_idx, end_idx):
                    word_ids.add(viewer.char_data[i]['word_id'])
                for ch in viewer.char_data:
                    if ch['word_id'] in word_ids:
                        self._add_hl(viewer, ch, color)
                        y_center = (ch['bbox'][1] + ch['bbox'][3]) / 2
                        diff_pages.append((ch['page'], y_center))

            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                left_anchor = self._build_anchor_from_range(self.viewer1, i1, i2)
                right_anchor = self._build_anchor_from_range(self.viewer2, j1, j2)
                if left_anchor or right_anchor:
                    self.sync_anchor_pairs.append((left_anchor, right_anchor))
                if tag == 'equal':
                    continue
                if tag in ('delete', 'replace'):
                    self._append_compared_area(self.viewer1, i1, i2)
                if tag in ('insert', 'replace'):
                    self._append_compared_area(self.viewer2, j1, j2)
                if tag in ('delete', 'replace'):
                    highlight_entire_word(self.viewer1, i1, i2, COLOR_P1, diff_pages1)
                if tag in ('insert', 'replace'):
                    highlight_entire_word(self.viewer2, j1, j2, COLOR_P2, diff_pages2)

            # 5) Store difference locations
            self.viewer1.diff_pages = sorted(set(diff_pages1))
            self.viewer2.diff_pages = sorted(set(diff_pages2))
            self.viewer1.diff_index = -1
            self.viewer2.diff_index = -1

            # 6) Refresh highlights
            self.viewer1.reload_pages()
            self.viewer2.reload_pages()

            total = len(self.viewer1.diff_pages) + len(self.viewer2.diff_pages)
            QMessageBox.information(self, 'Comparison Complete', f'Found {total} difference locations.')
        finally:
            self.loading.stop_animation()

    def _add_hl(self, viewer, info, color):
        page_num = info['page']
        if page_num not in viewer.word_highlights:
            viewer.word_highlights[page_num] = []
        if not any(h[0] == info['bbox'] and h[1] == color for h in viewer.word_highlights[page_num]):
            viewer.word_highlights[page_num].append((info['bbox'], color))

    # Reset methods
    def request_reset(self):
        self.loading.start_animation('Resetting all data...')
        QApplication.processEvents()
        QTimer.singleShot(300, self._do_reset)

    def _do_reset(self):
        try:
            self.viewer1.clear_all_data()
            self.viewer2.clear_all_data()
            self.last_s1_norm = ''
            self.last_s2_norm = ''
            self.sync_anchor_pairs = []
        finally:
            self.loading.stop_animation()

    def resizeEvent(self, event):
        if self.loading.isVisible():
            self.loading.setGeometry(self.rect())
        super().resizeEvent(event)
