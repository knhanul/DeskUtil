from PyQt6.QtGui import QColor
from app.common.resources import THEME_COLOR_PRIMARY

COLOR_PRIMARY = THEME_COLOR_PRIMARY
COLOR_SECONDARY = '#FF6D00'
COLOR_SIDEBAR_BG = '#F8F9FA'
COLOR_HEADER_BG = '#FFFFFF'
COLOR_MDI_BG = '#EBEEF5'
COLOR_WORKSPACE_DARK = '#2E3132'
COLOR_TEXT_PRIMARY = '#333333'
COLOR_TEXT_SECONDARY = '#606266'
COLOR_TEXT_MUTED = '#8C8C8C'
COLOR_BORDER = '#DCDFE6'
COLOR_BORDER_LIGHT = '#EBEEF5'
COLOR_HOVER = '#F2F6FC'
COLOR_ACTIVE = '#E4E7ED'

COLOR_P1 = QColor(255, 255, 0, 140)
COLOR_P2 = QColor(0, 255, 127, 140)
COLOR_AREA = QColor(0, 120, 255, 15)

MODERN_QSS = f"""
QWidget {{
    font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
    font-size: 13px;
    color: {COLOR_TEXT_PRIMARY};
}}

QMainWindow, QDialog {{
    background-color: {COLOR_MDI_BG};
    border: none;
}}

QFrame#sidebar {{
    background-color: {COLOR_SIDEBAR_BG};
    border: none;
}}

QLabel#sidebarBrandTitle {{
    color: {COLOR_PRIMARY};
    font-size: 16px;
    font-weight: 700;
}}

QLabel#sidebarBrandSubtitle {{
    color: {COLOR_TEXT_MUTED};
    font-size: 11px;
}}

QPushButton#sidebarBtn {{
    background-color: transparent;
    border: none;
    border-radius: 10px;
    padding: 12px 14px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 14px;
    font-weight: 500;
    text-align: left;
}}

QPushButton#sidebarBtn:hover {{
    background-color: {COLOR_HOVER};
    color: {COLOR_PRIMARY};
}}

QPushButton#sidebarBtn[active='true'] {{
    background-color: {COLOR_PRIMARY};
    color: {COLOR_HEADER_BG};
}}

QFrame#headerBar {{
    background-color: {COLOR_HEADER_BG};
    border: none;
    border-bottom: 1px solid {COLOR_BORDER_LIGHT};
}}

QLabel#headerTitle {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 16px;
    font-weight: 700;
}}

QLabel#headerTarget {{
    color: {COLOR_TEXT_MUTED};
    font-size: 12px;
}}

QPushButton#hamburgerBtn {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 8px;
    font-size: 18px;
    color: {COLOR_TEXT_PRIMARY};
    min-width: 40px;
    min-height: 40px;
}}

QPushButton#hamburgerBtn:hover {{
    background-color: {COLOR_HOVER};
}}

QPushButton#hamburgerBtn:pressed {{
    background-color: {COLOR_ACTIVE};
}}

QMdiArea {{
    background-color: {COLOR_MDI_BG};
    border: none;
}}

QMdiSubWindow {{
    background-color: {COLOR_HEADER_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
}}

QPushButton {{
    background-color: {COLOR_HEADER_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 8px 16px;
    color: {COLOR_TEXT_SECONDARY};
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {COLOR_HOVER};
    border-color: {COLOR_ACTIVE};
    color: {COLOR_TEXT_PRIMARY};
}}

QPushButton:pressed {{
    background-color: {COLOR_ACTIVE};
}}

QPushButton#actionBtn {{
    background-color: {COLOR_PRIMARY};
    color: {COLOR_HEADER_BG};
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton#actionBtn:hover {{
    background-color: #0056b3;
}}

QPushButton#actionBtn:pressed {{
    background-color: #004b93;
}}

QPushButton#compareBtn {{
    background-color: {COLOR_SECONDARY};
    color: {COLOR_HEADER_BG};
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    min-height: 36px;
    padding: 8px 16px;
}}

QPushButton#compareBtn:hover {{
    background-color: #FF8533;
}}

QPushButton#compareBtn:pressed {{
    background-color: #E66200;
}}

QPushButton#zoomBtn {{
    background-color: {COLOR_WORKSPACE_DARK};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    font-size: 11px;
    color: {COLOR_HEADER_BG};
    padding: 6px 10px;
    min-width: 32px;
    min-height: 28px;
}}

QPushButton#zoomBtn:hover {{
    background-color: #3E4142;
    border-color: {COLOR_SECONDARY};
}}

QFrame#cardFrame, QFrame#toolCard, QFrame#sidebarLogoCard {{
    background-color: {COLOR_HEADER_BG};
    border: 1px solid {COLOR_BORDER_LIGHT};
    border-radius: 10px;
}}

QScrollArea#pdfViewerArea {{
    background-color: {COLOR_WORKSPACE_DARK};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
}}

QScrollArea#pdfViewerArea > QWidget > QWidget {{
    background-color: {COLOR_WORKSPACE_DARK};
}}

QTextEdit {{
    background-color: {COLOR_HEADER_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 12px;
    selection-background-color: {COLOR_PRIMARY};
}}

QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLOR_BORDER};
    min-height: 20px;
    border-radius: 4px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLOR_TEXT_SECONDARY};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    border: none;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 8px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLOR_BORDER};
    min-width: 20px;
    border-radius: 4px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLOR_TEXT_SECONDARY};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    border: none;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

#infoBtn {{
    background: transparent;
    border: none;
    border-radius: 4px;
    font-size: 18px;
    padding: 4px 8px;
    min-width: 32px;
    max-width: 32px;
}}

#infoBtn:hover {{
    background-color: rgba(255, 255, 255, 0.1);
}}

#infoBtn:pressed {{
    background-color: rgba(255, 255, 255, 0.2);
}}

#pdfToolbar {{
    background-color: #F8F9FA;
    border-bottom: 1px solid #E4E7ED;
}}

#toolbarBtn {{
    background: transparent;
    border: 1px solid #DCDFE6;
    border-radius: 4px;
    font-size: 12px;
    padding: 4px;
}}

#toolbarBtn:hover {{
    background-color: rgba(0, 75, 147, 0.1);
    border-color: #004b93;
}}

#toolbarBtn:pressed {{
    background-color: rgba(0, 75, 147, 0.2);
}}

#toolbarLabel {{
    font-size: 12px;
    color: #606266;
    font-weight: bold;
}}

#toolbarSearch {{
    border: 1px solid #DCDFE6;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
    background-color: white;
}}

#toolbarSearch:focus {{
    border-color: #004b93;
}}
"""
