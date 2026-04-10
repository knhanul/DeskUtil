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
    from PySide6.QtCore import QDir, QItemSelectionModel, QModelIndex, QPoint, QSize, Qt, QThread, Signal as PySideSignal
    from PySide6.QtGui import QAction, QColor, QFileSystemModel, QFont, QPixmap, QImage
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
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
    from PyQt6.QtCore import QDir, QModelIndex, QPoint, QSize, Qt, QThread, pyqtSignal
    from PyQt6.QtGui import QAction, QColor, QFileSystemModel, QFont, QPixmap, QImage
    from PyQt6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
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


current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from doc_search.extractors import get_extractor


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

        # 탭 컨테이너 생성: 검색 탭 + 조건 탭
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName('searchTabs')
        self.tab_widget.addTab(self.search_panel, '🔍 검색')
        self.tab_widget.addTab(self.conditions_panel, '⚙️ 조건')
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(False)
        self.tab_widget.setTabsClosable(False)

        self.top_splitter.addWidget(self.folder_panel)
        self.top_splitter.addWidget(self.tab_widget)
        self.bottom_splitter.addWidget(self.result_panel)
        self.bottom_splitter.addWidget(self.preview_panel)

        self.top_splitter.setStretchFactor(0, 48)
        self.top_splitter.setStretchFactor(1, 52)
        self.bottom_splitter.setStretchFactor(0, 58)
        self.bottom_splitter.setStretchFactor(1, 42)

        self.vertical_splitter.addWidget(self.top_splitter)
        self.vertical_splitter.addWidget(self.bottom_splitter)
        self.vertical_splitter.setStretchFactor(0, 33)  # 상단 1/3
        self.vertical_splitter.setStretchFactor(1, 67)  # 하단 2/3
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
        """두 번째 탭: 검색 조건 (파일 타입, 스니펫 포함 등)"""
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

        self.include_snippet_checkbox = QCheckBox("검색 결과에 스니펫 포함")
        self.include_snippet_checkbox.setChecked(True)
        layout.addWidget(self.include_snippet_checkbox)

        self.conditions_summary_label = QLabel("모든 문서 형식이 검색 대상입니다.")
        self.conditions_summary_label.setObjectName("metaLabel")
        layout.addWidget(self.conditions_summary_label)

        layout.addStretch()
        self._update_conditions_summary()
        return panel

    def _build_result_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panelCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QLabel("검색 결과")
        header.setObjectName("sectionTitle")
        layout.addWidget(header)

        # QTableWidget으로 교체
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(5)
        self.result_table.setHorizontalHeaderLabels(["파일명", "종류", "크기", "생성일", "경로"])
        
        # 행 번호 숨기기
        self.result_table.verticalHeader().setVisible(False)
        
        # 테이블 속성 설정
        self.result_table.setObjectName("resultTable")
        self.result_table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.result_table.setAlternatingRowColors(True)
        
        # 열 너비 정책 설정
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # 파일명 컬럼은 남는 공간 모두 차지
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 종류
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # 크기
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 생성일
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # 경로
        
        # 선택 변경 시그널 연결
        self.result_table.itemSelectionChanged.connect(self._handle_table_selection_changed)

        # 더블클릭으로 파일 열기
        self.result_table.itemDoubleClicked.connect(self._on_result_item_double_clicked)

        # 우클릭 컨텍스트 메뉴
        self.result_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.result_table.customContextMenuRequested.connect(self._show_result_context_menu)

        layout.addWidget(self.result_table, 1)

        self.result_meta_label = QLabel("0개 문서")
        self.result_meta_label.setObjectName("metaLabel")
        layout.addWidget(self.result_meta_label)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panelCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.preview_title = QLabel("미리보기")
        self.preview_title.setObjectName("sectionTitle")
        layout.addWidget(self.preview_title)

        # QStackedWidget for dynamic preview content
        self.preview_stack = QStackedWidget()
        self.preview_stack.setObjectName("previewStack")

        # Page 0: QLabel for image/PDF thumbnails
        self.preview_image_label = QLabel()
        self.preview_image_label.setObjectName("previewImage")
        self.preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image_label.setScaledContents(True)
        self.preview_image_label.setMinimumHeight(200)
        self.preview_stack.addWidget(self.preview_image_label)

        # Page 1: QTextBrowser for HTML/text content
        self.preview_text_browser = QTextBrowser()
        self.preview_text_browser.setObjectName("previewTextBrowser")
        self.preview_text_browser.setOpenExternalLinks(False)
        self.preview_text_browser.setPlaceholderText("문서를 선택하면 미리보기가 표시됩니다.")
        self.preview_stack.addWidget(self.preview_text_browser)

        layout.addWidget(self.preview_stack, 1)
        return panel

    def _load_dummy_results_for_test(self) -> None:
        self.result_table.setRowCount(0)  # 테이블 초기화
        self._result_payloads.clear()
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
        self.conditions_summary_label.setText('검색 대상 형식: ' + ', '.join(selected_labels) + f' | 스니펫: {snippet_mode}')

    def _start_search(self) -> None:
        self.result_table.setRowCount(0)  # 테이블 초기화
        self._result_payloads.clear()
        self.result_meta_label.setText("0개 문서")
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
        include_snippet = self.include_snippet_checkbox.isChecked()
        
        # 메타데이터 준비
        file_name = payload.get('file_name', '')
        file_path = payload.get('file_path', '')
        file_size = payload.get('file_size', '')
        file_kind = payload.get('file_kind', '')
        created_at = payload.get('created_at', '')
        modified_at = payload.get('modified_at', '')
        snippet = payload.get('snippet', '')
        preview = payload.get('preview', '')
        
        # 검색어 강조 표시 기능 제거 - 일반 텍스트로 표시
        pass
        
        if include_snippet and snippet:
            # 스니펫 포함 시: 2개의 행 삽입
            # 첫 번째 행: 메타데이터
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            
            # 메타데이터 아이템 생성
            items = [
                QTableWidgetItem(file_name),   # 파일명
                QTableWidgetItem(file_kind),   # 종류
                QTableWidgetItem(file_size),   # 크기
                QTableWidgetItem(created_at),  # 생성일
                QTableWidgetItem(file_path)    # 경로
            ]
            
            for col, item in enumerate(items):
                item.setData(Qt.ItemDataRole.UserRole, preview)  # 미리보기 데이터 저장
                item.setData(Qt.ItemDataRole.UserRole + 1, file_path)  # 파일 경로 저장
                item.setData(Qt.ItemDataRole.UserRole + 2, file_name)  # 파일 이름 저장
                self.result_table.setItem(row, col, item)
            
            # 두 번째 행: 스니펫 (5개 컬럼 병합)
            snippet_row = self.result_table.rowCount()
            self.result_table.insertRow(snippet_row)
            
            snippet_item = QTableWidgetItem(snippet)
            snippet_item.setForeground(QColor('#6b7280'))  # 옅은 회색
            snippet_item.setFont(QFont("Segoe UI", 9))  # 약간 작은 폰트
            snippet_item.setData(Qt.ItemDataRole.UserRole, preview)  # 미리보기 데이터 저장
            snippet_item.setData(Qt.ItemDataRole.UserRole + 1, file_path)  # 파일 경로 저장
            snippet_item.setData(Qt.ItemDataRole.UserRole + 2, file_name)  # 파일 이름 저장
            
            self.result_table.setItem(snippet_row, 0, snippet_item)
            self.result_table.setSpan(snippet_row, 0, 1, 5)  # 5개 컬럼 병합
            
        else:
            # 스니펫 미포함 시: 1개의 행만 삽입
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            
            # 메타데이터 아이템 생성
            items = [
                QTableWidgetItem(file_name),   # 파일명
                QTableWidgetItem(file_kind),   # 종류
                QTableWidgetItem(file_size),   # 크기
                QTableWidgetItem(created_at),  # 생성일
                QTableWidgetItem(file_path)    # 경로
            ]
            
            for col, item in enumerate(items):
                item.setData(Qt.ItemDataRole.UserRole, preview)  # 미리보기 데이터 저장
                item.setData(Qt.ItemDataRole.UserRole + 1, file_path)  # 파일 경로 저장
                item.setData(Qt.ItemDataRole.UserRole + 2, file_name)  # 파일 이름 저장
                self.result_table.setItem(row, col, item)
        
        # 행 높이 자동 조절
        self.result_table.resizeRowsToContents()
        
        # 결과 카운트 업데이트
        self.result_meta_label.setText(f"{len(self._result_payloads)}개 문서")
        
        # 첫 번째 결과 자동 선택
        if self.result_table.currentRow() == -1:
            self.result_table.selectRow(0)
            self._handle_table_selection_changed()
    
    def _on_result_item_double_clicked(self, item) -> None:
        """검색 결과 더블클릭 시 파일 열기"""
        file_path = item.data(Qt.ItemDataRole.UserRole + 1)
        if file_path and os.path.exists(file_path):
            self._open_file(file_path)

    def _show_result_context_menu(self, position: QPoint) -> None:
        """검색 결과 우클릭 컨텍스트 메뉴 표시"""
        current_row = self.result_table.currentRow()
        if current_row < 0:
            return

        # 현재 행에서 파일 경로 가져오기
        item = self.result_table.item(current_row, 0)
        if not item:
            return

        file_path = item.data(Qt.ItemDataRole.UserRole + 1)
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
        menu.exec(self.result_table.viewport().mapToGlobal(position))

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
        """파일이 있는 폴더 열기"""
        try:
            folder_path = os.path.dirname(file_path)
            if os.name == 'nt':  # Windows
                # Use shell=True for proper path handling with special characters
                import subprocess
                subprocess.run(f'explorer /select,"{file_path}"', shell=True, check=True)
            else:  # macOS, Linux
                subprocess.run(['xdg-open', folder_path], check=True)
        except Exception as e:
            QMessageBox.warning(self, "폴더 열기 오류", f"폴더를 열 수 없습니다:\n{e}")

    def _rerender_result_items(self, checked: bool | None = None) -> None:
        if not hasattr(self, 'result_table'):
            return
        selected_path = self.current_preview_path
        self.result_table.setRowCount(0)  # 테이블 초기화
        for payload in self._result_payloads:
            self._append_result_item(payload)
        if selected_path:
            # 선택된 경로에 해당하는 행 찾기
            for row in range(self.result_table.rowCount()):
                item = self.result_table.item(row, 0)  # 첫 번째 컬럼에서 데이터 확인
                if item and item.data(Qt.ItemDataRole.UserRole + 1) == selected_path:
                    self.result_table.selectRow(row)
                    break
        self._update_conditions_summary()

    def _handle_table_selection_changed(self) -> None:
        """QTableWidget 선택 변경 처리 - 스니펫 행과 메타데이터 행 연동"""
        current_row = self.result_table.currentRow()
        if current_row >= 0:
            # 현재 행이 스니펫 행인지 확인 (첫 번째 컬럼에만 데이터가 있고 나머지는 비어있으면 스니펫 행)
            is_snippet_row = False
            for col in range(1, 5):  # 1-4번 컬럼 확인
                if self.result_table.item(current_row, col) is None:
                    is_snippet_row = True
                    break

            # 같은 데이터의 행 범위 결정
            if is_snippet_row and current_row > 0:
                # 스니펫 행을 선택하면 메타데이터 행과 함께 선택
                meta_row = current_row - 1
            else:
                # 메타데이터 행을 선택한 경우
                meta_row = current_row

            # 다음 행이 스니펫 행인지 확인
            has_snippet = False
            if meta_row + 1 < self.result_table.rowCount():
                for col in range(1, 5):
                    if self.result_table.item(meta_row + 1, col) is None:
                        has_snippet = True
                        break

            # 연결된 행들을 모두 선택 (시그널 임시 차단)
            self.result_table.itemSelectionChanged.disconnect(self._handle_table_selection_changed)
            self.result_table.clearSelection()
            self.result_table.selectRow(meta_row)
            if has_snippet:
                self.result_table.selectRow(meta_row + 1)
            self.result_table.itemSelectionChanged.connect(self._handle_table_selection_changed)

            # 대상 행에서 데이터 가져오기
            item = self.result_table.item(meta_row, 0)  # 첫 번째 컬럼에서 데이터 가져오기
            if item:
                file_path = item.data(Qt.ItemDataRole.UserRole + 1)
                preview = item.data(Qt.ItemDataRole.UserRole)
                file_name = item.data(Qt.ItemDataRole.UserRole + 2)
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

    def _fail_search(self, message: str) -> None:
        self.search_button.setEnabled(True)
        self.folder_tree.setEnabled(True)
        self.cancel_button.setVisible(False)
        
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
        """파일 확장자별 동적 미리보기 로드"""
        self.preview_title.setText(file_name if file_name else "미리보기")
        self.current_preview_path = file_path
        
        if not file_path or not Path(file_path).exists():
            self._show_preview_error("파일을 찾을 수 없습니다.")
            return
        
        suffix = Path(file_path).suffix.lower()
        
        try:
            if suffix == '.pdf':
                self._render_pdf_preview(file_path)
            elif suffix in {'.xlsx', '.csv', '.cell'}:
                self._render_spreadsheet_preview(file_path, suffix)
            elif suffix in {'.hwp', '.hwpx', '.docx', '.txt'}:
                self._render_text_preview(file_path, preview)
            else:
                # 기타 형식은 기존 preview 텍스트 사용
                self._render_plain_preview(preview)
        except Exception as e:
            print(f"[Preview] Error loading preview for {file_path}: {e}")
            self._show_preview_error("미리보기를 지원하지 않거나 파일을 읽을 수 없습니다.")

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
            
            # QPixmap으로 변환하여 QLabel에 표시
            pixmap = QPixmap.fromImage(image)
            
            # 스택 위젯을 이미지 페이지로 전환
            self.preview_stack.setCurrentIndex(PREVIEW_PAGE_IMAGE)
            self.preview_image_label.setPixmap(pixmap)
            
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
                self.preview_stack.setCurrentIndex(PREVIEW_PAGE_IMAGE)
                self.preview_image_label.setPixmap(pixmap)
                return
        
        # 이미지가 아니면 텍스트로 표시
        self._render_plain_preview(preview_text)

    def _clear_preview(self) -> None:
        """미리보기 초기화"""
        if hasattr(self, 'result_table'):
            self.result_table.clearSelection()
        self.preview_title.setText("미리보기")
        self.current_preview_path = ''
        
        # 스택 위젯을 텍스트 페이지로 전환하고 기본 메시지 표시
        self.preview_stack.setCurrentIndex(PREVIEW_PAGE_TEXT)
        self.preview_text_browser.setHtml("""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
                    margin: 0;
                    padding: 40px 20px;
                    background: #F2F2F7;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 200px;
                }
                .placeholder {
                    text-align: center;
                    color: #8E8E93;
                    font-size: 14px;
                }
            </style>
        </head>
        <body>
            <div class="placeholder">문서를 선택하면 미리보기가 표시됩니다.</div>
        </body>
        </html>
        """)
        
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
            /* ── Tabs ── */
            QTabWidget#searchTabs {
                background: transparent;
                border: none;
            }
            QTabWidget#searchTabs::pane {
                background: #FFFFFF;
                border: 0.5px solid #C6C6C8;
                border-radius: 14px;
                top: -1px;
            }
            QTabWidget#searchTabs::tab-bar {
                alignment: left;
            }
            QTabWidget#searchTabs QTabBar::tab {
                background: #F2F2F7;
                border: 0.5px solid #C6C6C8;
                border-bottom: none;
                border-radius: 10px 10px 0 0;
                padding: 8px 16px;
                margin-right: 2px;
                font-weight: 500;
                font-size: 13px;
                color: #8E8E93;
            }
            QTabWidget#searchTabs QTabBar::tab:selected {
                background: #FFFFFF;
                color: #007AFF;
                border-bottom: 1px solid #FFFFFF;
            }
            QTabWidget#searchTabs QTabBar::tab:hover {
                background: rgba(0, 122, 255, 0.06);
                color: #007AFF;
            }
            /* ── Table Widget ── */
            QTableWidget#resultTable {
                background: #FFFFFF;
                border: 0.5px solid #C6C6C8;
                border-radius: 12px;
                gridline-color: #E5E5EA;
                selection-background-color: rgba(0, 122, 255, 0.08);
                selection-color: #333333;
                alternate-background-color: #F9FAFB;
            }
            QTableWidget#resultTable::item {
                padding: 10px 12px;
                border: none;
            }
            QTableWidget#resultTable::item:selected {
                background: rgba(0, 122, 255, 0.08);
                color: #333333;
            }
            QTableWidget#resultTable::item:hover {
                background: rgba(0, 122, 255, 0.05);
            }
            QTableWidget#resultTable QHeaderView::section {
                background: #F2F2F7;
                border: none;
                border-bottom: 0.5px solid #C6C6C8;
                padding: 12px;
                font-weight: 600;
                font-size: 13px;
                color: #3C3C43;
            }
            QTableWidget#resultTable QHeaderView::section:first {
                border-top-left-radius: 12px;
            }
            QTableWidget#resultTable QHeaderView::section:last {
                border-top-right-radius: 12px;
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
        total_width = self.top_splitter.size().width()
        total_height = self.vertical_splitter.size().height()
        if total_width > 0:
            self.top_splitter.setSizes([int(total_width * 0.50), int(total_width * 0.50)])
            self.bottom_splitter.setSizes([int(total_width * 0.62), int(total_width * 0.38)])
        if total_height > 0:
            self.vertical_splitter.setSizes([int(total_height * 0.42), int(total_height * 0.58)])

    def closeEvent(self, event) -> None:
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
