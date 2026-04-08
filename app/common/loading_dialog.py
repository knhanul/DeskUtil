import os
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QMovie
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QApplication
from app.common.resources import get_timer_gif_path


class LoadingDialog(QDialog):
    """작업 진행 중을 표시하는 로딩 다이얼로그
    
    assets/nuni_timer.gif 애니메이션을 사용하여 시간이 걸리는 작업 수행 중
    사용자에게 현재 작업 진행 중임을 알립니다.
    """
    
    def __init__(self, parent=None, message="작업 진행 중..."):
        super().__init__(parent)
        self.setWindowTitle("처리 중")
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint
        )
        self.setFixedSize(300, 200)
        
        # 레이아웃 설정
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # GIF 애니메이션 레이블
        self.gif_label = QLabel()
        self.gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gif_label.setFixedSize(120, 120)
        
        # GIF 로드
        gif_path = get_timer_gif_path()
        if gif_path and os.path.exists(gif_path):
            self.movie = QMovie(gif_path)
            self.movie.setScaledSize(self.gif_label.size())
            self.gif_label.setMovie(self.movie)
            self.movie.start()
        else:
            # GIF 파일이 없는 경우 대체 텍스트
            self.gif_label.setText("⏳")
            self.gif_label.setStyleSheet("font-size: 48px;")
        
        layout.addWidget(self.gif_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 메시지 레이블
        self.message_label = QLabel(message)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #333333;
                font-weight: 500;
            }
        """)
        layout.addWidget(self.message_label)
        
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #E0E0E0;
            }
        """)
    
    def set_message(self, message):
        """메시지 텍스트 변경"""
        self.message_label.setText(message)
        QApplication.processEvents()
    
    def showEvent(self, event):
        """다이얼로그가 표시될 때 GIF 애니메이션 시작"""
        super().showEvent(event)
        if hasattr(self, 'movie') and self.movie:
            self.movie.start()
    
    def hideEvent(self, event):
        """다이얼로그가 숨겨질 때 GIF 애니메이션 정지"""
        super().hideEvent(event)
        if hasattr(self, 'movie') and self.movie:
            self.movie.stop()
    
    def closeEvent(self, event):
        """다이얼로그가 닫힐 때 GIF 애니메이션 정지"""
        super().closeEvent(event)
        if hasattr(self, 'movie') and self.movie:
            self.movie.stop()


class LoadingManager:
    """작업 진행 중 로딩 표시 관리 클래스
    
    사용 예시:
        with LoadingManager(parent_widget, "PDF 비교 중..."):
            # 시간이 걸리는 작업 수행
            result = do_long_operation()
    """
    
    def __init__(self, parent=None, message="작업 진행 중..."):
        self.dialog = LoadingDialog(parent, message)
    
    def __enter__(self):
        self.dialog.show()
        QApplication.processEvents()
        return self.dialog
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dialog.close()
        self.dialog.deleteLater()
        return False
    
    def update_message(self, message):
        """메시지 업데이트"""
        self.dialog.set_message(message)
