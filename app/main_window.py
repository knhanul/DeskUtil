from functools import partial
 
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget
 
from app.common.resources import APP_NAME, COMPANY_NAME, DEVELOPER, RELEASE_DATE, VERSION, get_icon_path, get_logo_path
from app.common.styles import COLOR_PRIMARY, MODERN_QSS
from app.tools.dual_pane_manager import DualPaneManager
from app.tools.document_search_ui import DocumentSearchWidget
from app.tools.pdf_header_footer_compare import HFCompareWidget
from app.tools.pdf_compare import PdfCompareWidget


class MdiMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'{APP_NAME} v{VERSION}')
        self.setGeometry(50, 50, 1700, 1000)
        self.setStyleSheet(MODERN_QSS)

        ico_path = get_icon_path()
        if ico_path:
            self.setWindowIcon(QIcon(ico_path))

        self.main_widget = QWidget()
        self.main_layout = QHBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setCentralWidget(self.main_widget)

        self.sidebar_expanded_width = 220
        self.sidebar_collapsed_width = 68
        self.sidebar_width = self.sidebar_expanded_width
        self.sidebar_buttons = []
        self.tool_definitions = []
        self.current_tool_widget = None
        self.current_tool_key = None
        self.tool_cache = {}  # Cache for tool widgets

        # Blink animation for legend caution button
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_button_blink)
        self.blink_state = False

        self.sidebar = self.create_sidebar()
        self.main_layout.addWidget(self.sidebar)

        self.right_panel = self.create_right_panel()
        self.main_layout.addWidget(self.right_panel, 1)

        self.sidebar_animation = QPropertyAnimation(self.sidebar, b'minimumWidth')
        self.sidebar_animation.setDuration(250)
        self.sidebar_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.sidebar_animation.valueChanged.connect(self.sync_sidebar_width)
        self.sidebar_animation.finished.connect(lambda: self.apply_sidebar_collapsed_state(self.sidebar_width == self.sidebar_collapsed_width))

        self.register_tools()
        self.populate_sidebar_buttons()
        self.open_tool('pdf_compare')

    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setMinimumWidth(self.sidebar_expanded_width)
        sidebar.setMaximumWidth(self.sidebar_expanded_width)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 18, 12, 18)
        sidebar_layout.setSpacing(10)

        logo_card = QFrame()
        logo_card.setObjectName('sidebarLogoCard')
        logo_layout = QVBoxLayout(logo_card)
        logo_layout.setContentsMargins(12, 12, 12, 12)
        logo_layout.setSpacing(6)
        self.sidebar_logo = QLabel()
        self.sidebar_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = get_logo_path()
        if logo_path:
            self.sidebar_logo.setPixmap(QPixmap(logo_path).scaled(144, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.sidebar_brand_title = QLabel(APP_NAME)
        self.sidebar_brand_title.setObjectName('sidebarBrandTitle')
        self.sidebar_brand_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_brand_subtitle = QLabel(COMPANY_NAME)
        self.sidebar_brand_subtitle.setObjectName('sidebarBrandSubtitle')
        self.sidebar_brand_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(self.sidebar_logo)
        logo_layout.addWidget(self.sidebar_brand_title)
        logo_layout.addWidget(self.sidebar_brand_subtitle)
        sidebar_layout.addWidget(logo_card)

        self.sidebar_button_host = QVBoxLayout()
        self.sidebar_button_host.setSpacing(6)
        sidebar_layout.addLayout(self.sidebar_button_host)
        sidebar_layout.addStretch()
        return sidebar

    def create_right_panel(self):
        right_panel = QWidget()
        right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(0)
        
        # Header bar
        self.header_bar = self.create_header_bar()
        right_panel_layout.addWidget(self.header_bar)
        
        # Tool container (replaces MDI area)
        self.tool_container = QWidget()
        self.tool_container_layout = QVBoxLayout(self.tool_container)
        self.tool_container_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.addWidget(self.tool_container, 1)
        
        return right_panel

    def create_header_bar(self):
        header = QFrame()
        header.setObjectName('headerBar')
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        self.hamburger_btn = QPushButton('☰')
        self.hamburger_btn.setObjectName('hamburgerBtn')
        self.hamburger_btn.clicked.connect(self.toggle_sidebar)
        header_layout.addWidget(self.hamburger_btn)
        header_layout.addSpacing(16)

        self.header_title = QLabel(APP_NAME)
        self.header_title.setObjectName('headerTitle')
        header_layout.addWidget(self.header_title)
        header_layout.addSpacing(10)
        self.header_target = QLabel(COMPANY_NAME)
        self.header_target.setObjectName('headerTarget')
        header_layout.addWidget(self.header_target)
        header_layout.addStretch()

        version_label = QLabel(f'v{VERSION}')
        version_label.setObjectName('headerTarget')
        header_layout.addWidget(version_label)
        header_layout.addSpacing(8)
        self.legend_caution_btn = QPushButton('📋 범례 및 주의사항')
        self.legend_caution_btn.setObjectName('actionBtn')
        self.legend_caution_btn.setVisible(False)  # Initially hidden
        self.legend_caution_btn.clicked.connect(self.show_legend_caution_for_active_tool)
        header_layout.addWidget(self.legend_caution_btn)
        header_layout.addSpacing(8)
        self.info_btn = QPushButton('ℹ️')
        self.info_btn.setObjectName('infoBtn')
        self.info_btn.clicked.connect(self.show_info)
        header_layout.addWidget(self.info_btn)
        return header

    def toggle_sidebar(self):
        if self.sidebar_width == self.sidebar_expanded_width:
            self.sidebar_width = self.sidebar_collapsed_width
            self.sidebar_animation.stop()
            self.sidebar_animation.setStartValue(self.sidebar.width())
            self.sidebar_animation.setEndValue(self.sidebar_collapsed_width)
            self.sidebar_animation.start()
        else:
            self.sidebar_width = self.sidebar_expanded_width
            self.sidebar_animation.stop()
            self.sidebar_animation.setStartValue(self.sidebar.width())
            self.sidebar_animation.setEndValue(self.sidebar_expanded_width)
            self.sidebar_animation.start()

    def sync_sidebar_width(self, value):
        width = int(value)
        self.sidebar.setMinimumWidth(width)
        self.sidebar.setMaximumWidth(width)

    def apply_sidebar_collapsed_state(self, collapsed):
        self.sidebar_logo.setVisible(not collapsed)
        self.sidebar_brand_title.setVisible(not collapsed)
        self.sidebar_brand_subtitle.setVisible(not collapsed)
        for tool_definition, button in zip(self.tool_definitions, self.sidebar_buttons):
            button.setProperty('collapsed', collapsed)
            if collapsed:
                # Use icon property for collapsed state
                icon = tool_definition.get('icon', '📄')
                button.setText(icon)
                button.setMinimumHeight(50)
                button.setMaximumHeight(50)
            else:
                button.setText(tool_definition['menu_title'])
                button.setMinimumHeight(0)
                button.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            button.style().unpolish(button)
            button.style().polish(button)

    def populate_sidebar_buttons(self):
        while self.sidebar_button_host.count():
            item = self.sidebar_button_host.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.sidebar_buttons = []
        for tool_definition in self.tool_definitions:
            button = QPushButton(tool_definition['menu_title'])
            button.setObjectName('sidebarBtn')
            button.setEnabled(tool_definition['enabled'])
            button.setProperty('active', False)
            if tool_definition['enabled']:
                button.clicked.connect(partial(self.open_tool, tool_definition['key']))
            self.sidebar_button_host.addWidget(button)
            self.sidebar_buttons.append(button)
        self.apply_sidebar_collapsed_state(self.sidebar_width == self.sidebar_collapsed_width)

    def set_active_sidebar_button(self, tool_key):
        for tool_definition, button in zip(self.tool_definitions, self.sidebar_buttons):
            button.setProperty('active', tool_definition['key'] == tool_key)
            button.style().unpolish(button)
            button.style().polish(button)
        
        # Show/hide legend caution button based on active tool
        should_show = tool_key in ('pdf_compare', 'pdf_hf_compare')
        self.legend_caution_btn.setVisible(should_show)
        if should_show:
            self.start_button_blinking()
        else:
            self.stop_button_blinking()

    def start_button_blinking(self):
        self.blink_state = False
        self.blink_timer.start(500)  # Blink every 500ms

    def stop_button_blinking(self):
        self.blink_timer.stop()
        self.legend_caution_btn.setStyleSheet('')  # Reset to default style

    def toggle_button_blink(self):
        self.blink_state = not self.blink_state
        if self.blink_state:
            self.legend_caution_btn.setStyleSheet('QPushButton#actionBtn { background-color: #FFA500; color: white; }')
        else:
            self.legend_caution_btn.setStyleSheet('')

    def register_tools(self):
        tool_definitions = [
            {
                'key': PdfCompareWidget.tool_key,
                'menu_title': '📄 PDF 지정 영역 비교',
                'window_title': PdfCompareWidget.window_title,
                'factory': PdfCompareWidget,
                'singleton': PdfCompareWidget.singleton,
                'enabled': PdfCompareWidget.enabled,
                'icon': '📄',
            },
            {
                'key': HFCompareWidget.tool_key,
                'menu_title': '📄 PDF 출력물 비교',
                'window_title': HFCompareWidget.window_title,
                'factory': HFCompareWidget,
                'singleton': HFCompareWidget.singleton,
                'enabled': HFCompareWidget.enabled,
                'icon': '📄',
            },
            {
                'key': DualPaneManager.tool_key,
                'menu_title': DualPaneManager.tool_name,
                'window_title': DualPaneManager.window_title,
                'factory': DualPaneManager,
                'singleton': DualPaneManager.singleton,
                'enabled': DualPaneManager.enabled,
                'icon': '🗂️',
            },
            {
                'key': DocumentSearchWidget.tool_key,
                'menu_title': DocumentSearchWidget.tool_name,
                'window_title': DocumentSearchWidget.window_title,
                'factory': DocumentSearchWidget,
                'singleton': DocumentSearchWidget.singleton,
                'enabled': DocumentSearchWidget.enabled,
                'icon': '🔍',
            },
        ]
        self.tool_definitions = tool_definitions

    def get_tool_definition(self, tool_key):
        for tool_definition in self.tool_definitions:
            if tool_definition['key'] == tool_key:
                return tool_definition
        return None

    def open_tool(self, tool_key):
        tool_definition = self.get_tool_definition(tool_key)
        if not tool_definition:
            QMessageBox.warning(self, 'Error', 'Selected tool information not found.')
            return
        
        # If the same tool is already active, do nothing
        if self.current_tool_key == tool_key:
            return
        
        # Hide current tool if exists - trigger closeEvent for thread cleanup
        if self.current_tool_widget:
            # close()를 호출하여 closeEvent가 실행되도록 함 (스레드 정리)
            self.current_tool_widget.close()
            self.current_tool_widget.hide()
        
        # Get or create tool widget from cache
        if tool_key not in self.tool_cache:
            new_tool = tool_definition['factory']()
            self.tool_cache[tool_key] = new_tool
            self.tool_container_layout.addWidget(new_tool)
        else:
            new_tool = self.tool_cache[tool_key]
        
        # Show the new tool
        new_tool.show()
        self.current_tool_widget = new_tool
        self.current_tool_key = tool_key
        
        # Update header and sidebar
        self.header_title.setText(tool_definition['window_title'])
        self.set_active_sidebar_button(tool_key)

    def show_legend_caution_for_active_tool(self):
        # Find the active PDF compare widget
        if self.current_tool_key in ('pdf_compare', 'pdf_hf_compare') and self.current_tool_widget:
            if hasattr(self.current_tool_widget, 'show_legend_caution_dialog'):
                self.current_tool_widget.show_legend_caution_dialog()

    def show_info(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('프로그램 정보')
        dialog.setFixedSize(420, 320)
        dialog.setStyleSheet(MODERN_QSS)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 30, 30, 30)
        img_path = get_logo_path()
        if img_path:
            image = QLabel()
            image.setPixmap(QPixmap(img_path).scaled(200, 80, Qt.AspectRatioMode.KeepAspectRatio))
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(image)
        text = QLabel(f"<div style='text-align:center;'><h2 style='color:{COLOR_PRIMARY}; margin-bottom:5px;'>{APP_NAME}</h2><span style='color:#777;'>v{VERSION}</span><br><br><b>배포일:</b> {RELEASE_DATE}<br><b>제작:</b> {DEVELOPER}</div>")
        layout.addWidget(text)
        button = QPushButton('확인')
        button.setObjectName('actionBtn')
        button.setFixedHeight(38)
        button.clicked.connect(dialog.accept)
        layout.addStretch()
        layout.addWidget(button)
        dialog.exec()

    def closeEvent(self, event):
        """애플리케이션 종료 시 모든 스레드 정리 (좀비 프로세스 방지)"""
        # 현재 활성화된 도구의 스레드 정리
        if self.current_tool_widget:
            self.current_tool_widget.close()
        
        # 캐시된 모든 도구 위젯의 스레드 정리
        for tool_widget in self.tool_cache.values():
            tool_widget.close()
        
        # 이벤트 수락 (창 닫기 진행)
        event.accept()


def run():
    app = QApplication.instance() or QApplication([])
    app.setFont(QFont('Malgun Gothic', 10))
    window = MdiMainWindow()
    window.show()
    return app.exec()
