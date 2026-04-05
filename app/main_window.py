from functools import partial
 
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMdiArea, QMdiSubWindow, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget
 
from app.common.resources import APP_NAME, COMPANY_NAME, DEVELOPER, ENABLE_INTERNAL_REPORT, ENABLE_LICENSE_MENU, RELEASE_DATE, VERSION, get_icon_path, get_logo_path
from app.common.styles import COLOR_PRIMARY, MODERN_QSS
from app.tools.document_search_ui import DocumentSearchWidget
from app.tools.pdf_header_footer_compare import HFCompareWidget
from app.tools.pdf_compare import PdfCompareWidget


class PlaceholderToolWidget(QWidget):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)
        card = QFrame()
        card.setObjectName('cardFrame')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        title_label = QLabel(f"<b style='font-size:18px; color:{COLOR_PRIMARY};'>{title}</b>")
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet('font-size:13px; color:#555; line-height:1.6;')
        card_layout.addWidget(title_label)
        card_layout.addWidget(message_label)
        card_layout.addStretch()
        layout.addWidget(card)
        layout.addStretch()


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
        
        # MDI area
        self.mdi_area = QMdiArea()
        self.mdi_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mdi_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_panel_layout.addWidget(self.mdi_area, 1)
        
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
            button.setText('' if collapsed else tool_definition['menu_title'])

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
        self.legend_caution_btn.setVisible(tool_key == 'pdf_compare')

    def register_tools(self):
        tool_definitions = [
            {
                'key': DocumentSearchWidget.tool_key,
                'menu_title': DocumentSearchWidget.tool_name,
                'window_title': DocumentSearchWidget.window_title,
                'factory': DocumentSearchWidget,
                'singleton': DocumentSearchWidget.singleton,
                'enabled': DocumentSearchWidget.enabled,
            },
            {
                'key': HFCompareWidget.tool_key,
                'menu_title': '📄 PDF 출력물 비교',
                'window_title': HFCompareWidget.window_title,
                'factory': HFCompareWidget,
                'singleton': HFCompareWidget.singleton,
                'enabled': HFCompareWidget.enabled,
            },
            {
                'key': PdfCompareWidget.tool_key,
                'menu_title': '📄 PDF 지정 영역 비교',
                'window_title': PdfCompareWidget.window_title,
                'factory': PdfCompareWidget,
                'singleton': PdfCompareWidget.singleton,
                'enabled': PdfCompareWidget.enabled,
            },
            {
                'key': 'excel_compare',
                'menu_title': '📊 엑셀 대조',
                'window_title': '엑셀 데이터 대조',
                'factory': lambda: PlaceholderToolWidget('엑셀 데이터 대조', '새 메뉴와 도구 파일을 이 구조에 맞춰 추가하면 됩니다.'),
                'singleton': True,
                'enabled': False,
            },
            {
                'key': 'log_analyzer',
                'menu_title': '🔍 로그 분석',
                'window_title': '로그 분석기',
                'factory': lambda: PlaceholderToolWidget('로그 분석기', '도구 모듈을 추가하고 register_tools에 등록하면 메뉴가 확장됩니다.'),
                'singleton': True,
                'enabled': False,
            },
        ]
        if ENABLE_INTERNAL_REPORT:
            tool_definitions.append(
                {
                    'key': 'internal_report',
                    'menu_title': '🧾 내부 보고서',
                    'window_title': '내부 보고서',
                    'factory': lambda: PlaceholderToolWidget('내부 보고서', f'{APP_NAME} 전용 내부 보고서 기능 자리입니다.'),
                    'singleton': True,
                    'enabled': False,
                }
            )
        if ENABLE_LICENSE_MENU:
            tool_definitions.append(
                {
                    'key': 'license_purchase',
                    'menu_title': '💳 License / Purchase',
                    'window_title': 'License / Purchase',
                    'factory': lambda: PlaceholderToolWidget('License / Purchase', f'{APP_NAME} 상용 배포용 라이선스 메뉴 자리입니다.'),
                    'singleton': True,
                    'enabled': False,
                }
            )
        self.tool_definitions = tool_definitions

    def get_tool_definition(self, tool_key):
        for tool_definition in self.tool_definitions:
            if tool_definition['key'] == tool_key:
                return tool_definition
        return None

    def find_subwindow_by_tool_key(self, tool_key):
        for window in self.mdi_area.subWindowList():
            if window.property('tool_key') == tool_key:
                return window
        return None

    def open_tool(self, tool_key):
        tool_definition = self.get_tool_definition(tool_key)
        if not tool_definition:
            QMessageBox.warning(self, '오류', '선택한 도구 정보를 찾을 수 없습니다.')
            return
        if tool_definition['singleton']:
            existing_window = self.find_subwindow_by_tool_key(tool_key)
            if existing_window:
                self.mdi_area.setActiveSubWindow(existing_window)
                existing_window.showNormal()
                existing_window.raise_()
                self.set_active_sidebar_button(tool_key)
                return

        sub_window = QMdiSubWindow()
        sub_window.setWidget(tool_definition['factory']())
        sub_window.setWindowTitle(tool_definition['window_title'])
        sub_window.setProperty('tool_key', tool_key)
        ico_path = get_icon_path()
        if ico_path:
            sub_window.setWindowIcon(QIcon(ico_path))
        self.mdi_area.addSubWindow(sub_window)
        
        # Calculate size accounting for sidebar
        mdi_width = self.mdi_area.width()
        mdi_height = self.mdi_area.height()
        
        # Maximize within MDI area for pdf_compare and pdf_hf_compare tools
        if tool_key in ['pdf_compare', 'pdf_hf_compare']:
            sub_window.showMaximized()
        else:
            window_width = min(1600, mdi_width - 50)  # Leave some margin
            window_height = min(900, mdi_height - 50)  # Leave some margin
            
            # Center the window in the available MDI area
            x = max(0, (mdi_width - window_width) // 2)
            y = max(0, (mdi_height - window_height) // 2)
            
            sub_window.setGeometry(x, y, window_width, window_height)
            sub_window.show()
        self.mdi_area.setActiveSubWindow(sub_window)
        self.set_active_sidebar_button(tool_key)

    def show_legend_caution_for_active_tool(self):
        # Find the active PDF compare widget
        active_window = self.mdi_area.activeSubWindow()
        if active_window and active_window.property('tool_key') == 'pdf_compare':
            widget = active_window.widget()
            if hasattr(widget, 'show_legend_caution_dialog'):
                widget.show_legend_caution_dialog()

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


def run():
    app = QApplication.instance() or QApplication([])
    app.setFont(QFont('Malgun Gothic', 10))
    window = MdiMainWindow()
    window.show()
    return app.exec()
