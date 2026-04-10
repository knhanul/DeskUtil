import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path
import ctypes
from ctypes import wintypes

def resolve_windows_junction(path: str) -> str:
    """Windows 재분석점(junction)을 실제 경로로 변환"""
    try:
        # Try to read the junction target using Windows API
        kernel32 = ctypes.windll.kernel32
        
        # Open the directory with FILE_FLAG_OPEN_REPARSE_POINT
        handle = kernel32.CreateFileW(
            path,
            0,  # GENERIC_READ
            0,  # FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
            None,
            3,  # OPEN_EXISTING
            0x00200000 | 0x02000000,  # FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS
            None
        )
        
        print(f"[DocumentSearch] CreateFileW handle={handle} for path={path}")
        
        if handle == -1 or handle == 0xFFFFFFFF:
            err = kernel32.GetLastError()
            print(f"[DocumentSearch] CreateFileW failed, error={err}")
            return path
        
        try:
            # Use GetFinalPathNameByHandleW to get the actual path
            buf = ctypes.create_unicode_buffer(32767)
            result = kernel32.GetFinalPathNameByHandleW(handle, buf, 32767, 0)
            
            print(f"[DocumentSearch] GetFinalPathNameByHandleW result={result}")
            
            if result > 0 and result < 32767:
                actual_path = buf.value
                print(f"[DocumentSearch] resolved path={actual_path!r}")
                # Remove \\?\ prefix if present
                if actual_path.startswith('\\\\?\\'):
                    actual_path = actual_path[4:]
                return actual_path
            else:
                print(f"[DocumentSearch] GetFinalPathNameByHandleW returned invalid result")
        finally:
            kernel32.CloseHandle(handle)
    except Exception as e:
        print(f"[DocumentSearch] resolve_windows_junction exception: {e}")
    
    # Fallback: try using readlink which works in Python 3.10+
    try:
        target = os.readlink(path)
        print(f"[DocumentSearch] os.readlink returned: {target!r}")
        # If relative path, make it absolute
        if not os.path.isabs(target):
            target = os.path.join(os.path.dirname(path), target)
        return target
    except (OSError, ValueError, NotImplementedError) as e:
        print(f"[DocumentSearch] os.readlink failed: {e}")
    
    return path


def list_files_win32(directory: str) -> list[str]:
    """Windows FindFirstFile API를 사용해 파일 목록 가져오기 (OneDrive 가상화 파일 포함)"""
    files = []
    kernel32 = ctypes.windll.kernel32
    
    # WIN32_FIND_DATA structure
    class WIN32_FIND_DATA(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("dwReserved0", wintypes.DWORD),
            ("dwReserved1", wintypes.DWORD),
            ("cFileName", wintypes.WCHAR * 260),
            ("cAlternateFileName", wintypes.WCHAR * 14),
        ]
    
    search_path = os.path.join(directory, "*")
    find_data = WIN32_FIND_DATA()
    
    handle = kernel32.FindFirstFileW(search_path, ctypes.byref(find_data))
    if handle == -1:
        return files
    try:
        while True:
            filename = find_data.cFileName
            if filename not in ('.', '..'):
                files.append(filename)
            if not kernel32.FindNextFileW(handle, ctypes.byref(find_data)):
                break
    finally:
        kernel32.FindClose(handle)
    
    return files


def get_windows_known_folder_path(folder_guid: str) -> str | None:
    """Windows Known Folder 경로 조회 (탐색기 기준 실제 경로)."""
    if os.name != 'nt':
        return None

    class GUID(ctypes.Structure):
        _fields_ = [
            ('Data1', wintypes.DWORD),
            ('Data2', wintypes.WORD),
            ('Data3', wintypes.WORD),
            ('Data4', ctypes.c_ubyte * 8),
        ]

    def _guid_from_string(guid_str: str) -> GUID:
        parts = guid_str.strip('{}').split('-')
        data1 = int(parts[0], 16)
        data2 = int(parts[1], 16)
        data3 = int(parts[2], 16)
        data4_hex = parts[3] + parts[4]
        data4 = (ctypes.c_ubyte * 8)(*[int(data4_hex[i:i + 2], 16) for i in range(0, 16, 2)])
        return GUID(data1, data2, data3, data4)

    try:
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32

        guid = _guid_from_string(folder_guid)
        path_ptr = ctypes.c_wchar_p()

        result = shell32.SHGetKnownFolderPath(
            ctypes.byref(guid),
            0,
            None,
            ctypes.byref(path_ptr),
        )
        if result != 0 or not path_ptr.value:
            return None

        known_path = path_ptr.value
        ole32.CoTaskMemFree(path_ptr)
        return known_path
    except Exception:
        return None


try:
    from PySide6.QtCore import QDir, QItemSelectionModel, QModelIndex, QPoint, QRectF, QSize, Qt, QThread, Signal as PySideSignal, QAbstractListModel, QSortFilterProxyModel
    from PySide6.QtGui import QAction, QColor, QFileSystemModel, QFont, QPainter, QPainterPath, QPen, QPixmap, QImage, QTextDocument, QTextOption
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QStyle,
        QComboBox,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QStackedWidget,
        QStyledItemDelegate,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QTextBrowser,
        QTextEdit,
        QTreeView,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    Signal = PySideSignal
except ImportError:
    from PyQt6.QtCore import QDir, QModelIndex, QPoint, QRectF, QSize, Qt, QThread, pyqtSignal, QAbstractListModel, QSortFilterProxyModel
    from PyQt6.QtGui import QAction, QColor, QFileSystemModel, QFont, QPainter, QPainterPath, QPen, QPixmap, QImage, QTextDocument, QTextOption
    from PyQt6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QStyle,
        QComboBox,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QListView,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QStackedWidget,
        QStyledItemDelegate,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QTextBrowser,
        QTextEdit,
        QTreeView,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    Signal = pyqtSignal

try:
    SelectionFlagSelect = QItemSelectionModel.SelectionFlag.Select
except NameError:
    SelectionFlagSelect = None


class CheckableFileSystemModel(QFileSystemModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._checked_paths: dict[str, Qt.CheckState] = {}

    def flags(self, index: QModelIndex):
        base_flags = super().flags(index)
        if not index.isValid():
            return base_flags
        if self.isDir(index):
            return base_flags | Qt.ItemFlag.ItemIsUserCheckable
        return base_flags

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if index.isValid() and index.column() == 0 and self.isDir(index) and role == Qt.ItemDataRole.CheckStateRole:
            return self._checked_paths.get(os.path.normpath(self.filePath(index)), Qt.CheckState.Unchecked)
        return super().data(index, role)

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole):
        if index.isValid() and index.column() == 0 and self.isDir(index) and role == Qt.ItemDataRole.CheckStateRole:
            check_state = Qt.CheckState(value)
            target_path = self.filePath(index)
            self._set_check_state_recursive(target_path, check_state)
            self._refresh_parent_states(Path(target_path).parent)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
        return super().setData(index, value, role)

    def _set_check_state_recursive(self, folder_path: str, check_state: Qt.CheckState) -> None:
        normalized = os.path.normpath(folder_path)
        if check_state == Qt.CheckState.Unchecked:
            self._checked_paths = {
                path: state for path, state in self._checked_paths.items() if path != normalized and not path.startswith(normalized + os.sep)
            }
        else:
            self._checked_paths[normalized] = check_state
            root_index = self.index(normalized)
            if root_index.isValid():
                self._apply_children_state(root_index, check_state)

    def _apply_children_state(self, parent_index: QModelIndex, check_state: Qt.CheckState) -> None:
        row_count = self.rowCount(parent_index)
        for row in range(row_count):
            child_index = self.index(row, 0, parent_index)
            if not child_index.isValid() or not self.isDir(child_index):
                continue
            child_path = os.path.normpath(self.filePath(child_index))
            self._checked_paths[child_path] = check_state
            self._apply_children_state(child_index, check_state)
            self.dataChanged.emit(child_index, child_index, [Qt.ItemDataRole.CheckStateRole])

    def _refresh_parent_states(self, parent_path: Path) -> None:
        while parent_path and str(parent_path) and parent_path != parent_path.parent:
            parent_index = self.index(str(parent_path))
            if not parent_index.isValid() or not self.isDir(parent_index):
                parent_path = parent_path.parent
                continue

            child_states: list[Qt.CheckState] = []
            for row in range(self.rowCount(parent_index)):
                child_index = self.index(row, 0, parent_index)
                if child_index.isValid() and self.isDir(child_index):
                    child_states.append(self._checked_paths.get(os.path.normpath(self.filePath(child_index)), Qt.CheckState.Unchecked))

            normalized = os.path.normpath(str(parent_path))
            if child_states and all(state == Qt.CheckState.Checked for state in child_states):
                self._checked_paths[normalized] = Qt.CheckState.Checked
            elif any(state != Qt.CheckState.Unchecked for state in child_states):
                self._checked_paths[normalized] = Qt.CheckState.PartiallyChecked
            else:
                self._checked_paths.pop(normalized, None)

            self.dataChanged.emit(parent_index, parent_index, [Qt.ItemDataRole.CheckStateRole])
            parent_path = parent_path.parent

    def checked_folder_paths(self) -> list[str]:
        checked = [path for path, state in self._checked_paths.items() if state == Qt.CheckState.Checked]
        checked.sort(key=lambda item: (len(Path(item).parts), item))
        collapsed: list[str] = []
        for path in checked:
            normalized = os.path.normpath(path)
            if any(normalized == base or normalized.startswith(base + os.sep) for base in collapsed):
                continue
            collapsed.append(normalized)
        return collapsed


# ─────────────────────────────────────────────────────────────────────────────
# Document Search Result Model / Proxy / Delegate Classes (QListView-based)
# ─────────────────────────────────────────────────────────────────────────────

# Custom Roles for DocumentResultListModel
FileNameRole = Qt.ItemDataRole.UserRole + 10
FilePathRole = Qt.ItemDataRole.UserRole + 11
SnippetRole = Qt.ItemDataRole.UserRole + 12
PreviewRole = Qt.ItemDataRole.UserRole + 13
CreatedAtRole = Qt.ItemDataRole.UserRole + 14
ModifiedAtRole = Qt.ItemDataRole.UserRole + 15
FileSizeRole = Qt.ItemDataRole.UserRole + 16
FileKindRole = Qt.ItemDataRole.UserRole + 17
SortTimestampRole = Qt.ItemDataRole.UserRole + 18
RawPayloadRole = Qt.ItemDataRole.UserRole + 19
SearchQueryRole = Qt.ItemDataRole.UserRole + 20
IncludeSnippetRole = Qt.ItemDataRole.UserRole + 21


class DocumentResultListModel(QAbstractListModel):
    """문서 검색 결과 리스트 모델 - payload 리스트 기반"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[dict[str, str]] = []
        self._search_query: str = ""
        self._include_snippet: bool = True

    def set_items(self, items: list[dict[str, str]]) -> None:
        """전체 아이템 교체"""
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def append_item(self, payload: dict[str, str]) -> None:
        """아이템 추가"""
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(payload)
        self.endInsertRows()

    def clear(self) -> None:
        """모두 삭제"""
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()

    def set_search_query(self, query: str) -> None:
        """검색어 설정 (하이라이트용)"""
        self._search_query = query
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, 0))

    def set_include_snippet(self, include: bool) -> None:
        """조각 문구 표시 여부 설정"""
        self._include_snippet = include
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, 0))

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None

        payload = self._items[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return payload.get('file_name', '')

        if role == FileNameRole:
            return payload.get('file_name', '')
        if role == FilePathRole:
            return payload.get('file_path', '')
        if role == SnippetRole:
            return payload.get('snippet', '')
        if role == PreviewRole:
            return payload.get('preview', '')
        if role == CreatedAtRole:
            return payload.get('created_at', '')
        if role == ModifiedAtRole:
            return payload.get('modified_at', '')
        if role == FileSizeRole:
            return payload.get('file_size', '')
        if role == FileKindRole:
            return payload.get('file_kind', '')
        if role == RawPayloadRole:
            return payload
        if role == SearchQueryRole:
            return self._search_query
        if role == IncludeSnippetRole:
            return self._include_snippet
        if role == SortTimestampRole:
            # 정렬용 타임스탬프 (modified_at 기준)
            modified_at = payload.get('modified_at', '')
            try:
                # ISO 형식 가정: 2024-01-15T10:30:00
                from datetime import datetime
                dt = datetime.fromisoformat(modified_at.replace('Z', '+00:00'))
                return int(dt.timestamp())
            except Exception:
                return 0

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def get_payload_at(self, row: int) -> dict[str, str] | None:
        """특정 행의 payload 가져오기"""
        if 0 <= row < len(self._items):
            return self._items[row]
        return None


class DocumentResultSortProxyModel(QSortFilterProxyModel):
    """문서 검색 결과 정렬용 프록시 모델"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSortRole(SortTimestampRole)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """정렬 로직"""
        sort_role = self.sortRole()

        left_data = self.sourceModel().data(left, sort_role) if self.sourceModel() else None
        right_data = self.sourceModel().data(right, sort_role) if self.sourceModel() else None

        if sort_role == SortTimestampRole:
            # 수치 비교
            left_val = left_data if isinstance(left_data, (int, float)) else 0
            right_val = right_data if isinstance(right_data, (int, float)) else 0
            return left_val < right_val

        if sort_role == FileNameRole:
            # 문자열 비교 (대소문자 무시)
            left_str = str(left_data or "").lower()
            right_str = str(right_data or "").lower()
            return left_str < right_str

        if sort_role == FileKindRole:
            left_str = str(left_data or "").lower()
            right_str = str(right_data or "").lower()
            return left_str < right_str

        # 기본: 원본 순서 유지 (관련도순)
        return left.row() < right.row()

    def get_payload_at_proxy_row(self, proxy_row: int) -> dict[str, str] | None:
        """프록시 인덱스 기준으로 payload 가져오기"""
        proxy_index = self.index(proxy_row, 0)
        source_index = self.mapToSource(proxy_index)
        if source_index.isValid() and self.sourceModel():
            return self.sourceModel().data(source_index, RawPayloadRole)
        return None


class DocumentResultDelegate(QStyledItemDelegate):
    """문서 검색 결과 카드 스타일 델리게이트"""

    # 시각적 상수 (밀도 높은 리스트용)
    CARD_MARGIN = 6
    CARD_PADDING = 8
    CARD_SPACING = 5
    ICON_SIZE = 24
    BADGE_HEIGHT = 14
    BADGE_PADDING_X = 6
    SNIPPET_MAX_LINES = 1
    PATH_ELLIPSIS_WIDTH = 200

    # 색상 팔레트
    COL_CARD_BG = QColor("#FFFFFF")
    COL_CARD_HOVER = QColor("#F2F7FF")
    COL_CARD_SELECTED_BORDER = QColor("#3B82F6")
    COL_CARD_SELECTED_FILL = QColor("#EFF6FF")
    COL_TEXT_PRIMARY = QColor("#111827")
    COL_TEXT_SECONDARY = QColor("#6B7280")
    COL_TEXT_TERTIARY = QColor("#9CA3AF")
    COL_BADGE_BG = QColor("#E5E7EB")
    COL_BADGE_TEXT = QColor("#374151")
    COL_HIGHLIGHT = QColor("#DBEAFE")
    COL_HIGHLIGHT_TEXT = QColor("#1D4ED8")
    COL_ICON_DEFAULT = QColor("#9CA3AF")

    # 파일 타입별 색상
    TYPE_COLORS = {
        'PDF': (QColor("#FEE2E2"), QColor("#991B1B")),
        'DOCX': (QColor("#DBEAFE"), QColor("#1E40AF")),
        'XLSX': (QColor("#D1FAE5"), QColor("#065F46")),
        'HWP': (QColor("#E0E7FF"), QColor("#3730A3")),
        'HWPX': (QColor("#E0E7FF"), QColor("#3730A3")),
        'TXT': (QColor("#F3F4F6"), QColor("#4B5563")),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    def sizeHint(self, option, index: QModelIndex) -> QSize:
        """카드 크기 계산 (밀도 높은 리스트용)"""
        include_snippet = index.data(IncludeSnippetRole) or False
        snippet = index.data(SnippetRole) or ""

        base_height = self.CARD_PADDING * 2 + self.ICON_SIZE

        if include_snippet and snippet.strip():
            # 조각 문구 높이 추가 (줄 수에 따라) - 최소 높이로 조정
            snippet_lines = min(self.SNIPPET_MAX_LINES, snippet.count('\n') + 1)
            base_height += self.CARD_SPACING + (snippet_lines * 14) + 6  # 여유 공간 축소

        # 경로 한 줄 추가 (작은 폰트)
        base_height += self.CARD_SPACING + 12

        return QSize(option.rect.width() - self.CARD_MARGIN * 2, base_height)

    def paint(self, painter, option, index: QModelIndex) -> None:
        """카드 렌더링"""
        if not index.isValid():
            return

        # 데이터 추출
        file_name = index.data(FileNameRole) or ""
        file_path = index.data(FilePathRole) or ""
        file_kind = index.data(FileKindRole) or ""
        file_size = index.data(FileSizeRole) or ""
        modified_at = index.data(ModifiedAtRole) or ""
        snippet = index.data(SnippetRole) or ""
        search_query = index.data(SearchQueryRole) or ""
        include_snippet = index.data(IncludeSnippetRole) or False

        # 상태 확인
        is_selected = option.state & (QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_HasFocus)
        is_hover = option.state & QStyle.StateFlag.State_MouseOver

        # 페인터 설정
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # 카드 영역 계산
        card_rect = option.rect.adjusted(self.CARD_MARGIN, self.CARD_MARGIN // 2,
                                          -self.CARD_MARGIN, -self.CARD_MARGIN // 2)

        # 배경 그리기 (QRectF 변환)
        self._paint_background(painter, QRectF(card_rect), is_selected, is_hover)

        # 내용 영역
        content_rect = card_rect.adjusted(self.CARD_PADDING, self.CARD_PADDING,
                                          -self.CARD_PADDING, -self.CARD_PADDING)
        x = content_rect.left()
        y = content_rect.top()
        available_width = content_rect.width()

        # 1행: 아이콘 + 파일명 + 배지 + 메타정보
        icon_rect = QRectF(x, y, self.ICON_SIZE, self.ICON_SIZE)
        self._paint_file_icon(painter, icon_rect, file_kind)

        x += self.ICON_SIZE + 10
        line1_y = y + (self.ICON_SIZE - 14) // 2

        # 파일명 (검색어 하이라이트 포함)
        name_width = int(available_width - (self.ICON_SIZE + 10 + 100 + 80 + 80))
        self._paint_highlighted_text(painter, int(x), int(line1_y), file_name, search_query,
                                      self.COL_TEXT_PRIMARY, is_bold=True, max_width=name_width)

        # 파일 타입 배지
        badge_x = int(x + name_width + 10)
        self._paint_badge(painter, badge_x, int(line1_y - 2), file_kind)

        # 파일 크기
        size_x = badge_x + 70
        self._paint_text(painter, size_x, int(line1_y), file_size, self.COL_TEXT_SECONDARY, 11)

        # 수정일
        date_x = size_x + 80
        self._paint_text(painter, date_x, int(line1_y), modified_at[:10], self.COL_TEXT_SECONDARY, 11)

        # 2행: 조각 문구 (있을 때만)
        y += self.ICON_SIZE + self.CARD_SPACING
        if include_snippet and snippet.strip():
            snippet_rect = QRectF(x, y, available_width - (x - content_rect.left()), 40)
            self._paint_snippet(painter, snippet_rect, snippet, search_query)
            y += snippet_rect.height() + self.CARD_SPACING
        else:
            y += self.CARD_SPACING // 2

        # 3행: 파일 경로 (elide 처리)
        self._paint_elided_path(painter, int(x), int(y), file_path, int(available_width - (x - content_rect.left())))

        painter.restore()

    def _paint_background(self, painter, rect: 'QRectF', is_selected: bool, is_hover: bool) -> None:
        """카드 배경 그리기"""
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)

        if is_selected:
            # 선택 상태: 테두리 + 배경
            painter.fillPath(path, self.COL_CARD_SELECTED_FILL)
            pen = QPen(self.COL_CARD_SELECTED_BORDER)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawPath(path)
        elif is_hover:
            # 호버 상태
            painter.fillPath(path, self.COL_CARD_HOVER)
        else:
            # 기본 상태
            painter.fillPath(path, self.COL_CARD_BG)

    def _paint_file_icon(self, painter, rect: 'QRectF', file_kind: str) -> None:
        """파일 아이콘 그리기"""
        # 파일 타입별 색상
        bg_color, text_color = self.TYPE_COLORS.get(file_kind, (self.COL_BADGE_BG, self.COL_BADGE_TEXT))

        # 둥근 사각형 배경
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        painter.fillPath(path, bg_color)

        # 확장자 텍스트
        painter.setPen(text_color)
        font = QFont("Segoe UI", 7, QFont.Weight.Bold)
        painter.setFont(font)

        ext = file_kind[:3].upper() if file_kind else "FILE"
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, ext)
        painter.restore()

    def _paint_badge(self, painter, x: int, y: int, text: str) -> None:
        """파일 타입 배지 그리기"""
        bg_color, text_color = self.TYPE_COLORS.get(text, (self.COL_BADGE_BG, self.COL_BADGE_TEXT))

        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        badge_width = text_width + self.BADGE_PADDING_X * 2

        badge_rect = QRectF(x, y, badge_width, self.BADGE_HEIGHT)

        # 배지 배경
        path = QPainterPath()
        path.addRoundedRect(badge_rect, 9, 9)
        painter.fillPath(path, bg_color)

        # 텍스트
        painter.setPen(text_color)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_text(self, painter, x: int, y: int, text: str, color: QColor, size: int = 10) -> None:
        """기본 텍스트 그리기"""
        painter.setPen(color)
        font = QFont("Segoe UI", size)
        painter.setFont(font)
        painter.drawText(x, y + 10, text)

    def _paint_highlighted_text(self, painter, x: int, y: int, text: str, query: str,
                                color: QColor, is_bold: bool = False, max_width: int = 0) -> None:
        """검색어 하이라이트 포함 텍스트 그리기"""
        font = QFont("Segoe UI", 11 if is_bold else 10)
        if is_bold:
            font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        # 텍스트가 너무 길면 elide
        display_text = text
        if max_width > 0 and metrics.horizontalAdvance(text) > max_width:
            display_text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max_width)

        if not query or query.lower() not in display_text.lower():
            # 하이라이트 없음
            painter.setPen(color)
            painter.drawText(x, y + 12, display_text)
            return

        # 하이라이트 처리
        query_lower = query.lower()
        text_lower = display_text.lower()
        start = 0
        current_x = x

        while start < len(display_text):
            idx = text_lower.find(query_lower, start)
            if idx == -1:
                # 남은 일반 텍스트
                segment = display_text[start:]
                painter.setPen(color)
                painter.drawText(current_x, y + 12, segment)
                break

            # 하이라이트 전 텍스트
            if idx > start:
                segment = display_text[start:idx]
                painter.setPen(color)
                painter.drawText(current_x, y + 12, segment)
                current_x += metrics.horizontalAdvance(segment)

            # 하이라이트 부분
            hl_text = display_text[idx:idx + len(query)]

            # 하이라이트 배경
            hl_width = metrics.horizontalAdvance(hl_text)
            hl_rect = QRectF(current_x - 1, y - 1, hl_width + 2, 16)
            painter.save()
            painter.fillRect(hl_rect, self.COL_HIGHLIGHT)
            painter.restore()

            # 하이라이트 텍스트
            painter.setPen(self.COL_HIGHLIGHT_TEXT)
            font.setWeight(QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(current_x, y + 12, hl_text)

            current_x += hl_width
            start = idx + len(query)

            # 폰트 원복
            font.setWeight(QFont.Weight.DemiBold if is_bold else QFont.Weight.Normal)
            painter.setFont(font)

    def _paint_snippet(self, painter, rect: 'QRectF', snippet: str, query: str) -> None:
        """조각 문구 텍스트 그리기 (최대 1줄, 작은 폰트)"""
        painter.setPen(self.COL_TEXT_SECONDARY)
        font = QFont("Segoe UI", 9)
        painter.setFont(font)

        # 줄바꿈 처리
        lines = snippet.split('\n')[:self.SNIPPET_MAX_LINES]
        y = int(rect.top())
        line_height = 12  # 줄 간격 축소

        for line in lines:
            if not line.strip():
                continue
            # 검색어 하이라이트
            self._paint_highlighted_text_simple(painter, int(rect.left()), y, line, query,
                                                self.COL_TEXT_SECONDARY, max_width=int(rect.width()))
            y += line_height

    def _paint_highlighted_text_simple(self, painter, x: int, y: int, text: str, query: str,
                                        color: QColor, max_width: int = 0) -> None:
        """간단한 하이라이트 텍스트 (조각 문구용)"""
        metrics = painter.fontMetrics()

        # elide 처리
        display_text = text
        if max_width > 0 and metrics.horizontalAdvance(text) > max_width:
            display_text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, max_width)

        if not query or query.lower() not in display_text.lower():
            painter.setPen(color)
            painter.drawText(x, y + 12, display_text)
            return

        # 하이라이트
        query_lower = query.lower()
        text_lower = display_text.lower()
        start = 0
        current_x = x

        while start < len(display_text):
            idx = text_lower.find(query_lower, start)
            if idx == -1:
                segment = display_text[start:]
                painter.setPen(color)
                painter.drawText(current_x, y + 12, segment)
                break

            if idx > start:
                segment = display_text[start:idx]
                painter.setPen(color)
                painter.drawText(current_x, y + 12, segment)
                current_x += metrics.horizontalAdvance(segment)

            hl_text = display_text[idx:idx + len(query)]
            hl_width = metrics.horizontalAdvance(hl_text)

            # 하이라이트 배경
            hl_rect = QRectF(current_x - 1, y - 1, hl_width + 2, 16)
            painter.save()
            painter.fillRect(hl_rect, self.COL_HIGHLIGHT)
            painter.restore()

            painter.setPen(self.COL_HIGHLIGHT_TEXT)
            font = painter.font()
            font.setWeight(QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(current_x, y + 12, hl_text)

            current_x += hl_width
            start = idx + len(query)

            # 원복
            font.setWeight(QFont.Weight.Normal)
            painter.setFont(font)

    def _paint_elided_path(self, painter, x: int, y: int, path: str, max_width: int) -> None:
        """경로 텍스트 (말줄임표 처리)"""
        painter.setPen(self.COL_TEXT_TERTIARY)
        font = QFont("Segoe UI", 9)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        elided = metrics.elidedText(path, Qt.TextElideMode.ElideMiddle, max_width)
        painter.drawText(x, y + 12, elided)


current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from doc_search.extractors import get_extractor
from .integrated_previewer import IntegratedPreviewer


# Preview page indices for QStackedWidget
PREVIEW_PAGE_IMAGE = 0  # QLabel for PDF/image thumbnails
PREVIEW_PAGE_TEXT = 1   # QTextBrowser for HTML/text content


def format_datetime(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
    except (OverflowError, OSError, ValueError):
        return '-'


def format_file_size(size_bytes: int) -> str:
    size = float(size_bytes)
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == 'B':
                return f'{int(size)} {unit}'
            return f'{size:.1f} {unit}'
        size /= 1024
    return f'{int(size_bytes)} B'


class CustomResultWidget(QWidget):
    def __init__(
        self,
        file_data: dict[str, str],
        snippet_text: str,
        include_snippet: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.file_name = file_data.get('file_name', '')
        self.file_path = file_data.get('file_path', '')
        self.preview_text = file_data.get('preview', '')
        self.include_snippet = include_snippet

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QFrame()
        card.setObjectName("resultItemCard")
        card.setProperty("selected", False)
        self.card = card
        if include_snippet:
            card_layout = QGridLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setHorizontalSpacing(12)
            card_layout.setVerticalSpacing(8)

            meta_labels = [
                f"경로: {self.file_path}",
                f"종류: {file_data.get('file_kind', '-')}",
                f"크기: {file_data.get('file_size', '-')}",
                f"생성: {file_data.get('created_at', '-')}",
                f"수정: {file_data.get('modified_at', '-')}",
            ]
            for col, text in enumerate(meta_labels):
                label = QLabel(text)
                label.setObjectName("resultMetaLabel")
                label.setToolTip(self.file_path)
                card_layout.addWidget(label, 0, col)

            snippet_label = QLabel(snippet_text or self.preview_text)
            snippet_label.setObjectName("resultSnippetLabel")
            snippet_label.setWordWrap(True)
            snippet_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            card_layout.addWidget(snippet_label, 1, 0, 1, len(meta_labels))
        else:
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.setSpacing(12)
            labels = [
                f"경로: {self.file_path}",
                f"종류: {file_data.get('file_kind', '-')}",
                f"크기: {file_data.get('file_size', '-')}",
                f"생성: {file_data.get('created_at', '-')}",
                f"수정: {file_data.get('modified_at', '-')}",
            ]
            for index, text in enumerate(labels):
                label = QLabel(text)
                label.setObjectName("resultMetaLabel")
                label.setToolTip(self.file_path)
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                if index == 0:
                    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                card_layout.addWidget(label)

        root.addWidget(card)

    def set_selected(self, selected: bool) -> None:
        self.card.setProperty("selected", selected)
        self.card.style().unpolish(self.card)
        self.card.style().polish(self.card)
        self.card.update()



class SearchWorker(QThread):
    result_found = Signal(str, str, str, str, str, str, str, str)
    progress_changed = Signal(int, int, str)
    search_finished = Signal(int, int, bool)
    search_failed = Signal(str)

    def __init__(self, folder_paths: list[str], query: str, allowed_extensions: set[str], parent=None) -> None:
        super().__init__(parent)
        self.folder_paths = [os.path.normpath(path) for path in folder_paths]
        self.query = query.strip().lower()
        self._is_cancelled = False
        self.supported_extensions = allowed_extensions

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            print(f"[DocumentSearch] worker started folders={self.folder_paths} extensions={sorted(self.supported_extensions)} query={self.query!r}")
            files = self._collect_files()
            total = len(files)
            found = 0
            print(f"[DocumentSearch] collected_files={total}")

            for index, file_path in enumerate(files, start=1):
                if self._is_cancelled:
                    print(f"[DocumentSearch] cancelled scanned={index - 1} found={found}")
                    self.search_finished.emit(found, index - 1, True)
                    return

                self.progress_changed.emit(index, total, file_path)
                if index <= 5 or index % 50 == 0:
                    print(f"[DocumentSearch] scanning {index}/{total}: {file_path}")
                text = self._extract_text(file_path)
                if not text:
                    continue

                if self.query in text.lower():
                    found += 1
                    snippet = self._build_snippet(text)
                    stats = os.stat(file_path)
                    extension = Path(file_path).suffix.lower().lstrip('.') or 'file'
                    self.result_found.emit(
                        os.path.basename(file_path),
                        file_path,
                        snippet,
                        text[:5000],
                        format_datetime(stats.st_ctime),
                        format_datetime(stats.st_mtime),
                        format_file_size(stats.st_size),
                        extension.upper(),
                    )

            print(f"[DocumentSearch] finished scanned={total} found={found}")
            self.search_finished.emit(found, total, False)
        except Exception as exc:
            print(f"[DocumentSearch] failed: {exc}")
            self.search_failed.emit(str(exc))

    def _collect_files(self) -> list[str]:
        file_paths: list[str] = []
        visited: set[str] = set()
        for folder_path in self.folder_paths:
            normalized_root = os.path.normpath(folder_path)
            print(f"[DocumentSearch] walking folder: {normalized_root}")
            
            # Try the original path first
            paths_to_try = [normalized_root]
            
            # If folder appears empty, try OneDrive equivalents
            folder_name = Path(normalized_root).name
            folder_name_lower = folder_name.lower()
            
            # Map of known folder names to possible OneDrive subfolder names
            onedrive_name_map = {
                'documents': ['Documents', '문서'],
                '문서': ['Documents', '문서'],
                'desktop': ['Desktop', '바탕 화면'],
                '바탕 화면': ['Desktop', '바탕 화면'],
                'pictures': ['Pictures', '사진'],
                '사진': ['Pictures', '사진'],
            }
            
            if folder_name_lower in onedrive_name_map or folder_name in onedrive_name_map:
                subfolder_names = onedrive_name_map.get(folder_name_lower, onedrive_name_map.get(folder_name, []))
                home = str(Path.home())
                # Find all OneDrive* directories in user home
                try:
                    onedrive_roots = [
                        os.path.join(home, entry.name)
                        for entry in os.scandir(home)
                        if entry.is_dir() and entry.name.lower().startswith('onedrive')
                    ]
                except OSError:
                    onedrive_roots = []
                
                for od_root in onedrive_roots:
                    for subfolder in subfolder_names:
                        candidate = os.path.join(od_root, subfolder)
                        if candidate not in paths_to_try:
                            paths_to_try.append(candidate)
                    # Also try the OneDrive root itself (some configs put files directly there)
                    if od_root not in paths_to_try:
                        paths_to_try.append(od_root)
            
            for try_path in paths_to_try:
                if try_path in visited:
                    continue
                    
                print(f"[DocumentSearch] trying path: {try_path}")
                
                if not os.path.exists(try_path):
                    print(f"[DocumentSearch] path does not exist: {try_path}")
                    continue
                if not os.path.isdir(try_path):
                    print(f"[DocumentSearch] path is not a directory: {try_path}")
                    continue
                
                # Check if this path has content via scandir
                try:
                    entries = list(os.scandir(try_path))
                    print(f"[DocumentSearch] scandir count={len(entries)}")
                    if len(entries) == 0:
                        print(f"[DocumentSearch] path is empty, trying next")
                        continue
                    for entry in entries[:5]:
                        print(f"[DocumentSearch] entry: {entry.name}")
                except Exception as e:
                    print(f"[DocumentSearch] scandir error: {e}")
                    continue
                
                # Found a path with content, use it
                visited.add(try_path)
                
                # Recursive collection using scandir
                try:
                    file_paths = self._collect_files_scandir(try_path, file_paths)
                    print(f"[DocumentSearch] after walk total={len(file_paths)}")
                    break  # Stop trying other paths for this folder
                except Exception as e:
                    print(f"[DocumentSearch] recursive collection error: {e}")
                    continue
            else:
                print(f"[DocumentSearch] all paths exhausted for {normalized_root}")
                
        return file_paths
    
    def _collect_files_scandir(self, root: str, file_paths: list[str]) -> list[str]:
        """os.scandir를 사용해 재귀적으로 파일 수집 (OneDrive 가상화 지원)"""
        try:
            for entry in os.scandir(root):
                if self._is_cancelled:
                    break
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Recurse into subdirectory
                        file_paths = self._collect_files_scandir(entry.path, file_paths)
                    elif entry.is_file(follow_symlinks=False):
                        # Check file extension
                        ext = Path(entry.name).suffix.lower()
                        if ext in self.supported_extensions:
                            file_paths.append(entry.path)
                            if len(file_paths) <= 5:
                                print(f"[DocumentSearch] MATCH {ext!r} {entry.name!r}")
                except (OSError, PermissionError):
                    # Skip files/dirs we can't access
                    continue
        except (OSError, PermissionError) as e:
            print(f"[DocumentSearch] scandir error in {root}: {e}")
        
        return file_paths

    def _extract_text(self, file_path: str) -> str:
        extractor = get_extractor(file_path)
        if extractor is None:
            return ''
        try:
            return extractor.extract_text(file_path) or ''
        except Exception:
            return ''

    def _build_snippet(self, text: str) -> str:
        lower_text = text.lower()
        pos = lower_text.find(self.query)
        clean_text = text.replace('\n', ' ')
        if pos < 0:
            return clean_text[:180]
        start = max(0, pos - 60)
        end = min(len(clean_text), pos + len(self.query) + 100)
        snippet = clean_text[start:end].strip()
        if start > 0:
            snippet = '...' + snippet
        if end < len(clean_text):
            snippet = snippet + '...'
        return snippet


class DocumentSearchMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.search_worker = None
        self.current_folder = ''
        self.current_preview_path = ''
        self._preview_original_pixmap: QPixmap | None = None
        self._result_payloads: list[dict[str, str]] = []
        self._syncing_folder_checks = False
        self.supported_file_types = {
            '.txt': 'TXT',
            '.pdf': 'PDF',
            '.docx': 'DOCX',
            '.xlsx': 'XLSX',
            '.hwp': 'HWP',
            '.cell': 'CELL',
            '.hwpx': 'HWPX',
        }
        self.setWindowTitle("문서 통합 검색")
        self.resize(1440, 860)
        self.setMinimumSize(QSize(1180, 720))
        self._build_ui()
        self._apply_styles()
        self._connect_signals()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter.setChildrenCollapsible(False)
        self.vertical_splitter.setHandleWidth(6)

        self.top_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.top_splitter.setChildrenCollapsible(False)
        self.top_splitter.setHandleWidth(6)

        self.bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.bottom_splitter.setChildrenCollapsible(False)
        self.bottom_splitter.setHandleWidth(6)

        self.folder_panel = self._build_folder_panel()
        self.search_panel = self._build_search_panel()
        self.conditions_panel = self._build_conditions_panel()
        self.result_panel = self._build_result_panel()
        self.preview_panel = self._build_preview_panel()

        # 탭 컨테이너 생성: 검색 탭 + 조건 탭 (Segmented Control 스타일)
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName('searchTabs')
        self.tab_widget.addTab(self.search_panel, '  🔍 검색어 입력  ')
        self.tab_widget.addTab(self.conditions_panel, '  ⚙️ 검색 조건 설정  ')
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(False)
        self.tab_widget.setTabsClosable(False)

        # 탭 위젯 직접 스타일 적용 (버튼형 Segmented Control)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                background: #FFFFFF;
                border: 0.5px solid #C6C6C8;
                border-radius: 14px;
                top: -1px;
            }
            QTabBar::tab {
                background: transparent;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                margin: 4px 2px;
                font-weight: 500;
                font-size: 13px;
                color: #636366;
                min-width: 100px;
            }
            QTabBar::tab:hover {
                background: rgba(0, 122, 255, 0.08);
                color: #007AFF;
            }
            QTabBar::tab:selected {
                background: #007AFF;
                color: #FFFFFF;
                font-weight: 600;
            }
        """)

        self.top_splitter.addWidget(self.folder_panel)
        self.top_splitter.addWidget(self.tab_widget)
        self.bottom_splitter.addWidget(self.result_panel)
        self.bottom_splitter.addWidget(self.preview_panel)

        # 좌우 3:2 고정 비율 (60% : 40%) - 1/4:2/4분면, 3/4:4/4분면
        self.top_splitter.setStretchFactor(0, 60)
        self.top_splitter.setStretchFactor(1, 40)
        self.bottom_splitter.setStretchFactor(0, 60)
        self.bottom_splitter.setStretchFactor(1, 40)

        self.vertical_splitter.addWidget(self.top_splitter)
        self.vertical_splitter.addWidget(self.bottom_splitter)
        # 상하 2:3 고정 비율 (상단 40%, 하단 60%)
        self.vertical_splitter.setStretchFactor(0, 40)
        self.vertical_splitter.setStretchFactor(1, 60)
        root.addWidget(self.vertical_splitter, 1)

        self._build_menu()

    def _build_folder_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panelCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QLabel("폴더 탐색기")
        header.setObjectName("sectionTitle")
        layout.addWidget(header)

        self.folder_path_edit = QLineEdit()
        self.folder_path_edit.setReadOnly(True)
        self.folder_path_edit.setPlaceholderText("선택한 탐색 경로")
        self.folder_path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.folder_path_edit)

        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setRootIsDecorated(True)
        self.folder_tree.setIndentation(16)
        self.folder_tree.setUniformRowHeights(True)
        self.folder_tree.setAnimated(True)
        self.folder_tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.folder_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.folder_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.folder_tree, 1)

        self.checked_paths_label = QLabel("선택된 폴더 없음")
        self.checked_paths_label.setObjectName("metaLabel")
        layout.addWidget(self.checked_paths_label)
        self.checked_folder_paths_set: set[str] = set()
        self._populate_folder_tree()
        return panel

    def _build_search_panel(self) -> QWidget:
        """첫 번째 탭: 검색어 입력 + 검색 시작 버튼 + 진행 정보"""
        panel = QFrame()
        panel.setObjectName("panelCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 검색어 입력 영역
        query_label = QLabel("검색어")
        query_label.setObjectName("fieldLabel")
        layout.addWidget(query_label)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("검색어를 입력하세요")
        self.search_input.setClearButtonEnabled(True)
        layout.addWidget(self.search_input)

        # 검색 시작 버튼
        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.search_button = QPushButton("🔍 검색 시작")
        self.search_button.setObjectName('compareBtn')
        self.search_button.setFixedHeight(42)
        self.search_button.setMinimumWidth(120)

        self.cancel_button = QPushButton("⏹ 취소")
        self.cancel_button.setObjectName('resetBtn')
        self.cancel_button.setFixedHeight(42)
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.setVisible(False)

        controls.addWidget(self.search_button)
        controls.addWidget(self.cancel_button)
        controls.addStretch()
        layout.addLayout(controls)

        # 검색 진행 정보 (바 타입)
        progress_frame = QFrame()
        progress_frame.setObjectName("innerCard")
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(14, 12, 14, 12)
        progress_layout.setSpacing(8)

        self.progress_title = QLabel("검색 준비")
        self.progress_title.setObjectName("fieldLabel")
        progress_layout.addWidget(self.progress_title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.progress_status = QLabel("폴더를 선택하고 검색어를 입력하세요.")
        self.progress_status.setObjectName("metaLabel")
        progress_layout.addWidget(self.progress_status)

        self.progress_details = QLabel("")
        self.progress_details.setObjectName("metaLabel")
        self.progress_details.setWordWrap(True)
        progress_layout.addWidget(self.progress_details)

        layout.addWidget(progress_frame)
        layout.addStretch()
        return panel

    def _build_conditions_panel(self) -> QWidget:
        """두 번째 탭: 검색 조건 (파일 타입, 조각 문구 포함 등)"""
        panel = QFrame()
        panel.setObjectName("panelCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QLabel("검색 조건")
        header.setObjectName("sectionTitle")
        layout.addWidget(header)

        type_label = QLabel("문서 파일 선택")
        type_label.setObjectName("fieldLabel")
        layout.addWidget(type_label)

        type_frame = QFrame()
        type_frame.setObjectName("innerCard")
        type_layout = QGridLayout(type_frame)
        type_layout.setContentsMargins(12, 12, 12, 12)
        type_layout.setHorizontalSpacing(10)
        type_layout.setVerticalSpacing(8)

        self.file_type_checkboxes = {}
        for index, (extension, label) in enumerate(self.supported_file_types.items()):
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            self.file_type_checkboxes[extension] = checkbox
            type_layout.addWidget(checkbox, index // 3, index % 3)
        layout.addWidget(type_frame)

        self.include_snippet_checkbox = QCheckBox("검색 결과에 조각 문구 포함")
        self.include_snippet_checkbox.setChecked(True)
        layout.addWidget(self.include_snippet_checkbox)

        self.conditions_summary_label = QLabel("모든 문서 형식이 검색 대상입니다.")
        self.conditions_summary_label.setObjectName("metaLabel")
        layout.addWidget(self.conditions_summary_label)

        layout.addStretch()
        self._update_conditions_summary()
        return panel

    def _build_result_panel(self) -> QWidget:
        """검색 결과 패널 - QListView + 카드 UI"""
        panel = QFrame()
        panel.setObjectName("panelCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # ── 상단 툴바 (콤팩트) ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        # 결과 수 라벨
        self.result_count_label = QLabel("0개 문서")
        self.result_count_label.setObjectName("resultCountLabel")
        toolbar.addWidget(self.result_count_label)

        toolbar.addStretch()

        # 정렬 콤보박스
        sort_label = QLabel("정렬:")
        sort_label.setObjectName("fieldLabel")
        toolbar.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_combo.setObjectName("sortCombo")
        self.sort_combo.addItem("관련도순", "relevance")
        self.sort_combo.addItem("수정일순", "modified")
        self.sort_combo.addItem("파일명순", "filename")
        self.sort_combo.addItem("종류순", "filekind")
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_combo)

        # 조각 문구 표시 토글
        self.snippet_toggle_btn = QPushButton("조각 문구 보기")
        self.snippet_toggle_btn.setObjectName("snippetToggleBtn")
        self.snippet_toggle_btn.setCheckable(True)
        self.snippet_toggle_btn.setChecked(True)
        self.snippet_toggle_btn.clicked.connect(self._on_snippet_toggle)
        toolbar.addWidget(self.snippet_toggle_btn)

        layout.addLayout(toolbar)

        # ── Stacked Widget: Empty State / Result List ──
        self.result_stack = QStackedWidget()
        self.result_stack.setObjectName("resultStack")

        # Page 0: Empty State
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon = QLabel("🔍")
        empty_icon.setStyleSheet("font-size: 48px; color: #9CA3AF;")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)
        empty_title = QLabel("검색 결과가 없습니다")
        empty_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #4B5563; margin: 10px 0;")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)
        empty_desc = QLabel("검색어를 입력하고 검색 버튼을 눌러 문서를 찾아보세요.\n\n"
                           "팁: 더 짧은 검색어를 사용하거나 파일 형식을 넓혀보세요.")
        empty_desc.setStyleSheet("font-size: 12px; color: #6B7280; line-height: 1.5;")
        empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_desc)
        self.result_stack.addWidget(empty_widget)

        # Page 1: Result ListView
        result_container = QWidget()
        result_layout = QVBoxLayout(result_container)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(0)

        # QListView 설정
        self.result_view = QListView()
        self.result_view.setObjectName("resultView")
        self.result_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.result_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.result_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result_view.setUniformItemSizes(False)  # 가변 높이 카드

        # 모델 및 프록시 설정
        self.result_model = DocumentResultListModel(self)
        self.result_proxy = DocumentResultSortProxyModel(self)
        self.result_proxy.setSourceModel(self.result_model)
        self.result_view.setModel(self.result_proxy)

        # 델리게이트 설정
        self.result_delegate = DocumentResultDelegate(self)
        self.result_view.setItemDelegate(self.result_delegate)

        # 시그널 연결
        self.result_view.selectionModel().currentChanged.connect(self._on_result_selection_changed)
        self.result_view.doubleClicked.connect(self._on_result_double_clicked)
        self.result_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.result_view.customContextMenuRequested.connect(self._show_result_context_menu)

        result_layout.addWidget(self.result_view)
        self.result_stack.addWidget(result_container)

        # 초기에는 empty state 표시
        self.result_stack.setCurrentIndex(0)

        layout.addWidget(self.result_stack, 1)

        return panel

    def _build_preview_panel(self) -> QWidget:
        """통합 미리보기 패널 - QWebEngineView 기반"""
        panel = QFrame()
        panel.setObjectName("panelCard")
        # 미리보기 패널이 splitter 비율을 벗어나 확장되지 않도록 제한
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.preview_title = QLabel("미리보기")
        self.preview_title.setObjectName("sectionTitle")
        layout.addWidget(self.preview_title)

        # 통합 미리보기 위젯 (QWebEngineView 기반)
        self.integrated_previewer = IntegratedPreviewer()
        self.integrated_previewer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.integrated_previewer, 1)

        return panel

    def _load_dummy_results_for_test(self) -> None:
        # 결과 초기화
        self.result_model.clear()
        self._result_payloads.clear()
        self.result_stack.setCurrentIndex(0)
        dummy_rows = [
            {
                "file_name": "아파트 공동체 활성화 실행계획서.pdf",
                "file_path": r"C:\\Temp\\docs\\아파트 공동체 활성화 실행계획서.pdf",
                "snippet": "...이문 지역 공동체 프로그램 운영 계획...",
                "preview": "이문 지역 공동체 활성화를 위한 연간 실행 계획입니다. 주민 참여형 행사 및 예산 편성 기준이 포함되어 있습니다.",
                "created_at": "2026-04-01 10:20",
                "modified_at": "2026-04-03 14:05",
                "file_size": "2.1 MB",
                "file_kind": "PDF",
            },
            {
                "file_name": "주간업무보고_5월3주차.docx",
                "file_path": r"C:\\Temp\\docs\\주간업무보고_5월3주차.docx",
                "snippet": "...이문역 주변 상권 분석 결과 정리...",
                "preview": "주간업무보고에는 이문역 주변 상권 분석, 다음 주 실행 항목, 리스크 관리 체크리스트가 포함됩니다.",
                "created_at": "2026-03-28 09:11",
                "modified_at": "2026-04-04 08:42",
                "file_size": "384 KB",
                "file_kind": "DOCX",
            },
            {
                "file_name": "회의록_주민협의체.hwpx",
                "file_path": r"C:\\Temp\\docs\\회의록_주민협의체.hwpx",
                "snippet": "...이문 주민협의체 2차 회의 의결사항...",
                "preview": "2차 회의에서 논의된 의결사항은 주차 공간 개선안, 커뮤니티센터 야간 개방, 분기별 만족도 조사 시행입니다.",
                "created_at": "2026-04-02 13:00",
                "modified_at": "2026-04-02 17:33",
                "file_size": "1.0 MB",
                "file_kind": "HWPX",
            },
            {
                "file_name": "예산배정표.xlsx",
                "file_path": r"C:\\Temp\\docs\\예산배정표.xlsx",
                "snippet": "...이문 커뮤니티 프로그램 예산 항목...",
                "preview": "예산배정표에는 문화행사, 시설개선, 홍보비, 운영인력 항목별 분기 예산이 포함되어 있습니다.",
                "created_at": "2026-03-25 16:22",
                "modified_at": "2026-04-05 09:12",
                "file_size": "212 KB",
                "file_kind": "XLSX",
            },
        ]

        for row in dummy_rows:
            self._append_result(
                file_name=row["file_name"],
                file_path=row["file_path"],
                snippet=row["snippet"],
                preview=row["preview"],
                created_at=row["created_at"],
                modified_at=row["modified_at"],
                file_size=row["file_size"],
                file_kind=row["file_kind"],
            )

    def _connect_signals(self) -> None:
        self.search_button.clicked.connect(self._start_search)
        self.search_input.returnPressed.connect(self._start_search)
        self.cancel_button.clicked.connect(self._cancel_search)
        self.include_snippet_checkbox.toggled.connect(self._rerender_result_items)
        self.folder_tree.itemClicked.connect(lambda item, *_: self._handle_folder_tree_item_clicked(item))
        self.folder_tree.itemChanged.connect(self._handle_folder_item_changed)
        self.folder_tree.itemExpanded.connect(self._populate_folder_children)
        self.folder_tree.itemSelectionChanged.connect(self._sync_selected_folder)
        for checkbox in self.file_type_checkboxes.values():
            checkbox.toggled.connect(self._update_conditions_summary)

    def _build_menu(self) -> None:
        refresh_action = QAction("새로고침", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._start_search)

        clear_action = QAction("선택 해제", self)
        clear_action.setShortcut("Esc")
        clear_action.triggered.connect(self._clear_preview)

        toolbar = self.addToolBar("Quick Actions")
        toolbar.setMovable(False)
        toolbar.addAction(refresh_action)
        toolbar.addAction(clear_action)

    def _handle_folder_tree_item_clicked(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        node_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if node_type == 'folder' and path:
            self._navigate_to_path(path)

    def _handle_folder_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0 or self._syncing_folder_checks:
            return
        if item.data(0, Qt.ItemDataRole.UserRole + 1) != 'folder':
            return
        self._set_folder_check_state(item, item.checkState(0))
        self._update_checked_paths_label()

    def _sync_selected_folder(self) -> None:
        item = self.folder_tree.currentItem()
        if item is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        self.current_folder = path
        self.folder_path_edit.setText(self.current_folder)
        self.folder_path_edit.setCursorPosition(0)

    def _populate_folder_tree(self) -> None:
        self.folder_tree.clear()

        favorites_item = QTreeWidgetItem(["즐겨찾기"])
        favorites_item.setData(0, Qt.ItemDataRole.UserRole + 1, 'group')

        this_pc_item = QTreeWidgetItem(["내 PC"])
        this_pc_item.setData(0, Qt.ItemDataRole.UserRole + 1, 'group')

        # Windows 탐색기의 Known Folder 경로를 우선 사용하여 실제 대상 폴더를 일치시킨다.
        known_folder_guids = {
            'Desktop': '{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}',
            'Documents': '{FDD39AD0-238F-46AF-ADB4-6C85480369C7}',
            'Downloads': '{374DE290-123F-4565-9164-39C4925E467B}',
            'Pictures': '{33E28130-4E1E-4676-835A-98395C3BC3BB}',
        }
        favorite_candidates: list[tuple[str, Path]] = []
        for key in ('Desktop', 'Documents', 'Downloads', 'Pictures'):
            known_path = get_windows_known_folder_path(known_folder_guids[key])
            candidate = Path(known_path) if known_path else (Path.home() / key)
            favorite_candidates.append((key, candidate))

        labels = {
            'Desktop': '바탕 화면',
            'Documents': '문서',
            'Downloads': '다운로드',
            'Pictures': '사진',
        }
        for folder_key, folder in favorite_candidates:
            if folder.exists():
                item = self._create_folder_item(str(folder), labels.get(folder_key, folder_key))
                favorites_item.addChild(item)

        for drive in QDir.drives():
            drive_path = drive.absoluteFilePath()
            label = drive_path.rstrip('\\/') or drive_path
            item = self._create_folder_item(drive_path, label)
            this_pc_item.addChild(item)

        self.folder_tree.addTopLevelItem(favorites_item)
        self.folder_tree.addTopLevelItem(this_pc_item)
        favorites_item.setExpanded(True)
        this_pc_item.setExpanded(True)

    def _create_folder_item(self, folder_path: str, label: str | None = None) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label or Path(folder_path).name or folder_path])
        normalized_path = os.path.normpath(folder_path)
        item.setData(0, Qt.ItemDataRole.UserRole, normalized_path)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, 'folder')
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, self._effective_check_state(normalized_path))
        if self._has_child_directories(folder_path):
            item.addChild(QTreeWidgetItem(["..."]))
        return item

    def _effective_check_state(self, folder_path: str) -> Qt.CheckState:
        normalized_path = os.path.normpath(folder_path)
        if normalized_path in self.checked_folder_paths_set:
            return Qt.CheckState.Checked
        if any(normalized_path.startswith(base + os.sep) for base in self.checked_folder_paths_set):
            return Qt.CheckState.Checked
        return Qt.CheckState.Unchecked

    def _has_child_directories(self, folder_path: str) -> bool:
        try:
            with os.scandir(folder_path) as entries:
                return any(entry.is_dir() for entry in entries)
        except OSError:
            return False

    def _populate_folder_children(self, item: QTreeWidgetItem) -> None:
        if item.data(0, Qt.ItemDataRole.UserRole + 1) != 'folder':
            return
        if item.childCount() == 1 and item.child(0).data(0, Qt.ItemDataRole.UserRole) is None:
            item.takeChildren()
            folder_path = item.data(0, Qt.ItemDataRole.UserRole)
            try:
                child_paths = sorted(
                    [entry.path for entry in os.scandir(folder_path) if entry.is_dir()],
                    key=lambda path: Path(path).name.lower(),
                )
            except OSError:
                child_paths = []
            for child_path in child_paths:
                child_item = self._create_folder_item(child_path)
                item.addChild(child_item)

    def _set_folder_check_state(self, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        self._syncing_folder_checks = True
        try:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            normalized_path = os.path.normpath(path) if path else ''
            if normalized_path:
                if state == Qt.CheckState.Checked:
                    self.checked_folder_paths_set = {
                        checked_path for checked_path in self.checked_folder_paths_set if not normalized_path.startswith(checked_path + os.sep)
                    }
                    self.checked_folder_paths_set = {
                        checked_path for checked_path in self.checked_folder_paths_set if not checked_path.startswith(normalized_path + os.sep)
                    }
                    self.checked_folder_paths_set.add(normalized_path)
                else:
                    self.checked_folder_paths_set = {
                        checked_path for checked_path in self.checked_folder_paths_set if checked_path != normalized_path and not checked_path.startswith(normalized_path + os.sep)
                    }
            item.setCheckState(0, state)
            self._refresh_loaded_descendant_check_states(item)
        finally:
            self._syncing_folder_checks = False

    def _refresh_loaded_descendant_check_states(self, parent_item: QTreeWidgetItem) -> None:
        for index in range(parent_item.childCount()):
            child = parent_item.child(index)
            if child.data(0, Qt.ItemDataRole.UserRole + 1) != 'folder':
                continue
            child_path = child.data(0, Qt.ItemDataRole.UserRole)
            child.setCheckState(0, self._effective_check_state(child_path))
            self._refresh_loaded_descendant_check_states(child)

    def _navigate_to_path(self, target_path: str) -> None:
        self.current_folder = target_path
        self.folder_path_edit.setText(target_path)
        self.folder_path_edit.setCursorPosition(0)

    def _selected_extensions(self) -> set[str]:
        return {extension for extension, checkbox in self.file_type_checkboxes.items() if checkbox.isChecked()}

    def _update_conditions_summary(self) -> None:
        selected_labels = [label for extension, label in self.supported_file_types.items() if self.file_type_checkboxes[extension].isChecked()]
        if not selected_labels:
            self.conditions_summary_label.setText('선택된 문서 형식이 없습니다.')
            return
        snippet_mode = '포함' if self.include_snippet_checkbox.isChecked() else '미포함'
        self.conditions_summary_label.setText('검색 대상 형식: ' + ', '.join(selected_labels) + f' | 조각 문구: {snippet_mode}')

    def _start_search(self) -> None:
        # 결과 초기화
        self.result_model.clear()
        self._result_payloads.clear()
        self.result_count_label.setText("0개 문서")
        self.result_stack.setCurrentIndex(0)  # Empty state로 전환
        self._clear_preview()

        checked_folders = sorted(self.checked_folder_paths_set)
        if not checked_folders:
            QMessageBox.information(self, "폴더 선택", "왼쪽 트리에서 검색할 폴더를 체크하세요.")
            return

        query = self.search_input.text().strip()
        if not query:
            QMessageBox.information(self, "검색어 입력", "검색어를 입력하세요.")
            return

        selected_extensions = self._selected_extensions()
        if not selected_extensions:
            QMessageBox.information(self, "파일 형식 선택", "하나 이상의 문서 파일 형식을 선택하세요.")
            return

        print(
            f"[DocumentSearch] start requested folders={checked_folders} "
            f"extensions={sorted(selected_extensions)} query={query!r}"
        )

        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.cancel()
            self.search_worker.wait()

        self.search_button.setEnabled(False)
        self.folder_tree.setEnabled(False)
        self.cancel_button.setVisible(True)
        
        # 진행 바 초기화
        self.progress_bar.setValue(0)
        self.progress_title.setText("검색 시작")
        self.progress_status.setText(f"{len(checked_folders)}개 폴더 검색 준비 중...")
        self.progress_details.setText(f"검색어: '{query}' | 파일 형식: {', '.join([self.supported_file_types[ext] for ext in selected_extensions])}")
        
        # 현재 검색어 저장 (강조 표시용)
        self._current_query = query

        self.search_worker = SearchWorker(checked_folders, query, selected_extensions, self)
        self.search_worker.result_found.connect(self._append_result)
        self.search_worker.progress_changed.connect(self._update_progress)
        self.search_worker.search_finished.connect(self._finish_search)
        self.search_worker.search_failed.connect(self._fail_search)
        self.search_worker.start()

    def _append_result(self, file_name: str, file_path: str, snippet: str, preview: str, created_at: str, modified_at: str, file_size: str, file_kind: str) -> None:
        payload = {
            'file_name': file_name,
            'file_path': file_path,
            'snippet': snippet,
            'preview': preview,
            'created_at': created_at,
            'modified_at': modified_at,
            'file_size': file_size,
            'file_kind': file_kind,
        }
        self._result_payloads.append(payload)
        self._append_result_item(payload)

    def _append_result_item(self, payload: dict[str, str]) -> None:
        """검색 결과 아이템을 모델에 추가 (QListView 기반)"""
        # 모델에 추가
        self.result_model.append_item(payload)

        # 결과 카운트 업데이트
        count = len(self._result_payloads)
        self.result_count_label.setText(f"{count}개 문서")

        # 첫 번째 결과일 때 결과 뷰 표시
        if count == 1:
            self.result_stack.setCurrentIndex(1)  # 결과 리스트 페이지로 전환
            # 조각 문구 상태 동기화
            include_snippet = self.include_snippet_checkbox.isChecked()
            self.result_model.set_include_snippet(include_snippet)
            self.snippet_toggle_btn.setChecked(include_snippet)
            # 검색어 설정
            self.result_model.set_search_query(self._current_query)
            # 첫 번째 아이템 선택
            self.result_view.setCurrentIndex(self.result_proxy.index(0, 0))
    
    def _on_result_double_clicked(self, index: QModelIndex) -> None:
        """검색 결과 더블클릭 시 파일 열기 (QListView 기반)"""
        source_index = self.result_proxy.mapToSource(index)
        payload = self.result_model.get_payload_at(source_index.row())
        if payload:
            file_path = payload.get('file_path', '')
            if file_path and os.path.exists(file_path):
                self._open_file(file_path)

    def _show_result_context_menu(self, position: QPoint) -> None:
        """검색 결과 우클릭 컨텍스트 메뉴 표시 (QListView 기반)"""
        index = self.result_view.indexAt(position)
        if not index.isValid():
            return

        # 선택된 아이템으로 변경
        self.result_view.setCurrentIndex(index)

        # payload 가져오기
        source_index = self.result_proxy.mapToSource(index)
        payload = self.result_model.get_payload_at(source_index.row())
        if not payload:
            return

        file_path = payload.get('file_path', '')
        if not file_path:
            return

        # 컨텍스트 메뉴 생성
        menu = QMenu(self)

        # 파일 열기 메뉴
        open_action = QAction("파일 열기", self)
        open_action.triggered.connect(lambda: self._open_file(file_path))
        menu.addAction(open_action)

        # 폴더 열기 메뉴
        folder_action = QAction("파일 경로 열기", self)
        folder_action.triggered.connect(lambda: self._open_folder(file_path))
        menu.addAction(folder_action)

        # 메뉴 표시
        menu.exec(self.result_view.viewport().mapToGlobal(position))

    def _open_file(self, file_path: str) -> None:
        """파일 열기"""
        try:
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            else:  # macOS, Linux
                subprocess.run(['xdg-open', file_path], check=True)
        except Exception as e:
            QMessageBox.warning(self, "파일 열기 오류", f"파일을 열 수 없습니다:\n{e}")

    def _open_folder(self, file_path: str) -> None:
        """파일이 있는 폴더 열기 - 파일 관리자 위젯에서 오른쪽 패널에 표시"""
        try:
            folder_path = os.path.dirname(file_path)
            
            # 메인 윈도우에 파일 관리자 열기 요청
            main_window = self.window()
            if main_window and hasattr(main_window, 'open_file_manager_with_folder'):
                main_window.open_file_manager_with_folder(folder_path)
            else:
                # 메인 윈도우 메서드가 없으면 시스템 탐색기로 폴백
                if os.name == 'nt':  # Windows
                    subprocess.run(f'explorer /select,"{file_path}"', shell=True, check=True)
                else:  # macOS, Linux
                    subprocess.run(['xdg-open', folder_path], check=True)
        except Exception as e:
            QMessageBox.warning(self, "폴더 열기 오류", f"폴더를 열 수 없습니다:\n{e}")

    def _rerender_result_items(self, checked: bool | None = None) -> None:
        """조각 문구 표시 상태 변경 시 결과 재렌더링"""
        if not hasattr(self, 'result_view'):
            return

        # 현재 선택된 파일 경로 저장
        selected_path = self.current_preview_path

        # 조각 문구 상태 업데이트
        include_snippet = self.include_snippet_checkbox.isChecked()
        self.result_model.set_include_snippet(include_snippet)
        self.snippet_toggle_btn.setChecked(include_snippet)

        # 선택 복원
        if selected_path:
            for row in range(self.result_model.rowCount()):
                payload = self.result_model.get_payload_at(row)
                if payload and payload.get('file_path') == selected_path:
                    proxy_index = self.result_proxy.mapFromSource(self.result_model.index(row, 0))
                    self.result_view.setCurrentIndex(proxy_index)
                    break

        self._update_conditions_summary()

    def _on_result_selection_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        """QListView 선택 변경 처리"""
        if not current.isValid():
            return

        # 소스 모델 인덱스로 변환
        source_index = self.result_proxy.mapToSource(current)
        payload = self.result_model.get_payload_at(source_index.row())

        if payload:
            file_path = payload.get('file_path', '')
            preview = payload.get('preview', '')
            file_name = payload.get('file_name', '')
            self._load_preview(file_path, preview, file_name)
        else:
            self._clear_preview()

    def _update_progress(self, current: int, total: int, current_file: str) -> None:
        file_name = os.path.basename(current_file)
        percentage = int((current / total) * 100) if total > 0 else 0
        
        # 진행 바 업데이트
        self.progress_bar.setValue(percentage)
        self.progress_title.setText(f"검색 진행 중 ({percentage}%)")
        self.progress_status.setText(f"{current:,} / {total:,} 파일 스캔 중")
        self.progress_details.setText(f"현재 파일: {file_name}")
        
        # 진행 정보는 검색 조건 탭에서만 표시됨

    def _finish_search(self, found_count: int, scanned_count: int, cancelled: bool) -> None:
        self.search_button.setEnabled(True)
        self.folder_tree.setEnabled(True)
        self.cancel_button.setVisible(False)

        # 결과가 있으면 결과 뷰로 전환, 없으면 empty state 유지
        if found_count > 0:
            self.result_stack.setCurrentIndex(1)
        else:
            self.result_stack.setCurrentIndex(0)
        print(f"[DocumentSearch] finish signal scanned={scanned_count} found={found_count} cancelled={cancelled}")
        
        # 진행 바 완료 처리
        self.progress_bar.setValue(100)
        if cancelled:
            self.progress_title.setText("검색 취소됨")
            self.progress_status.setText(f"{scanned_count:,}개 파일 확인, {found_count}개 결과")
            self.progress_details.setText("검색이 사용자에 의해 취소되었습니다.")
        else:
            self.progress_title.setText("검색 완료")
            self.progress_status.setText(f"{scanned_count:,}개 파일 확인, {found_count:,}개 결과")
            self.progress_details.setText("모든 파일 검색이 완료되었습니다.")

    def _on_sort_changed(self, index: int) -> None:
        """정렬 기준 변경 처리"""
        sort_key = self.sort_combo.currentData()

        if sort_key == "relevance":
            # 관련도순: 원본 순서 유지
            self.result_proxy.setSortRole(Qt.ItemDataRole.DisplayRole)
            self.result_proxy.sort(-1, Qt.SortOrder.AscendingOrder)  # 정렬 해제
        elif sort_key == "modified":
            # 수정일순
            self.result_proxy.setSortRole(SortTimestampRole)
            self.result_proxy.sort(0, Qt.SortOrder.DescendingOrder)
        elif sort_key == "filename":
            # 파일명순
            self.result_proxy.setSortRole(FileNameRole)
            self.result_proxy.sort(0, Qt.SortOrder.AscendingOrder)
        elif sort_key == "filekind":
            # 종류순
            self.result_proxy.setSortRole(FileKindRole)
            self.result_proxy.sort(0, Qt.SortOrder.AscendingOrder)

    def _on_snippet_toggle(self, checked: bool) -> None:
        """조각 문구 토글 버튼 클릭 처리"""
        # 체크박스와 동기화
        self.include_snippet_checkbox.setChecked(checked)
        # 모델 업데이트
        self.result_model.set_include_snippet(checked)
        # 델리게이트 크기 힌트가 변경되므로 뷰 업데이트
        self.result_view.update()

    def _fail_search(self, message: str) -> None:
        self.search_button.setEnabled(True)
        self.folder_tree.setEnabled(True)
        self.cancel_button.setVisible(False)
        self.result_stack.setCurrentIndex(0)  # Empty state
        
        # 진행 바 오류 처리
        self.progress_bar.setValue(0)
        self.progress_title.setText("검색 오류")
        self.progress_status.setText("검색 중 오류가 발생했습니다.")
        self.progress_details.setText(f"오류 내용: {message}")
        print(f"[DocumentSearch] fail signal message={message}")
        QMessageBox.critical(self, "검색 오류", message)

    def _cancel_search(self) -> None:
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.cancel()

    def _load_preview(self, file_path: str, preview: str, file_name: str) -> None:
        """통합 미리보기 로드 - QWebEngineView 기반"""
        self.preview_title.setText(file_name if file_name else "미리보기")
        self.current_preview_path = file_path
        
        if not file_path or not Path(file_path).exists():
            self.integrated_previewer._show_error("파일을 찾을 수 없습니다.")
            return
        
        # 통합 미리보기 위젯에 파일 로드 (비동기)
        self.integrated_previewer.preview_file(file_path, file_name or Path(file_path).name)

    def _update_checked_paths_label(self) -> None:
        checked_folders = sorted(self.checked_folder_paths_set)
        if not checked_folders:
            self.checked_paths_label.setText("선택된 폴더 없음")
            return
        if len(checked_folders) == 1:
            self.checked_paths_label.setText(checked_folders[0])
        else:
            self.checked_paths_label.setText(f"{len(checked_folders)}개 폴더 선택됨")

    def _render_pdf_preview(self, file_path: str) -> None:
        """PDF 파일 미리보기 - PyMuPDF로 1페이지를 이미지로 렌더링"""
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(file_path)
            if doc.page_count == 0:
                self._show_preview_error("PDF 페이지가 없습니다.")
                return
            
            # 첫 페이지 렌더링
            page = doc.load_page(0)
            
            # 적절한 해상도로 렌더링 (150 DPI 기준)
            mat = fitz.Matrix(1.5, 1.5)
            pix = page.get_pixmap(matrix=mat)
            
            # QImage로 변환
            img_data = pix.tobytes("ppm")
            image = QImage.fromData(img_data, "ppm")
            
            if image.isNull():
                self._show_preview_error("PDF 이미지 변환에 실패했습니다.")
                return
            
            # QPixmap으로 변환하여 preview 영역에 맞춰 표시
            pixmap = QPixmap.fromImage(image)
            self._preview_original_pixmap = pixmap

            # 스택 위젯을 이미지 페이지로 전환
            self.preview_stack.setCurrentIndex(PREVIEW_PAGE_IMAGE)
            self._apply_preview_pixmap()

            doc.close()
            
        except ImportError:
            self._show_preview_error("PDF 미리보기를 위한 PyMuPDF 라이브러리가 설치되지 않았습니다.")
        except Exception as e:
            print(f"[Preview] PDF rendering error: {e}")
            self._show_preview_error("PDF 미리보기를 생성할 수 없습니다.")

    def _render_spreadsheet_preview(self, file_path: str, suffix: str) -> None:
        """엑셀/CSV 파일 미리보기 - pandas로 상위 30줄을 HTML 테이블로 변환"""
        try:
            import pandas as pd
            
            # 파일 형식에 따라 읽기
            if suffix == '.csv':
                # CSV는 인코딩 자동 감지
                encodings = ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr']
                df = None
                for encoding in encodings:
                    try:
                        df = pd.read_csv(file_path, nrows=30, encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                if df is None:
                    raise ValueError("CSV 인코딩을 감지할 수 없습니다.")
            elif suffix == '.cell':
                # 한셀 파일은 pyhwp 또는 pandas 엔진 필요
                try:
                    df = pd.read_excel(file_path, nrows=30, engine='xlrd')
                except:
                    df = pd.read_excel(file_path, nrows=30, engine='openpyxl')
            else:
                # xlsx - 첫 번째 시트 읽기
                df = pd.read_excel(file_path, sheet_name=0, nrows=30, engine='openpyxl')
            
            # HTML 테이블로 변환 (스타일 적용)
            html_table = df.to_html(
                index=False,
                classes='preview-table',
                border=0,
                max_rows=30,
                max_cols=20
            )
            
            # HTML 문서 구성
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
                        font-size: 13px;
                        margin: 0;
                        padding: 10px;
                        background: #FFFFFF;
                    }}
                    .preview-table {{
                        border-collapse: collapse;
                        width: 100%;
                        font-size: 12px;
                    }}
                    .preview-table th {{
                        background: #F2F2F7;
                        color: #3C3C43;
                        padding: 8px 10px;
                        text-align: left;
                        font-weight: 600;
                        border-bottom: 1px solid #C6C6C8;
                        white-space: nowrap;
                    }}
                    .preview-table td {{
                        padding: 6px 10px;
                        border-bottom: 1px solid #E5E5EA;
                        color: #1C1C1E;
                    }}
                    .preview-table tr:hover {{
                        background: rgba(0, 122, 255, 0.06);
                    }}
                    .info {{
                        color: #8E8E93;
                        font-size: 11px;
                        margin-bottom: 10px;
                        padding: 8px;
                        background: #F2F2F7;
                        border-radius: 8px;
                    }}
                </style>
            </head>
            <body>
                <div class="info">미리보기: 상위 {min(30, len(df))}행 / 전체 {len(df)}+행 (총 {len(df.columns)}열)</div>
                {html_table}
            </body>
            </html>
            """
            
            # 스택 위젯을 텍스트 페이지로 전환
            self.preview_stack.setCurrentIndex(PREVIEW_PAGE_TEXT)
            self.preview_text_browser.setHtml(html_content)
            
        except ImportError:
            self._show_preview_error("스프레드시트 미리보기를 위한 pandas/openpyxl 라이브러리가 설치되지 않았습니다.")
        except Exception as e:
            print(f"[Preview] Spreadsheet rendering error: {e}")
            self._show_preview_error(f"스프레드시트 미리보기를 생성할 수 없습니다: {str(e)[:100]}")

    def _render_text_preview(self, file_path: str, preview_text: str) -> None:
        """텍스트 문서 미리보기 - HTML 형식으로 스타일링"""
        try:
            # 텍스트 추출 (기존 preview 또는 새로 추출)
            text = preview_text or ""
            
            if not text:
                extractor = get_extractor(file_path)
                if extractor:
                    text = extractor.extract_text(file_path) or ""
            
            # 앞부분 1000자만 사용
            text = text[:1000]
            
            # 첫 줄을 제목으로, 나머지를 본문으로 분리
            lines = text.split('\n', 1)
            title = lines[0].strip() if lines else ""
            body = lines[1].strip() if len(lines) > 1 else ""
            
            # HTML 이스케이프
            import html
            title = html.escape(title)
            body = html.escape(body).replace('\n', '<br>')
            
            # HTML 문서 구성
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
                        font-size: 14px;
                        line-height: 1.6;
                        margin: 0;
                        padding: 16px;
                        background: #FFFFFF;
                        color: #1C1C1E;
                    }}
                    h1 {{
                        font-size: 18px;
                        font-weight: 700;
                        color: #1C1C1E;
                        margin: 0 0 12px 0;
                        padding-bottom: 8px;
                        border-bottom: 2px solid #007AFF;
                    }}
                    p {{
                        margin: 0;
                        color: #3C3C43;
                    }}
                    .preview-info {{
                        color: #8E8E93;
                        font-size: 11px;
                        margin-top: 16px;
                        padding-top: 12px;
                        border-top: 1px solid #E5E5EA;
                    }}
                </style>
            </head>
            <body>
                <h1>{title or "제목 없음"}</h1>
                <p>{body or "(내용 없음)"}</p>
                <div class="preview-info">미리보기: 앞부분 1000자까지 표시</div>
            </body>
            </html>
            """
            
            # 스택 위젯을 텍스트 페이지로 전환
            self.preview_stack.setCurrentIndex(PREVIEW_PAGE_TEXT)
            self.preview_text_browser.setHtml(html_content)
            
        except Exception as e:
            print(f"[Preview] Text rendering error: {e}")
            self._show_preview_error("텍스트 미리보기를 생성할 수 없습니다.")

    def _render_plain_preview(self, preview_text: str) -> None:
        """일반 텍스트 미리보기"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
                    font-size: 14px;
                    line-height: 1.6;
                    margin: 0;
                    padding: 16px;
                    background: #FFFFFF;
                    color: #3C3C43;
                }}
            </style>
        </head>
        <body>
            <pre>{preview_text or "문서를 선택하면 미리보기가 표시됩니다."}</pre>
        </body>
        </html>
        """
        self.preview_stack.setCurrentIndex(PREVIEW_PAGE_TEXT)
        self.preview_text_browser.setHtml(html_content)

    def _show_preview_error(self, message: str) -> None:
        """미리보기 오류 표시 - 중앙 정렬된 안내 텍스트"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
                    margin: 0;
                    padding: 40px 20px;
                    background: #F2F2F7;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 200px;
                }}
                .error-container {{
                    text-align: center;
                    color: #8E8E93;
                }}
                .error-icon {{
                    font-size: 48px;
                    margin-bottom: 16px;
                }}
                .error-message {{
                    font-size: 14px;
                    color: #8E8E93;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <div class="error-icon">📄</div>
                <div class="error-message">{message}</div>
            </div>
        </body>
        </html>
        """
        self.preview_stack.setCurrentIndex(PREVIEW_PAGE_TEXT)
        self.preview_text_browser.setHtml(html_content)

    def _update_preview_surface(self, file_path: str, preview_text: str) -> None:
        """이전 버전 호환용 - 이미지 파일 미리보기 (유지보수용)"""
        suffix = Path(file_path).suffix.lower()
        image_suffixes = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}
        
        if suffix in image_suffixes and Path(file_path).exists():
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self._preview_original_pixmap = pixmap
                self.preview_stack.setCurrentIndex(PREVIEW_PAGE_IMAGE)
                self._apply_preview_pixmap()
                return
        
        # 이미지가 아니면 텍스트로 표시
        self._render_plain_preview(preview_text)

    def _clear_preview(self) -> None:
        """미리보기 초기화 - 통합 미리보기 사용"""
        if hasattr(self, 'result_view'):
            self.result_view.clearSelection()
        self.preview_title.setText("미리보기")
        self.current_preview_path = ''
        self._preview_original_pixmap = None
        
        # 통합 미리보기 클리어
        if hasattr(self, 'integrated_previewer'):
            self.integrated_previewer.clear_preview()
        
        # 진행 상태 초기화 (검색 시작 전 상태로)
        if not self.search_worker or not self.search_worker.isRunning():
            self.progress_bar.setValue(0)
            self.progress_title.setText("검색 준비")
            self.progress_status.setText("폴더를 선택하고 검색어를 입력하세요.")
            self.progress_details.setText("")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            /* ── iOS-style Document Search ── */
            QMainWindow {
                background: #F2F2F7;
            }
            QToolBar {
                background: transparent;
                border: none;
                spacing: 6px;
                padding: 0 0 8px 0;
            }
            QToolButton {
                background: #FFFFFF;
                border: 0.5px solid #C6C6C8;
                border-radius: 12px;
                padding: 7px 12px;
                color: #007AFF;
                font-weight: 500;
            }
            QToolButton:hover {
                background: rgba(0, 122, 255, 0.06);
            }
            #panelCard {
                background: #FFFFFF;
                border: 0.5px solid #C6C6C8;
                border-radius: 16px;
            }
            QLabel {
                color: #1C1C1E;
            }
            #sectionTitle {
                font-size: 17px;
                font-weight: 700;
                color: #1C1C1E;
                padding: 2px 2px 8px 2px;
                letter-spacing: -0.4px;
            }
            #fieldLabel {
                font-size: 13px;
                font-weight: 600;
                color: #3C3C43;
                padding-top: 4px;
            }
            #metaLabel {
                color: #8E8E93;
                font-size: 12px;
            }
            #innerCard {
                background: #F2F2F7;
                border: 0.5px solid #C6C6C8;
                border-radius: 14px;
            }
            QLineEdit, QTextEdit, QTreeWidget, QTreeView {
                background: #FFFFFF;
                border: 0.5px solid #C6C6C8;
                border-radius: 12px;
                padding: 9px 12px;
                color: #1C1C1E;
                selection-background-color: rgba(0, 122, 255, 0.25);
            }
            QLineEdit:focus {
                border: 1.5px solid #007AFF;
            }
            QLineEdit[readOnly="true"] {
                color: #8E8E93;
                background: #F2F2F7;
            }
            QPushButton {
                background: #FFFFFF;
                border: 0.5px solid #C6C6C8;
                border-radius: 12px;
                padding: 0 18px;
                color: #007AFF;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(0, 122, 255, 0.06);
                border-color: #007AFF;
            }
            QPushButton:pressed {
                background: rgba(0, 122, 255, 0.12);
            }
            QCheckBox {
                color: #1C1C1E;
                spacing: 8px;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1.5px solid #C6C6C8;
                border-radius: 5px;
                background: #FFFFFF;
            }
            QCheckBox::indicator:checked {
                background: #007AFF;
                border: 1.5px solid #007AFF;
            }
            /* ── Folder Tree ── */
            QTreeWidget, QTreeView {
                outline: none;
                padding: 6px;
            }
            QTreeWidget::item, QTreeView::item {
                padding: 10px 8px;
                border-radius: 10px;
            }
            QTreeWidget::item:hover, QTreeView::item:hover {
                background: rgba(0, 122, 255, 0.06);
            }
            QTreeWidget::item:selected, QTreeView::item:selected {
                background: rgba(0, 122, 255, 0.12);
                color: #1C1C1E;
            }
            QTreeWidget::branch, QTreeView::branch {
                border-image: none;
                image: none;
                background: transparent;
            }
            /* ── Result List ── */
            QListWidget#resultList {
                outline: none;
                border: 0.5px solid #C6C6C8;
                border-radius: 14px;
                background: #FFFFFF;
                padding: 6px;
            }
            QListWidget#resultList::item {
                border: none;
                margin: 0px 0px 6px 0px;
                padding: 0px;
            }
            QListWidget#resultList::item:selected {
                background: transparent;
            }
            #resultHeaderCard {
                background: #F2F2F7;
                border: 0.5px solid #C6C6C8;
                border-radius: 12px;
            }
            #resultHeaderLabel {
                color: #8E8E93;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
            }
            /* ── Result Card ── */
            #resultItemCard {
                background: #FFFFFF;
                border: 0.5px solid #E5E5EA;
                border-radius: 14px;
            }
            #resultItemCard[selected="true"] {
                background: rgba(0, 122, 255, 0.06);
                border: 1.5px solid #007AFF;
            }
            #resultMetaLabel {
                color: #8E8E93;
                font-size: 11px;
            }
            #resultSnippetLabel {
                color: #1C1C1E;
                font-size: 12px;
                line-height: 1.4;
                background: #F2F2F7;
                border: 0.5px solid #E5E5EA;
                border-radius: 10px;
                padding: 8px 10px;
            }
            #resultItemCard[selected="true"] #resultSnippetLabel {
                background: rgba(0, 122, 255, 0.10);
                border: 0.5px solid rgba(0, 122, 255, 0.3);
                color: #003D80;
            }
            QHeaderView::section {
                background: #F2F2F7;
                color: #8E8E93;
                border: none;
                border-bottom: 0.5px solid #C6C6C8;
                padding: 8px;
                font-weight: 600;
                font-size: 12px;
            }
            /* ── Preview ── */
            QScrollArea {
                background: transparent;
                border: none;
            }
            QTextEdit {
                padding: 14px;
                border-radius: 12px;
            }
            #previewImage {
                background: #F2F2F7;
                border: 0.5px solid #C6C6C8;
                border-radius: 14px;
                min-height: 160px;
            }
            /* ── Tab Widget Reference Only (actual styles applied in _build_ui) ── */
            QTabWidget#searchTabs {
                background: transparent;
                border: none;
            }
            QListView#resultView QScrollBar::add-line:vertical,
            QListView#resultView QScrollBar::sub-line:vertical {
                height: 0px;
            }
            /* ── Result Toolbar ── */
            QLabel#resultCountLabel {
                font-size: 14px;
                font-weight: 600;
                color: #111827;
            }
            QComboBox#sortCombo {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                color: #374151;
                min-width: 100px;
            }
            QComboBox#sortCombo:hover {
                border-color: #D1D5DB;
            }
            QComboBox#sortCombo::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox#sortCombo::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #6B7280;
            }
            QPushButton#snippetToggleBtn {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                color: #374151;
            }
            QPushButton#snippetToggleBtn:checked {
                background: #3B82F6;
                border-color: #3B82F6;
                color: #FFFFFF;
            }
            QPushButton#snippetToggleBtn:hover {
                border-color: #D1D5DB;
            }
            QPushButton#snippetToggleBtn:checked:hover {
                background: #2563EB;
                border-color: #2563EB;
            }
            /* ── Progress Bar ── */
            QProgressBar {
                background: #F2F2F7;
                border: 0.5px solid #C6C6C8;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: #007AFF;
                border-radius: 2px;
            }
            /* ── Splitter ── */
            QSplitter::handle {
                background: transparent;
            }
            QSplitter::handle:hover {
                background: rgba(0, 122, 255, 0.10);
                border-radius: 3px;
            }
            /* ── Scrollbars (iOS thin) ── */
            QScrollBar:vertical, QScrollBar:horizontal {
                background: transparent;
                border: none;
                margin: 2px;
            }
            QScrollBar:vertical {
                width: 6px;
            }
            QScrollBar:horizontal {
                height: 6px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: rgba(0, 0, 0, 0.18);
                border-radius: 3px;
                min-height: 28px;
                min-width: 28px;
            }
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
                background: rgba(0, 0, 0, 0.35);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
                border: none;
            }
            """
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_fixed_splitter_ratios()
        self._apply_preview_pixmap()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_fixed_splitter_ratios()
        self._apply_preview_pixmap()

    def _apply_fixed_splitter_ratios(self) -> None:
        total_width = self.top_splitter.size().width()
        total_height = self.vertical_splitter.size().height()

        # 좌우 3:2 고정 비율 (왼쪽 60%, 오른쪽 40%) - 1/4:2/4분면, 3/4:4/4분면
        if total_width > 0:
            left = int(total_width * 0.60)
            right = max(1, total_width - left)
            self.top_splitter.setSizes([left, right])
            self.bottom_splitter.setSizes([left, right])

        # 상하 2:3 고정 비율 (상단 40%, 하단 60%)
        if total_height > 0:
            top = int(total_height * 0.40)
            bottom = max(1, total_height - top)
            self.vertical_splitter.setSizes([top, bottom])

    def _apply_preview_pixmap(self) -> None:
        if not self._preview_original_pixmap or self._preview_original_pixmap.isNull():
            return
        target_width = self.preview_image_label.width()
        target_height = self.preview_image_label.height()
        if target_width <= 0 or target_height <= 0:
            return
        scaled = self._preview_original_pixmap.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_image_label.setPixmap(scaled)

    def closeEvent(self, event) -> None:
        # 통합 미리보기 정리
        if hasattr(self, 'integrated_previewer'):
            self.integrated_previewer.cleanup()
        
        # 검색 작업 취소
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.cancel()
            self.search_worker.wait(2000)
        super().closeEvent(event)


class DocumentSearchWidget(QWidget):
    tool_key = 'document_search'
    tool_name = '🔍 문서 찾기'
    window_title = '문서 통합 검색'
    singleton = True
    enabled = True

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.window_adapter = DocumentSearchMainWindow()
        self.window_adapter.setMenuWidget(None)
        central = self.window_adapter.takeCentralWidget()
        if central is not None:
            central.setParent(self)
            layout.addWidget(central)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DocumentSearchMainWindow()
    if '--demo-results' in sys.argv:
        window._load_dummy_results_for_test()
    window.show()
    sys.exit(app.exec())
